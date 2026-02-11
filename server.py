from flask import (
    Flask,
    make_response,
    jsonify,
    render_template,
    send_from_directory,
    send_file,
    session,
    redirect,
    url_for,
)
from werkzeug.exceptions import InternalServerError
from werkzeug.middleware.proxy_fix import ProxyFix
import os
import json
import requests
from datetime import datetime
import dotenv
from authlib.integrations.flask_client import OAuth
from flask_caching import Cache

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
    if (
        filename.endswith(".png")
        or filename.endswith(".jpg")
        or filename.endswith(".jpeg")
        or filename.endswith(".svg")
    ):
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
                try:
                    req = requests.get(svc["icon"], timeout=5)
                    if req.status_code == 200:
                        return make_response(
                            req.content,
                            200,
                            {"Content-Type": req.headers["Content-Type"]},
                        )
                except Exception as e:
                    print(f"Failed to fetch icon for {service}: {e}")

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
    # Get current time in the format "dd MMM YYYY hh:mm AM/PM"
    current_datetime = datetime.now().strftime("%d %b %Y %I:%M %p")

    services = load_services()
    user = session.get("user")

    return render_template(
        "index.html", datetime=current_datetime, services=services, user=user
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

api_requests = 0


@app.route("/api/v1/data", methods=["GET"])
def api_data():
    """
    Example API endpoint that returns some data.
    You can modify this to return whatever data you need.
    """

    global api_requests
    api_requests += 1

    data = {
        "header": "Sample API Response",
        "content": f"Hello, this is a sample API response! You have called this endpoint {api_requests} times.",
        "timestamp": datetime.now().isoformat(),
    }
    return jsonify(data)


# endregion


# region Error Catching
# 404 catch all
@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# endregion
# region Auth routes


@app.route("/login")
def login():
    redirect_uri = url_for("auth_callback", _external=True)
    return oauth.authentik.authorize_redirect(redirect_uri)  # type: ignore


@app.route("/auth/callback")
def auth_callback():
    token = oauth.authentik.authorize_access_token()  # type: ignore
    user = token.get("userinfo")
    if user:
        session["user"] = user
    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# endregion

# region Error handling


@app.errorhandler(InternalServerError)
def handle_internal_server_error(e: InternalServerError):
    return render_template("500.html", message=e.original_exception), 500


# endregion


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="127.0.0.1")
