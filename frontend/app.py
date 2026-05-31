from flask import Flask, session, request, redirect, render_template_string, url_for
import requests
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

BASE_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Cloud Cost & Infrastructure Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f0f2f5; color: #333; }
        nav { background: #f8bbd0; color: #880e4f; padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
        nav a { color: #880e4f; text-decoration: none; margin-left: 18px; font-size: 14px; }
        nav a:hover { text-decoration: underline; }
        nav .brand { font-weight: 700; font-size: 18px; }
        nav .brand a { margin: 0; }
        .container { max-width: 1000px; margin: 24px auto; padding: 0 16px; }
        .card { background: white; border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        h1 { font-size: 24px; margin-bottom: 16px; color: #c2185b; }
        h2 { font-size: 18px; margin-bottom: 12px; color: #444; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #e0e0e0; font-size: 14px; }
        th { background: #f8f9fa; color: #555; font-weight: 600; }
        tr:hover { background: #f1f3f4; }
        .btn { display: inline-block; padding: 8px 18px; border-radius: 6px; font-size: 14px; cursor: pointer; border: none; text-decoration: none; }
        .btn-primary { background: #ec407a; color: white; }
        .btn-primary:hover { background: #d81b60; }
        .btn-danger { background: #d93025; color: white; }
        .btn-danger:hover { background: #b3261e; }
        .btn-outline { background: transparent; color: #ec407a; border: 1px solid #ec407a; }
        .btn-outline:hover { background: #fce4ec; }
        .error { background: #fce8e6; color: #d93025; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
        .success { background: #e6f4ea; color: #1e8e3e; padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 4px; color: #555; }
        .form-group input, .form-group select { width: 100%; padding: 10px 12px; border: 1px solid #dadce0; border-radius: 6px; font-size: 14px; }
        .form-group input:focus, .form-group select:focus { outline: none; border-color: #f48fb1; box-shadow: 0 0 0 2px #fce4ec; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .stat { text-align: center; padding: 20px; }
        .stat .value { font-size: 28px; font-weight: 700; color: #c2185b; }
        .stat .label { font-size: 13px; color: #888; margin-top: 4px; }
        .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
        .badge-success { background: #e6f4ea; color: #1e8e3e; }
        .badge-warning { background: #fef7e0; color: #e37400; }
        .badge-info { background: #fce4ec; color: #c2185b; }
        .empty { text-align: center; color: #888; padding: 40px 0; font-size: 15px; }
        .actions { display: flex; gap: 8px; flex-wrap: wrap; }
        .meta { color: #888; font-size: 13px; margin-bottom: 16px; }
        .inline-form { display: inline; }
    </style>
</head>
<body>
    <nav>
        <div class="brand"><a href="/">Cloud Dashboard</a></div>
        <div>
            {% if session.get('user_id') %}
                <span style="font-size:14px;">{{ session.get('username') }}</span>
                <a href="/">Resources</a>
                <a href="/cost-summary">Costs</a>
                <a href="/deployments">Deployments</a>
                <a href="/logout">Logout</a>
            {% else %}
                <a href="/login">Login</a>
                <a href="/register">Register</a>
            {% endif %}
        </div>
    </nav>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

def api_get(path):
    headers = {}
    if session.get("user_id") and session.get("token"):
        headers["X-User-ID"] = str(session["user_id"])
        headers["X-Auth-Token"] = session["token"]
    try:
        resp = requests.get(f"{BACKEND_URL}{path}", headers=headers, timeout=5)
        return resp.json() if resp.status_code < 500 else {"error": "server error"}
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend"}
    except Exception as e:
        return {"error": str(e)}

def api_post(path, data):
    headers = {"Content-Type": "application/json"}
    if session.get("user_id") and session.get("token"):
        headers["X-User-ID"] = str(session["user_id"])
        headers["X-Auth-Token"] = session["token"]
    try:
        resp = requests.post(f"{BACKEND_URL}{path}", json=data, headers=headers, timeout=5)
        return resp.json(), resp.status_code
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend"}, 503
    except Exception as e:
        return {"error": str(e)}, 500

def api_delete(path):
    headers = {}
    if session.get("user_id") and session.get("token"):
        headers["X-User-ID"] = str(session["user_id"])
        headers["X-Auth-Token"] = session["token"]
    try:
        resp = requests.delete(f"{BACKEND_URL}{path}", headers=headers, timeout=5)
        return resp.json(), resp.status_code
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend"}, 503
    except Exception as e:
        return {"error": str(e)}, 500

def render_page(content, **kwargs):
    tmpl = BASE_TEMPLATE.replace("{% block content %}{% endblock %}", content)
    return render_template_string(tmpl, **kwargs)

@app.route("/")
def dashboard():
    if not session.get("user_id"):
        return redirect("/login")
    data = api_get("/api/resources")
    error = None
    resources = []
    if isinstance(data, list):
        resources = data
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    content = """
    <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <h1>Infrastructure Inventory</h1>
            <a href="/resources/add" class="btn btn-primary">+ Add Resource</a>
        </div>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        {% if resources %}
        <table>
            <tr><th>Name</th><th>Type</th><th>Region</th><th>Cost/hr</th><th>Status</th><th>Actions</th></tr>
            {% for r in resources %}
            <tr>
                <td>{{ r.name }}</td>
                <td><span class="badge badge-info">{{ r.type }}</span></td>
                <td>{{ r.region }}</td>
                <td>${{ "%.4f"|format(r.cost_per_hour) }}</td>
                <td><span class="badge badge-success">{{ r.status }}</span></td>
                <td>
                    <form class="inline-form" method="post" action="/resources/{{ r.id }}/delete" onsubmit="return confirm('Delete this resource?')">
                        <button class="btn btn-danger" style="padding:4px 12px;font-size:12px;">Delete</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <div class="empty">No resources yet. <a href="/resources/add">Add your first resource</a></div>
        {% endif %}
    </div>
    """
    return render_page(content, resources=resources, error=error)

@app.route("/resources/add", methods=["GET", "POST"])
def add_resource():
    if not session.get("user_id"):
        return redirect("/login")

    if request.method == "POST":
        data = {
            "name": request.form["name"],
            "type": request.form["type"],
            "region": request.form.get("region", "us-east-1"),
        }
        result, status = api_post("/api/resources", data)
        if status in (200, 201):
            return redirect("/")
        return render_page("""
        <div class="card">
            <h1>Add Resource</h1>
            <div class="error">{{ result.error }}</div>
            <a href="/resources/add" class="btn btn-outline">Try again</a>
        </div>
        """, result=result)

    content = """
    <div class="card">
        <h1>Add Cloud Resource</h1>
        <p class="meta">Create a new infrastructure resource to track in your dashboard.</p>
        <form method="post">
            <div class="form-group">
                <label>Resource Name</label>
                <input type="text" name="name" placeholder="e.g. prod-web-server" required>
            </div>
            <div class="form-group">
                <label>Resource Type</label>
                <select name="type" required>
                    <option value="">Select type...</option>
                    <option value="Virtual Machine">Virtual Machine</option>
                    <option value="Storage Account">Storage Account</option>
                    <option value="Load Balancer">Load Balancer</option>
                    <option value="Database">Database</option>
                    <option value="Kubernetes Cluster">Kubernetes Cluster</option>
                    <option value="Serverless Function">Serverless Function</option>
                    <option value="CDN Profile">CDN Profile</option>
                </select>
            </div>
            <div class="form-group">
                <label>Region</label>
                <select name="region">
                    <option value="us-east-1">US East (N. Virginia)</option>
                    <option value="us-west-2">US West (Oregon)</option>
                    <option value="eu-west-1">EU (Ireland)</option>
                    <option value="ap-southeast-1">Asia Pacific (Singapore)</option>
                </select>
            </div>
            <button type="submit" class="btn btn-primary">Create Resource</button>
            <a href="/" class="btn btn-outline">Cancel</a>
        </form>
    </div>
    """
    return render_page(content)

@app.route("/resources/<int:rid>/delete", methods=["POST"])
def delete_resource(rid):
    if not session.get("user_id"):
        return redirect("/login")
    api_delete(f"/api/resources/{rid}")
    return redirect("/")

@app.route("/cost-summary")
def cost_summary():
    if not session.get("user_id"):
        return redirect("/login")
    data = api_get("/api/cost-summary")
    error = None
    summary = {}
    if isinstance(data, dict) and "error" not in data:
        summary = data
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    content = """
    <div class="card">
        <h1>Cost Summary</h1>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        {% if summary and summary.total_hourly is defined %}
        <div class="grid-2">
            <div class="stat">
                <div class="value">${{ "%.2f"|format(summary.total_hourly) }}</div>
                <div class="label">Per Hour</div>
            </div>
            <div class="stat">
                <div class="value">${{ "%.2f"|format(summary.total_monthly) }}</div>
                <div class="label">Per Month (730h)</div>
            </div>
        </div>
        {% endif %}
    </div>

    {% if summary and summary.by_type %}
    <div class="card">
        <h2>Cost by Resource Type</h2>
        <table>
            <tr><th>Type</th><th>Count</th><th>Cost/hr</th><th>Cost/month</th></tr>
            {% for t in summary.by_type %}
            <tr>
                <td><span class="badge badge-info">{{ t.type }}</span></td>
                <td>{{ t.count }}</td>
                <td>${{ "%.4f"|format(t.total_hourly) }}</td>
                <td>${{ "%.2f"|format(t.total_monthly) }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    {% endif %}

    {% if summary and summary.resources %}
    <div class="card">
        <h2>Resource Breakdown</h2>
        <table>
            <tr><th>Name</th><th>Type</th><th>Cost/hr</th><th>Cost/month</th></tr>
            {% for r in summary.resources %}
            <tr>
                <td>{{ r.name }}</td>
                <td><span class="badge badge-info">{{ r.type }}</span></td>
                <td>${{ "%.4f"|format(r.cost_per_hour) }}</td>
                <td>${{ "%.2f"|format(r.monthly_cost) }}</td>
            </tr>
            {% endfor %}
        </table>
    </div>
    {% endif %}
    """
    return render_page(content, summary=summary, error=error)

@app.route("/deployments")
def deployments():
    if not session.get("user_id"):
        return redirect("/login")
    data = api_get("/api/deployments")
    error = None
    deploy_list = []
    if isinstance(data, list):
        deploy_list = data
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    content = """
    <div class="card">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
            <h1>Deployment History</h1>
            <a href="/deploy" class="btn btn-primary">+ New Deployment</a>
        </div>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        {% if deploy_list %}
        <table>
            <tr><th>ID</th><th>Resources</th><th>Status</th><th>Created</th><th>Completed</th></tr>
            {% for d in deploy_list %}
            <tr>
                <td>#{{ d.id }}</td>
                <td>{{ d.resource_ids|length }} resource(s)</td>
                <td>
                    {% if d.status == 'completed' %}
                    <span class="badge badge-success">{{ d.status }}</span>
                    {% elif d.status == 'in_progress' %}
                    <span class="badge badge-warning">{{ d.status }}</span>
                    {% else %}
                    <span class="badge badge-info">{{ d.status }}</span>
                    {% endif %}
                </td>
                <td>{{ d.created_at[:10] if d.created_at else '--' }}</td>
                <td>{{ d.completed_at[:10] if d.completed_at else '--' }}</td>
            </tr>
            {% endfor %}
        </table>
        {% else %}
        <div class="empty">No deployments yet. <a href="/deploy">Trigger a deployment</a></div>
        {% endif %}
    </div>
    """
    return render_page(content, deploy_list=deploy_list, error=error)

@app.route("/deploy", methods=["GET", "POST"])
def deploy():
    if not session.get("user_id"):
        return redirect("/login")

    resources_data = api_get("/api/resources")
    resource_list = resources_data if isinstance(resources_data, list) else []

    if request.method == "POST":
        selected = request.form.getlist("resource_ids")
        if not selected:
            return render_page("""
            <div class="card">
                <h1>Deploy Resources</h1>
                <div class="error">Select at least one resource.</div>
                <a href="/deploy" class="btn btn-outline">Try again</a>
            </div>
            """)
        ids = [int(x) for x in selected]
        result, status = api_post("/api/deployments", {"resource_ids": ids})
        if status in (200, 201):
            return redirect("/deployments")
        return render_page("""
        <div class="card">
            <h1>Deploy Resources</h1>
            <div class="error">{{ result.error }}</div>
            <a href="/deploy" class="btn btn-outline">Try again</a>
        </div>
        """, result=result)

    resource_rows = ""
    for r in resource_list:
        resource_rows += f"""
        <tr>
            <td><input type="checkbox" name="resource_ids" value="{r['id']}"></td>
            <td>{r['name']}</td>
            <td><span class="badge badge-info">{r['type']}</span></td>
            <td>{r['region']}</td>
            <td>${r['cost_per_hour']:.4f}/hr</td>
        </tr>"""

    content = f"""
    <div class="card">
        <h1>Trigger Infrastructure Deployment</h1>
        <p class="meta">Select resources to deploy. Deployment will complete in approximately 5 seconds (simulated).</p>
        <form method="post">
            {{% if resource_list %}}
            <table>
                <tr><th>Select</th><th>Name</th><th>Type</th><th>Region</th><th>Cost</th></tr>
                {resource_rows}
            </table>
            <br>
            <button type="submit" class="btn btn-primary">Deploy Selected</button>
            {{% else %}}
            <div class="empty">No resources available. <a href="/resources/add">Add resources first</a></div>
            {{% endif %}}
            <a href="/deployments" class="btn btn-outline">Cancel</a>
        </form>
    </div>
    """
    return render_page(content, resource_list=resource_list)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        result, status = api_post("/api/login", {
            "username": request.form["username"],
            "password": request.form["password"],
        })
        if status == 200 and "token" in result:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            session["token"] = result["token"]
            return redirect("/")
        error = result.get("error", "Login failed")
        content = """
        <div class="card" style="max-width:400px;margin:40px auto;">
            <h1>Login</h1>
            <div class="error">{{ error }}</div>
            <form method="post">
                <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
                <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
                <button type="submit" class="btn btn-primary" style="width:100%;">Sign In</button>
            </form>
            <p style="text-align:center;margin-top:12px;font-size:14px;">Don't have an account? <a href="/register">Register</a></p>
        </div>
        """
        return render_page(content, error=error)

    content = """
    <div class="card" style="max-width:400px;margin:40px auto;">
        <h1>Login</h1>
        <form method="post">
            <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
            <button type="submit" class="btn btn-primary" style="width:100%;">Sign In</button>
        </form>
        <p style="text-align:center;margin-top:12px;font-size:14px;">Don't have an account? <a href="/register">Register</a></p>
    </div>
    """
    return render_page(content)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if request.form["password"] != request.form.get("confirm_password", ""):
            content = """
            <div class="card" style="max-width:400px;margin:40px auto;">
                <h1>Register</h1>
                <div class="error">Passwords do not match</div>
                <a href="/register" class="btn btn-outline">Try again</a>
            </div>
            """
            return render_page(content)
        result, status = api_post("/api/register", {
            "username": request.form["username"],
            "password": request.form["password"],
        })
        if status in (200, 201) and "token" in result:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            session["token"] = result["token"]
            return redirect("/")
        error = result.get("error", "Registration failed")
        content = """
        <div class="card" style="max-width:400px;margin:40px auto;">
            <h1>Register</h1>
            <div class="error">{{ error }}</div>
            <form method="post">
                <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
                <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
                <div class="form-group"><label>Confirm Password</label><input type="password" name="confirm_password" required></div>
                <button type="submit" class="btn btn-primary" style="width:100%;">Create Account</button>
            </form>
            <p style="text-align:center;margin-top:12px;font-size:14px;">Already have an account? <a href="/login">Login</a></p>
        </div>
        """
        return render_page(content, error=error)

    content = """
    <div class="card" style="max-width:400px;margin:40px auto;">
        <h1>Register</h1>
        <form method="post">
            <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
            <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
            <div class="form-group"><label>Confirm Password</label><input type="password" name="confirm_password" required></div>
            <button type="submit" class="btn btn-primary" style="width:100%;">Create Account</button>
        </form>
        <p style="text-align:center;margin-top:12px;font-size:14px;">Already have an account? <a href="/login">Login</a></p>
    </div>
    """
    return render_page(content)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
