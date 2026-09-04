import json
import os

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
        "scope": "openid profile email",
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


def load_services():
    with open("services.json", "r") as f:
        return json.load(f)


def find(name, path):
    for root, dirs, files in os.walk(path):
        if name in files:
            return os.path.join(root, name)


# Assets routes
@app.route("/assets/<path:path>")
def send_assets(path):
    if path.endswith(".json"):
        return send_from_directory(
            "templates/assets", path, mimetype="application/json"
        )

    if os.path.isfile("templates/assets/" + path):
        return send_from_directory("templates/assets", path)

    # Try looking in one of the directories
    filename: str = path.split("/")[-1]
    if filename.endswith((".png", ".jpg", ".jpeg", ".svg")):
        if os.path.isfile("templates/assets/img/" + filename):
            return send_from_directory("templates/assets/img", filename)
        if os.path.isfile("templates/assets/img/favicon/" + filename):
            return send_from_directory("templates/assets/img/favicon", filename)

    return render_template("404.html"), 404


@app.route("/services/<string:category>/<string:service>.png")
@cache.cached(timeout=3600, query_string=True)
def service_images(category: str, service: str):
    services = load_services()
    for svc in services.get(category, []):
        if svc["id"] == service:
            # If icon is defined, use it, otherwise return 404
            if "icon" in svc:
                # If the icon isn't a URL, try to serve it from the filesystem
                if not svc["icon"].startswith("http"):
                    icon_path = os.path.join(
                        "templates/assets/img/services", svc["icon"]
                    )
                    if os.path.isfile(icon_path):
                        return make_response(
                            open(icon_path, "rb").read(),
                            200,
                            {"Content-Type": "image/png"},
                        )
                    else:
                        print(f"Icon file not found for {service} at {icon_path}")
                        break  # Break to return default favicon

                # Pull image from URL and return it
                req = requests.get(svc["icon"], timeout=5)
                if req.status_code == 200:
                    return make_response(
                        req.content,
                        200,
                        {"Content-Type": req.headers["Content-Type"]},
                    )

            # Read default favicon into memory to allow caching (pickling)
            with open("templates/assets/img/favicon.png", "rb") as f:
                return make_response(f.read(), 200, {"Content-Type": "image/png"})

    return render_template("404.html"), 404


# region Special routes
@app.route("/favicon.png")
def faviconPNG():
    return send_from_directory("templates/assets/img", "favicon.png")


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
    services = load_services()
    user = session.get("user")

    if isCLI(request):
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

    return render_template("index.html", services=services, user=user)


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


@app.route("/api/v1/cloud_quota", methods=["GET"])
def api_cloud_quota():
    """
    API endpoint to get the user's cloud quota information.
    """

    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    quota_info = getUserQuota(user["preferred_username"])
    if "error" in quota_info:
        return jsonify(quota_info), 500
    return jsonify(quota_info)


@app.route("/api/v1/immich")
def api_immich_stats():
    """
    API endpoint to get the user's Immich stats.
    """

    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    stats = get_immich_stats(user["sub"])
    if "error" in stats:
        return jsonify(stats), 500
    return jsonify(stats)


@app.route("/api/v1/links")
def api_links_stats():
    """
    API endpoint to get the user's Links stats.
    """

    user = session.get("user")
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    from tools.links import get_links_stats

    stats = get_links_stats(user["email"])
    if "error" in stats:
        return jsonify(stats), 500
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
            session["user"] = user
    except OAuthError as e:
        app.logger.warning(f"OAuth callback failed: {e}")

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user", None)
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
