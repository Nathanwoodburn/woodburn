import json
import os
import secrets
from urllib.parse import urlparse

import dotenv
import requests
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from flask_caching import Cache
from werkzeug.exceptions import InternalServerError, MethodNotAllowed
from werkzeug.middleware.proxy_fix import ProxyFix

from tools.ascii import render_ascii_page
from tools.cloud import getUserQuota
from tools.immich import get_immich_stats

dotenv.load_dotenv()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = os.getenv("APP_SECRET_KEY", os.urandom(24))

# Cache Configuration
cache = Cache(app, config={"CACHE_TYPE": "SimpleCache", "CACHE_DEFAULT_TIMEOUT": 300})

# OAuth Configuration
oauth = OAuth(app)
oauth.register(
    name="authentik",
    server_metadata_url=os.getenv("AUTHENTIK_METADATA_URL"),
    client_id=os.getenv("AUTHENTIK_CLIENT_ID"),
    client_secret=os.getenv("AUTHENTIK_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email goauthentik.io/api",
    },
)

# CLI Agents to return cli formatted responses
CLI_AGENTS = ["curl", "hurl", "xh", "Posting", "HTTPie", "nushell"]


def isCLI(request) -> bool:
    """
    Check if the request is from curl, hurl, xh, etc., or requested via query param.

    Args:
        request (Request): The Flask request object

    Returns:
        bool: True if the request is from a CLI agent or ASCII format requested, False otherwise
    """
    if request.args.get("format") in [
        "ascii",
        "txt",
        "text",
        "cli",
    ] or request.args.get("cli") in ["1", "true"]:
        return True
    if request.headers and request.headers.get("User-Agent"):
        user_agent = request.headers.get("User-Agent", "")
        return any(agent in user_agent for agent in CLI_AGENTS)
    return False


def get_client_ip(request) -> str:
    """
    Extract the real client IP address considering reverse proxies (Cloudflare, NGINX, etc.).
    """
    if cf_ip := request.headers.get("CF-Connecting-IP"):
        return cf_ip.strip()
    if x_real := request.headers.get("X-Real-IP"):
        return x_real.strip()
    if x_forwarded := request.headers.get("X-Forwarded-For"):
        return x_forwarded.split(",")[0].strip()
    return request.remote_addr or ""


_services_cache = {"mtime": 0.0, "data": {}}


def load_services() -> dict:
    try:
        mtime = os.path.getmtime("services.json")
        if mtime != _services_cache["mtime"]:
            with open("services.json", "r") as f:
                _services_cache["data"] = json.load(f)
            _services_cache["mtime"] = mtime
        return _services_cache["data"]
    except (OSError, json.JSONDecodeError):
        with open("services.json", "r") as f:
            return json.load(f)


def sanitize_userinfo(user: dict | None) -> dict | None:
    if not user:
        return None
    allowed_keys = {"sub", "preferred_username", "name", "email", "groups"}
    return {k: user[k] for k in allowed_keys if k in user}


def store_session_access_token(access_token: str) -> str:
    sid = session.get("sid")
    if not sid:
        sid = secrets.token_hex(16)
        session["sid"] = sid
    cache.set(f"access_token_{sid}", access_token, timeout=86400)
    # Ensure large access_token is never written to client cookie
    session.pop("access_token", None)
    return sid


def get_session_access_token() -> str | None:
    sid = session.get("sid")
    if sid:
        token = cache.get(f"access_token_{sid}")
        if token:
            return token
    return session.get("access_token")


def get_authentik_base_url() -> str:
    """
    Extract the base Authentik URL from environment variables or AUTHENTIK_METADATA_URL.
    """
    if explicit_url := (
        os.getenv("AUTHENTIK_API_URL")
        or os.getenv("AUTHENTIK_INTERNAL_URL")
        or os.getenv("AUTHENTIK_URL")
    ):
        return explicit_url.rstrip("/")
    metadata_url = os.getenv("AUTHENTIK_METADATA_URL", "")
    if metadata_url:
        parsed = urlparse(metadata_url)
        return f"{parsed.scheme}://{parsed.netloc}"
    return ""


def get_user_authentik_apps(
    access_token: str | None, user_sub: str | None = None
) -> list[dict] | None:
    """
    Fetch the list of applications the current user can access from Authentik API.
    Results are cached in Flask-Caching to avoid querying Authentik on every request.
    Returns None if the request failed or access token was missing/unauthorized.
    """
    if not access_token:
        return None

    cache_key = (
        f"authentik_apps_{user_sub}"
        if user_sub
        else f"authentik_apps_{access_token[:16]}"
    )
    cached_apps = cache.get(cache_key)
    if cached_apps is not None:
        return cached_apps

    error_key = f"authentik_apps_err_{user_sub}" if user_sub else None
    if error_key and cache.get(error_key):
        return None

    base_url = get_authentik_base_url()
    if not base_url:
        app.logger.warning("No Authentik base URL configured.")
        return None

    connect_timeout = float(os.getenv("AUTHENTIK_CONNECT_TIMEOUT", "5"))
    read_timeout = float(os.getenv("AUTHENTIK_API_TIMEOUT", "15"))
    timeout = (connect_timeout, read_timeout)

    apps: list[dict] = []
    url = f"{base_url}/api/v3/core/applications/?page_size=100"
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}

    try:
        while url:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                app.logger.warning(
                    f"Authentik applications API returned status {resp.status_code}: {resp.text[:200]}. "
                    "Ensure 'goauthentik.io/api' scope is permitted in Authentik provider settings."
                )
                if error_key:
                    cache.set(error_key, True, timeout=60)
                return None
            data = resp.json()
            apps.extend(data.get("results", []))
            url = data.get("pagination", {}).get("next")

        cache.set(cache_key, apps, timeout=300)
        return apps
    except requests.RequestException as e:
        app.logger.error(f"Failed to connect to Authentik API: {e}")
        if error_key:
            cache.set(error_key, True, timeout=60)
        return None


def _normalize_slug(s: str) -> str:
    return s.strip().lower().replace("_", "-")


def _get_netloc(url: str) -> str:
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc or parsed.path
        return netloc.lower().split(":")[0]
    except (ValueError, AttributeError):
        return ""


def is_service_accessible_via_authentik(svc: dict, authentik_apps: list[dict]) -> bool:
    """
    Check whether a service in services.json matches any application returned by Authentik.
    Matches by:
    1. Explicit 'authentik_slug' in services.json (set to false to bypass)
    2. Normalized ID matching app slug
    3. Normalized Name matching app name
    4. URL Host matching app launch URL host
    """
    if svc.get("unrestricted") is True or svc.get("authentik_slug") is False:
        return True

    explicit_slug = svc.get("authentik_slug")
    if explicit_slug and isinstance(explicit_slug, str):
        target = _normalize_slug(explicit_slug)
        return any(
            _normalize_slug(app.get("slug", "")) == target for app in authentik_apps
        )

    svc_id = _normalize_slug(svc.get("id", ""))
    svc_name = svc.get("name", "").strip().lower()
    svc_host = _get_netloc(svc.get("url", ""))

    for app_item in authentik_apps:
        app_slug = _normalize_slug(app_item.get("slug", ""))
        if svc_id and app_slug and svc_id == app_slug:
            return True

        app_name = app_item.get("name", "").strip().lower()
        if svc_name and app_name and svc_name == app_name:
            return True

        app_url = app_item.get("launch_url") or app_item.get("meta_launch_url") or ""
        app_host = _get_netloc(app_url)
        if svc_host and app_host and svc_host == app_host:
            return True

    return False


def filter_services_for_user(
    services: dict, user: dict | None, access_token: str | None
) -> dict:
    """
    Filter the services dictionary based on Authentik application permissions.
    """
    if not user:
        return {
            "external": services.get("external", []),
            "internal": [],
        }

    internal_services = services.get("internal", [])
    if not internal_services:
        return {
            "external": services.get("external", []),
            "internal": [],
        }

    user_identifier = user.get("sub") or user.get("preferred_username") or "user"
    authentik_apps = get_user_authentik_apps(access_token, user_identifier)

    if authentik_apps is None:
        fail_closed = os.getenv("AUTHENTIK_FILTER_FAIL_CLOSED", "false").lower() in [
            "1",
            "true",
            "yes",
        ]
        if fail_closed:
            app.logger.warning(
                "Authentik API inaccessible and fail-closed enabled; hiding internal services."
            )
            allowed_internal = []
        else:
            app.logger.warning(
                "Authentik API inaccessible or access token missing; showing all internal services."
            )
            allowed_internal = internal_services
    else:
        allowed_internal = [
            svc
            for svc in internal_services
            if is_service_accessible_via_authentik(svc, authentik_apps)
        ]

    return {
        "external": services.get("external", []),
        "internal": allowed_internal,
    }


def user_has_service_access(
    service_id: str, user: dict | None, access_token: str | None
) -> bool:
    if not user:
        return False
    services = load_services()
    for svc in services.get("internal", []):
        if svc.get("id") == service_id:
            filtered = filter_services_for_user({"internal": [svc]}, user, access_token)
            return len(filtered.get("internal", [])) > 0
    return False


def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)


# Assets routes
@app.route("/assets/<path:path>")
def send_assets(path):
    resp = None
    if path.endswith(".json"):
        resp = send_from_directory(
            "templates/assets", path, mimetype="application/json"
        )
    elif os.path.isfile("templates/assets/" + path):
        resp = send_from_directory("templates/assets", path)
    else:
        # Try looking in one of the directories
        filename: str = path.split("/")[-1]
        if filename.endswith((".png", ".jpg", ".jpeg", ".svg")):
            if os.path.isfile("templates/assets/img/" + filename):
                resp = send_from_directory("templates/assets/img", filename)
            elif os.path.isfile("templates/assets/img/favicon/" + filename):
                resp = send_from_directory("templates/assets/img/favicon", filename)

    if resp is not None:
        response = make_response(resp)
        response.headers["Cache-Control"] = "public, max-age=86400"
        return response

    return render_template("404.html"), 404


@app.route("/services/<string:category>/<string:service>.png")
@cache.cached(timeout=3600, query_string=True)
def service_images(category: str, service: str):
    services = load_services()
    for svc in services.get(category, []):
        if svc["id"] == service:
            # If icon is defined, use it, otherwise return default
            if "icon" in svc:
                # If the icon isn't a URL, try to serve it from the filesystem
                if not svc["icon"].startswith("http"):
                    icon_path = os.path.join(
                        "templates/assets/img/services", svc["icon"]
                    )
                    if os.path.isfile(icon_path):
                        with open(icon_path, "rb") as f:
                            resp = make_response(
                                f.read(),
                                200,
                                {"Content-Type": "image/png"},
                            )
                        resp.headers["Cache-Control"] = (
                            "public, max-age=604800, immutable"
                        )
                        return resp
                    else:
                        print(f"Icon file not found for {service} at {icon_path}")
                        break  # Break to return default favicon

                # For remote icons: check local disk cache first
                cache_dir = os.path.join("templates/assets/img/services", "cache")
                os.makedirs(cache_dir, exist_ok=True)
                cached_file = os.path.join(cache_dir, f"{service}.png")
                if os.path.isfile(cached_file):
                    with open(cached_file, "rb") as f:
                        resp = make_response(
                            f.read(), 200, {"Content-Type": "image/png"}
                        )
                    resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
                    return resp

                # Pull image from URL, persist to disk cache, and return it
                try:
                    req = requests.get(svc["icon"], timeout=5)
                    if req.status_code == 200:
                        content_type = req.headers.get("Content-Type", "image/png")
                        with open(cached_file, "wb") as f:
                            f.write(req.content)
                        resp = make_response(
                            req.content,
                            200,
                            {"Content-Type": content_type},
                        )
                        resp.headers["Cache-Control"] = (
                            "public, max-age=604800, immutable"
                        )
                        return resp
                except requests.RequestException as e:
                    print(f"Failed to fetch icon for {service} from {svc['icon']}: {e}")

            # Fallback to default favicon
            with open("templates/assets/img/favicon.png", "rb") as f:
                resp = make_response(f.read(), 200, {"Content-Type": "image/png"})
            resp.headers["Cache-Control"] = "public, max-age=86400"
            return resp

    return render_template("404.html"), 404


# region Special routes
@app.route("/favicon.png")
def faviconPNG():
    resp = make_response(send_from_directory("templates/assets/img", "favicon.png"))
    resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return resp


@app.route("/.well-known/<path:path>")
def wellknown(path):
    # Try to proxy to https://nathan.woodburn.au/.well-known/
    req = requests.get(f"https://nathan.woodburn.au/.well-known/{path}")
    return make_response(
        req.content, 200, {"Content-Type": req.headers["Content-Type"]}
    )


# endregion


# region Main routes
@app.route("/")
def index():
    raw_services = load_services()
    user = session.get("user")

    if isCLI(request):
        access_token = get_session_access_token()
        services = filter_services_for_user(raw_services, user, access_token)
        use_color = not (
            request.args.get("color") in ["0", "false", "no"]
            or request.args.get("plain") in ["1", "true", "yes"]
            or "NO_COLOR" in request.headers
        )
        ascii_output = render_ascii_page(
            services=services,
            user=user,
            use_color=use_color,
            base_url=request.host_url.rstrip("/"),
            client_ip=get_client_ip(request),
        )
        return make_response(
            ascii_output, 200, {"Content-Type": "text/plain; charset=utf-8"}
        )

    # Passive SSO check on initial visit for unauthenticated users
    if "user" not in session and not session.get("auth_checked"):
        session["auth_checked"] = True
        redirect_uri = url_for("auth_callback", _external=True)
        return oauth.authentik.authorize_redirect(redirect_uri, prompt="none")  # type: ignore

    services_loading = False
    allowed_internal = []
    if user:
        user_identifier = user.get("sub") or user.get("preferred_username") or "user"
        cached_apps = cache.get(f"authentik_apps_{user_identifier}")
        if cached_apps is not None:
            # Memory cache hit: instant render with zero network calls
            allowed_internal = [
                svc
                for svc in raw_services.get("internal", [])
                if is_service_accessible_via_authentik(svc, cached_apps)
            ]
            services_loading = False
        else:
            # Uncached: render immediately with skeleton cards; client fetches via API
            services_loading = True

    services = {
        "external": raw_services.get("external", []),
        "internal": allowed_internal,
    }

    return render_template(
        "index.html",
        services=services,
        user=user,
        services_loading=services_loading,
    )


@app.route("/<path:path>")
def catch_all(path: str):
    if os.path.isfile("templates/" + path):
        return render_template(path)

    # Try with .html
    if os.path.isfile("templates/" + path + ".html"):
        return render_template(path + ".html")

    if os.path.isfile("templates/" + path.strip("/") + ".html"):
        return render_template(path.strip("/") + ".html")

    # Try to find a file matching
    if path.count("/") < 1:
        # Try to find a file matching
        filename = find(path, "templates")
        if filename:
            return send_file(filename)

    return render_template("404.html"), 404


# endregion


# region API routes
@app.route("/api/v1/status")
def api_status():
    return jsonify({"status": "ok"})


@app.route("/api/v1/internal_services")
def api_internal_services():
    """
    API endpoint to fetch the internal services the logged-in user can access.
    """
    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    raw_services = load_services()
    access_token = get_session_access_token()
    filtered = filter_services_for_user(raw_services, user, access_token)
    return jsonify({"services": filtered.get("internal", [])})


@app.route("/api/v1/cloud_quota", methods=["GET"])
def api_cloud_quota():
    """
    API endpoint to get the user's cloud quota information.
    """

    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    access_token = get_session_access_token()
    if not user_has_service_access("cloud", user, access_token):
        return jsonify({"error": "Forbidden"}), 403

    username = user["preferred_username"]
    cache_key = f"cloud_quota_{username}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return jsonify(cached_data)

    quota_info = getUserQuota(username)
    if "error" in quota_info:
        return jsonify(quota_info), 500
    cache.set(cache_key, quota_info, timeout=300)
    return jsonify(quota_info)


@app.route("/api/v1/immich")
def api_immich_stats():
    """
    API endpoint to get the user's Immich stats.
    """

    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    access_token = get_session_access_token()
    if not user_has_service_access("immich", user, access_token):
        return jsonify({"error": "Forbidden"}), 403

    user_sub = user["sub"]
    cache_key = f"immich_stats_{user_sub}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return jsonify(cached_data)

    stats = get_immich_stats(user_sub)
    if "error" in stats:
        return jsonify(stats), 500
    cache.set(cache_key, stats, timeout=300)
    return jsonify(stats)


@app.route("/api/v1/links")
def api_links_stats():
    """
    API endpoint to get the user's Links stats.
    """

    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    access_token = get_session_access_token()
    if not user_has_service_access("links", user, access_token):
        return jsonify({"error": "Forbidden"}), 403

    email = user["email"]
    cache_key = f"links_stats_{email}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return jsonify(cached_data)

    from tools.links import get_links_stats

    stats = get_links_stats(email)
    if "error" in stats:
        return jsonify(stats), 500
    cache.set(cache_key, stats, timeout=300)
    return jsonify(stats)


# @app.route("/api/v1/user")
# def api_user_info():
#     return(session.get("user"))

# endregion

# region Auth routes


@app.route("/login")
def login():
    redirect_uri = url_for("auth_callback", _external=True)
    return oauth.authentik.authorize_redirect(redirect_uri)  # type: ignore


@app.route("/auth/callback")
def auth_callback():
    # If Authentik returns an error (e.g. login_required or interaction_required with prompt=none)
    if "error" in request.args:
        return redirect(url_for("index"))

    try:
        token = oauth.authentik.authorize_access_token()  # type: ignore
        user = token.get("userinfo")
        if user:
            session["user"] = sanitize_userinfo(user)
            access_token = token.get("access_token")
            if access_token:
                store_session_access_token(access_token)
    except OAuthError as e:
        app.logger.warning(f"OAuth callback failed: {e}")

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    sid = session.get("sid")
    if sid:
        cache.delete(f"access_token_{sid}")
    user = session.get("user")
    if user:
        user_identifier = user.get("sub") or user.get("preferred_username")
        if user_identifier:
            cache.delete(f"authentik_apps_{user_identifier}")
            cache.delete(f"authentik_apps_err_{user_identifier}")
    session.clear()
    session["auth_checked"] = (
        True  # Prevent immediately auto-redirecting right after logout
    )
    return redirect(url_for("index"))


# endregion


# region Error handling
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


@app.errorhandler(InternalServerError)
def handle_internal_server_error(e: InternalServerError):
    return render_template("500.html", message=e.original_exception), 500


@app.errorhandler(MethodNotAllowed)
def handle_method_not_allowed(e: MethodNotAllowed):
    if isCLI(request):
        return jsonify(
            {"status": 405, "message": "Umm, what do you think you are doing?"}
        ), 405
    return render_template("405.html"), 405


# endregion


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="127.0.0.1")
