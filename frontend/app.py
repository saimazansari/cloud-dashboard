from flask import Flask, session, request, redirect, render_template, Response, jsonify
import requests
import os
import csv
import io
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024

@app.after_request
def set_cache(response):
    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")

RESOURCE_COLORS = {
    "Virtual Machine": "#7c6ff7",
    "Kubernetes Cluster": "#38bdf8",
    "Load Balancer": "#fbbf24",
    "Storage Account": "#4ade80",
    "Database": "#f472b6",
    "CDN Profile": "#fb923c",
    "Serverless Function": "#a78bfa",
    "Virtual Network": "#14b8a6",
    "Network Security Group": "#f97316",
    "Key Vault": "#e879f9",
    "Public IP": "#06b6d4",
    "Network Watcher": "#6366f1",
    "Container Registry": "#ec4899",
    "Managed Disk": "#84cc16",
}

def type_color(rtype):
    c = RESOURCE_COLORS.get(rtype)
    if c:
        return c
    h = hash(rtype) & 0xFFFFFF
    return "#" + format(h % 0xCCCCCC + 0x333333, "06x")

HOURS_PER_MONTH = 730
USD_TO_INR = 85.0


def api_request(method, path, data=None):
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if session.get("user_id") and session.get("token"):
        headers["X-User-ID"] = str(session["user_id"])
        headers["X-Auth-Token"] = session["token"]
    if session.get("subscription_id"):
        headers["X-Subscription-ID"] = session["subscription_id"]
    try:
        timeout = 120 if path == "/api/cost-summary" else 120 if path.endswith("/stop") or path.endswith("/start") else 30
        response = requests.request(method, f"{BACKEND_URL}{path}", json=data, headers=headers, timeout=timeout)
        if method == "GET":
            return response.json() if response.status_code < 500 else {"error": "server error"}
        return response.json(), response.status_code
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend"} if method == "GET" else ({"error": "Could not connect to backend"}, 503)
    except requests.exceptions.Timeout:
        return {"error": "Backend timed out. Please try again."} if method == "GET" else ({"error": "Backend timed out. The operation is taking longer than expected."}, 504)
    except Exception as e:
        return {"error": str(e)} if method == "GET" else ({"error": str(e)}, 500)

api_get = lambda p: api_request("GET", p)
api_post = lambda p, d: api_request("POST", p, d)
api_put = lambda p, d: api_request("PUT", p, d)


@app.context_processor
def inject_globals():
    return {
        "google_client_id": GOOGLE_CLIENT_ID,
        "github_client_id": GITHUB_CLIENT_ID,
    }

def derive_health(status):
    if status == "running":
        return "healthy"
    elif status == "stopped":
        return "degraded"
    return "offline"

def status_badge_class(status):
    if status in ("running", "healthy", "completed", "starting"):
        return "success"
    elif status in ("stopped", "degraded", "in_progress", "stopping"):
        return "warning"
    return "danger"


@app.route("/")
def dashboard():
    if not session.get("user_id"):
        return redirect("/login")

    error = None
    resources = []

    with ThreadPoolExecutor(max_workers=3) as pool:
        fut_resources = pool.submit(api_get, "/api/resources")
        fut_cost = pool.submit(api_get, "/api/cost-summary")
        fut_subs = pool.submit(api_get, "/api/subscriptions")
        data = fut_resources.result()
        cost_data = fut_cost.result()
        sub_data = fut_subs.result()

    if isinstance(data, list):
        for resource in data:
            resource["health"] = derive_health(resource["status"])
            resource["health_class"] = status_badge_class(resource["health"])
            resource["status_class"] = status_badge_class(resource["status"])
            resource["type_color"] = type_color(resource["type"])
            resource["cost_inr_per_hour"] = round(resource.get("cost_per_hour", 0) * USD_TO_INR, 2)
            resource["monthly_cost_inr"] = round(resource.get("cost_per_hour", 0) * HOURS_PER_MONTH * USD_TO_INR, 2)
        resources = data
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    stats = {
        "total": 0,
        "running": 0,
        "stopped": 0,
        "terminated": 0,
        "monthly_cost": 0,
        "hourly_cost": 0,
        "monthly_cost_inr": 0,
        "hourly_cost_inr": 0,
        "cost_sofar": 0,
        "cost_sofar_inr": 0,
    }
    health = {"healthy": 0, "degraded": 0, "offline": 0}
    type_colors_json = "{}"

    if resources:
        groups = {}
        status_groups = {}
        hourly_total = 0

        for resource in resources:
            resource_type = resource["type"]
            groups[resource_type] = groups.get(resource_type, 0) + 1
            resource_status = resource["status"]
            status_groups[resource_status] = status_groups.get(resource_status, 0) + 1
            hourly_total += resource.get("cost_per_hour", 0)
            resource_health = resource["health"]
            health[resource_health] = health.get(resource_health, 0) + 1

        stats["total"] = len(resources)
        stats["running"] = status_groups.get("running", 0)
        stats["stopped"] = status_groups.get("stopped", 0)
        stats["terminated"] = status_groups.get("terminated", 0)
        stats["hourly_cost"] = round(hourly_total, 4)
        stats["monthly_cost"] = round(hourly_total * HOURS_PER_MONTH, 2)
        stats["hourly_cost_inr"] = round(hourly_total * USD_TO_INR, 2)
        stats["monthly_cost_inr"] = round(hourly_total * HOURS_PER_MONTH * USD_TO_INR, 2)
        type_colors_json = json.dumps({t: type_color(t) for t in groups.keys()})

    if isinstance(cost_data, dict) and "error" not in cost_data and cost_data.get("total_monthly"):
        stats["monthly_cost"] = round(cost_data["total_monthly"], 2)
        stats["hourly_cost"] = round(cost_data["total_hourly"], 4)
        stats["monthly_cost_inr"] = round(cost_data["total_monthly"] * USD_TO_INR, 2)
        stats["hourly_cost_inr"] = round(cost_data["total_hourly"] * USD_TO_INR, 2)

    now = datetime.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    hours_so_far = (now - month_start).total_seconds() / 3600
    stats["cost_sofar"] = round(stats["hourly_cost"] * hours_so_far, 2)
    stats["cost_sofar_inr"] = round(stats["cost_sofar"] * USD_TO_INR, 2)

    subscriptions = sub_data if isinstance(sub_data, list) else []

    if not session.get("subscription_id") and subscriptions:
        current = next((s for s in subscriptions if s.get("is_current")), None)
        if current:
            session["subscription_id"] = current["id"]

    return render_template(
        "dashboard.html",
        resources=resources,
        error=error,
        stats=stats,
        health=health,
        type_colors_json=type_colors_json,
        hours_sofar=int(hours_so_far),
        subscriptions=subscriptions,
    )


@app.route("/cost-summary")
def cost_summary():
    if not session.get("user_id"):
        return redirect("/login")

    data = api_get("/api/cost-summary")
    error = None
    summary = {}
    breakdown_json = "[]"

    if isinstance(data, dict) and "error" not in data:
        summary = data
        breakdown_json = json.dumps(data.get("by_type", []))
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    cost_type_colors = {t["type"]: type_color(t["type"]) for t in summary.get("by_type", [])}
    cost_type_colors_json = json.dumps(cost_type_colors)

    return render_template("cost.html", summary=summary, error=error, breakdown_json=breakdown_json, type_colors_json=cost_type_colors_json)


@app.route("/settings")
def settings():
    if not session.get("user_id"):
        return redirect("/login")
    return render_template("settings.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        result, status_code = api_post(
            "/api/login",
            {
                "username": request.form["username"],
                "password": request.form["password"],
            },
        )
        if status_code == 200 and "token" in result:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            session["token"] = result["token"]
            return redirect("/")
        return render_template(
            "login.html",
            error=result.get("error", "Login failed"),
        )
    return render_template("login.html")


@app.route("/auth/google", methods=["POST"])
def auth_google():
    data = request.get_json(force=True)
    result, status_code = api_post("/api/auth/google", {"credential": data.get("credential", "")})
    if status_code == 200 and "token" in result:
        session["user_id"] = result["user_id"]
        session["username"] = result["username"]
        session["token"] = result["token"]
        return {"ok": True}
    return {"error": result.get("error", "Authentication failed")}, status_code


@app.route("/auth/github")
def auth_github():
    if not GITHUB_CLIENT_ID:
        return render_template("login.html", error="GitHub sign-in is not configured")
    redirect_uri = request.url_root.rstrip("/") + "/auth/github/callback"
    url = (
        "https://github.com/login/oauth/authorize"
        "?client_id=" + GITHUB_CLIENT_ID +
        "&redirect_uri=" + redirect_uri +
        "&scope=read:user"
    )
    return redirect(url)


@app.route("/auth/github/callback")
def auth_github_callback():
    code = request.args.get("code")
    if not code:
        return render_template("login.html", error="GitHub authorization failed: no code returned")

    result, status_code = api_post("/api/auth/github", {"code": code})
    if status_code == 200 and "token" in result:
        session["user_id"] = result["user_id"]
        session["username"] = result["username"]
        session["token"] = result["token"]
        return redirect("/")

    return render_template("login.html", error=result.get("error", "GitHub sign-in failed"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if not username or not password:
            return render_template("register.html", error="Username and password are required")
        if password != confirm:
            return render_template("register.html", error="Passwords do not match")

        result, status_code = api_post("/api/register", {"username": username, "password": password})
        if status_code == 200 and "token" in result:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            session["token"] = result["token"]
            return redirect("/")
        return render_template("register.html", error=result.get("error", "Registration failed"))

    return render_template("register.html")


@app.route("/api/resources")
def resource_list_proxy():
    return api_get("/api/resources")


@app.route("/api/resources/<int:resource_id>")
def resource_detail_proxy(resource_id):
    return api_get(f"/api/resources/{resource_id}")


def safe_redirect(fallback="/"):
    ref = request.referrer
    if ref:
        from urllib.parse import urlparse
        host = request.host
        ref_host = urlparse(ref).hostname
        if ref_host == host:
            return redirect(ref)
    return redirect(fallback)


@app.route("/api/resources/<int:resource_id>/stop-redirect")
def resource_stop_redirect(resource_id):
    api_post(f"/api/resources/{resource_id}/stop", {})
    return safe_redirect()


@app.route("/api/resources/<int:resource_id>/start-redirect")
def resource_start_redirect(resource_id):
    api_post(f"/api/resources/{resource_id}/start", {})
    return safe_redirect()


@app.route("/api/resources/batch", methods=["POST"])
def resource_batch_proxy():
    data = request.get_json(force=True)
    result, status_code = api_post("/api/resources/batch", data)
    if status_code == 200:
        return {"ok": True}
    return {"error": result.get("error", "Batch action failed")}, status_code


@app.route("/api/cost-history")
def cost_history_proxy():
    return api_get("/api/cost-history")


@app.route("/api/cost-summary")
def cost_summary_proxy():
    return api_get("/api/cost-summary")


@app.route("/api/subscriptions")
def subscriptions_proxy():
    return api_get("/api/subscriptions")


@app.route("/api/user/preferences", methods=["GET", "PUT"])
def user_preferences_proxy():
    if request.method == "PUT":
        data = request.get_json(force=True)
        result, sc = api_put("/api/user/preferences", data)
        if sc == 200:
            return {"ok": True}
        return result, sc
    return api_get("/api/user/preferences")


@app.route("/set-subscription", methods=["POST"])
def set_subscription():
    sub_id = request.form.get("subscription_id")
    if sub_id:
        session["subscription_id"] = sub_id
    return safe_redirect("/login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/export/csv/resources")
def export_resources_csv():
    data = api_get("/api/resources")
    if not isinstance(data, list):
        data = []
    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(["Name", "Type", "Region", "Status", "Cost/hr", "Cost/mo", "Created"])
    for r in data:
        w.writerow([r.get("name",""), r.get("type",""), r.get("region",""), r.get("status",""), r.get("cost_per_hour",0), round(r.get("cost_per_hour",0)*730,2), r.get("created_at","")])
    out = io.BytesIO()
    out.write(si.getvalue().encode("utf-8"))
    out.seek(0)
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=resources.csv"})


@app.route("/export/csv/costs")
def export_costs_csv():
    data = api_get("/api/cost-summary")
    si = io.StringIO()
    w = csv.writer(si)
    w.writerow(["Type", "Cost/hr", "Cost/mo"])
    for b in data.get("by_type", []) if isinstance(data, dict) else []:
        w.writerow([b.get("type",""), b.get("hourly",0), b.get("monthly",0)])
    out = io.BytesIO()
    out.write(si.getvalue().encode("utf-8"))
    out.seek(0)
    return Response(out.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=costs.csv"})


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
