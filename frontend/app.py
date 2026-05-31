from flask import Flask, session, request, redirect, render_template_string, Response
import requests
import os
import csv
import io
import json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

BASE_TEMPLATE = """
<!DOCTYPE html>
<html data-theme="{{ 'dark' if session.get('dark_mode') else 'light' }}">
<head>
    <title>Cloud Cost & Infrastructure Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        :root {
            --bg: #f0f2f5; --card-bg: white; --text: #333; --text-light: #888; --border: #e0e0e0;
            --th-bg: #f8f9fa; --th-text: #555; --hover: #f1f3f4; --nav-bg: #f8bbd0; --nav-text: #880e4f;
            --primary: #ec407a; --primary-hover: #d81b60; --outline-hover: #fce4ec; --focus: #fce4ec;
            --danger: #d93025; --danger-hover: #b3261e; --success-bg: #e6f4ea; --success-text: #1e8e3e;
            --error-bg: #fce8e6; --error-text: #d93025; --warn-bg: #fef7e0; --warn-text: #e37400;
            --input-bg: white; --input-border: #dadce0; --tag-bg: #f3e8ff; --tag-text: #7c3aed;
            --filter-bg: #fce4ec;
        }
        [data-theme="dark"] {
            --bg: #1a1a2e; --card-bg: #16213e; --text: #e0e0e0; --text-light: #aaa; --border: #2a2a4a;
            --th-bg: #1e2a4a; --th-text: #ccc; --hover: #1e2a4a; --nav-bg: #2d1b3d; --nav-text: #f8bbd0;
            --primary: #f06292; --primary-hover: #ec407a; --outline-hover: #2d1b3d; --focus: #4a2040;
            --danger: #ef5350; --danger-hover: #e53935; --success-bg: #1b3a2b; --success-text: #81c784;
            --error-bg: #3a1b1b; --error-text: #ef9a9a; --warn-bg: #3a2e1b; --warn-text: #ffcc80;
            --input-bg: #1e2a4a; --input-border: #3a4a6a; --tag-bg: #2d1b3d; --tag-text: #f8bbd0;
            --filter-bg: #2d1b3d;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); transition: background .2s, color .2s; }
        nav { background: var(--nav-bg); color: var(--nav-text); padding: 14px 24px; display: flex; justify-content: space-between; align-items: center; }
        nav a { color: var(--nav-text); text-decoration: none; margin-left: 18px; font-size: 14px; }
        nav a:hover { text-decoration: underline; }
        nav .brand { font-weight: 700; font-size: 18px; }
        nav .brand a { margin: 0; }
        .theme-btn { background: none; border: 1px solid var(--nav-text); color: var(--nav-text); border-radius: 6px; padding: 4px 12px; cursor: pointer; font-size: 14px; margin-left: 12px; }
        .container { max-width: 1100px; margin: 24px auto; padding: 0 16px; }
        .card { background: var(--card-bg); border-radius: 8px; padding: 24px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: background .2s; }
        h1 { font-size: 24px; margin-bottom: 16px; color: var(--primary); }
        h2 { font-size: 18px; margin-bottom: 12px; color: var(--text-light); }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--border); font-size: 14px; }
        th { background: var(--th-bg); color: var(--th-text); font-weight: 600; }
        tr:hover { background: var(--hover); }
        .btn { display: inline-block; padding: 8px 18px; border-radius: 6px; font-size: 14px; cursor: pointer; border: none; text-decoration: none; }
        .btn-primary { background: var(--primary); color: white; }
        .btn-primary:hover { background: var(--primary-hover); }
        .btn-danger { background: var(--danger); color: white; }
        .btn-danger:hover { background: var(--danger-hover); }
        .btn-outline { background: transparent; color: var(--primary); border: 1px solid var(--primary); }
        .btn-outline:hover { background: var(--outline-hover); }
        .btn-sm { padding: 4px 12px; font-size: 12px; }
        .error { background: var(--error-bg); color: var(--error-text); padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
        .success { background: var(--success-bg); color: var(--success-text); padding: 12px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 14px; }
        .form-group { margin-bottom: 14px; }
        .form-group label { display: block; font-size: 14px; font-weight: 500; margin-bottom: 4px; color: var(--text-light); }
        .form-group input, .form-group select, .form-group textarea { width: 100%; padding: 10px 12px; border: 1px solid var(--input-border); border-radius: 6px; font-size: 14px; background: var(--input-bg); color: var(--text); }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 2px var(--focus); }
        .form-group textarea { resize: vertical; font-family: monospace; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        .stat { text-align: center; padding: 20px; }
        .stat .value { font-size: 28px; font-weight: 700; color: var(--primary); }
        .stat .label { font-size: 13px; color: var(--text-light); margin-top: 4px; }
        .badge { display: inline-block; padding: 3px 10px; border-radius: 12px; font-size: 12px; font-weight: 500; }
        .badge-success { background: var(--success-bg); color: var(--success-text); }
        .badge-warning { background: var(--warn-bg); color: var(--warn-text); }
        .badge-info { background: var(--filter-bg); color: var(--primary); }
        .tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; background: var(--tag-bg); color: var(--tag-text); margin: 1px 2px; }
        .empty { text-align: center; color: var(--text-light); padding: 40px 0; font-size: 15px; }
        .actions { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }
        .meta { color: var(--text-light); font-size: 13px; margin-bottom: 16px; }
        .inline-form { display: inline; }
        .filter-input { padding: 6px 12px; border: 1px solid var(--input-border); border-radius: 6px; font-size: 13px; background: var(--input-bg); color: var(--text); max-width: 200px; }
        .chart-wrap { max-width: 400px; margin: 0 auto; }
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
                <button class="theme-btn" onclick="fetch('/toggle-theme',{method:'POST'}).then(()=>location.reload())">{{ '☀️' if session.get('dark_mode') else '🌙' }}</button>
            {% else %}
                <a href="/login">Login</a>
                <a href="/register">Register</a>
            {% endif %}
        </div>
    </nav>
    <div class="container">
        {% block content %}{% endblock %}
    </div>
    <script>
        function filterTable(inputId, tableId) {
            var q = document.getElementById(inputId).value.toLowerCase();
            var rows = document.getElementById(tableId).querySelectorAll('tbody tr');
            rows.forEach(function(r) { r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none'; });
        }
    </script>
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

def api_put(path, data):
    headers = {"Content-Type": "application/json"}
    if session.get("user_id") and session.get("token"):
        headers["X-User-ID"] = str(session["user_id"])
        headers["X-Auth-Token"] = session["token"]
    try:
        resp = requests.put(f"{BACKEND_URL}{path}", json=data, headers=headers, timeout=5)
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

def tags_html(tags):
    if not tags:
        return ""
    return " ".join(f'<span class="tag">{k}:{v}</span>' for k, v in sorted(tags.items()))

DASHBOARD_TEMPLATE = """
<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px;">
        <h1>Infrastructure Inventory</h1>
        <div class="actions">
            <input class="filter-input" id="filterInput" placeholder="Search..." oninput="filterTable('filterInput','resourceTable')">
            <a href="/resources/add" class="btn btn-primary">+ Add</a>
            <a href="/export/csv/resources" class="btn btn-outline">CSV</a>
        </div>
    </div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if resources %}
    <table id="resourceTable">
        <thead><tr><th>Name</th><th>Type</th><th>Region</th><th>Cost/hr</th><th>Tags</th><th>Status</th><th>Actions</th></tr></thead>
        <tbody>
            {% for r in resources %}
            <tr>
                <td>{{ r.name }}</td>
                <td><span class="badge badge-info">{{ r.type }}</span></td>
                <td>{{ r.region }}</td>
                <td>${{ "%.4f"|format(r.cost_per_hour) }}</td>
                <td>{{ r.tags_html|safe }}</td>
                <td><span class="badge badge-success">{{ r.status }}</span></td>
                <td class="actions">
                    <a href="/resources/{{ r.id }}/edit" class="btn btn-outline btn-sm">Edit</a>
                    <form class="inline-form" method="post" action="/resources/{{ r.id }}/delete" onsubmit="return confirm('Delete this resource?')">
                        <button class="btn btn-danger btn-sm">Del</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty">No resources yet. <a href="/resources/add">Add your first resource</a></div>
    {% endif %}
</div>
"""

@app.route("/")
def dashboard():
    if not session.get("user_id"):
        return redirect("/login")
    data = api_get("/api/resources")
    error = None
    resources = []
    if isinstance(data, list):
        for r in data:
            r["tags_html"] = tags_html(r.get("tags"))
        resources = data
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]
    return render_page(DASHBOARD_TEMPLATE, resources=resources, error=error)

def resource_form_html(method, action, values=None, error=None):
    name = values.get("name", "") if values else ""
    rtype = values.get("type", "") if values else ""
    region = values.get("region", "us-east-1") if values else "us-east-1"
    status = values.get("status", "running") if values else "running"
    tags_val = ""
    if values and values.get("tags"):
        if isinstance(values["tags"], dict):
            tags_val = "\n".join(f"{k}:{v}" for k, v in values["tags"].items())
        else:
            tags_val = values["tags"]
    title = "Edit Resource" if method == "PUT" else "Add Cloud Resource"
    submit_label = "Update Resource" if method == "PUT" else "Create Resource"
    types = ["Virtual Machine", "Storage Account", "Load Balancer", "Database", "Kubernetes Cluster", "Serverless Function", "CDN Profile"]
    types_opts = "".join(f'<option value="{t}"{" selected" if t == rtype else ""}>{t}</option>' for t in types)
    regions_list = [("us-east-1", "US East (N. Virginia)"), ("us-west-2", "US West (Oregon)"), ("eu-west-1", "EU (Ireland)"), ("ap-southeast-1", "Asia Pacific (Singapore)")]
    regions_opts = "".join(f'<option value="{v}"{" selected" if v == region else ""}>{l}</option>' for v, l in regions_list)
    statuses = ["running", "stopped", "terminated"]
    status_opts = "".join(f'<option value="{s}"{" selected" if s == status else ""}>{s}</option>' for s in statuses)
    error_html = f'<div class="error">{error}</div>' if error else ""
    return f"""<div class="card"><h1>{title}</h1><p class="meta">Tags format: one per line as key:value</p>{error_html}<form method="post"><div class="form-group"><label>Name</label><input type="text" name="name" value="{name}" required></div><div class="form-group"><label>Type</label><select name="type" required>{types_opts}</select></div><div class="form-group"><label>Region</label><select name="region">{regions_opts}</select></div><div class="form-group"><label>Status</label><select name="status">{status_opts}</select></div><div class="form-group"><label>Tags (key:value per line)</label><textarea name="tags" rows="4">{tags_val}</textarea></div><button type="submit" class="btn btn-primary">{submit_label}</button><a href="/" class="btn btn-outline">Cancel</a></form></div>"""

def parse_tags(form):
    tags = {}
    for line in form.get("tags", "").strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            tags[k.strip()] = v.strip()
    return tags

@app.route("/resources/add", methods=["GET", "POST"])
def add_resource():
    if not session.get("user_id"):
        return redirect("/login")
    if request.method == "POST":
        data = {"name": request.form["name"], "type": request.form["type"], "region": request.form.get("region", "us-east-1"), "status": request.form.get("status", "running")}
        tags = parse_tags(request.form)
        if tags:
            data["tags"] = tags
        result, status = api_post("/api/resources", data)
        if status in (200, 201):
            return redirect("/")
        return render_page(resource_form_html("POST", "/resources/add", request.form, result.get("error", "Failed")))
    return render_page(resource_form_html("POST", "/resources/add"))

@app.route("/resources/<int:rid>/edit", methods=["GET", "POST"])
def edit_resource(rid):
    if not session.get("user_id"):
        return redirect("/login")
    if request.method == "POST":
        data = {"name": request.form["name"], "type": request.form["type"], "region": request.form.get("region", "us-east-1"), "status": request.form.get("status", "running")}
        tags = parse_tags(request.form)
        if tags:
            data["tags"] = tags
        result, status = api_put(f"/api/resources/{rid}", data)
        if status in (200, 201):
            return redirect("/")
        return render_page(resource_form_html("PUT", f"/resources/{rid}/edit", request.form, result.get("error", "Failed")))
    data = api_get("/api/resources")
    resource = next((r for r in data if r["id"] == rid), None) if isinstance(data, list) else None
    if not resource:
        return redirect("/")
    return render_page(resource_form_html("PUT", f"/resources/{rid}/edit", resource))

@app.route("/resources/<int:rid>/delete", methods=["POST"])
def delete_resource(rid):
    if not session.get("user_id"):
        return redirect("/login")
    api_delete(f"/api/resources/{rid}")
    return redirect("/")

COST_TEMPLATE = """
<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h1>Cost Summary</h1>
        <a href="/export/csv/costs" class="btn btn-outline">CSV</a>
    </div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if summary and summary.total_hourly is defined %}
    <div class="grid-2">
        <div class="stat"><div class="value">${{ "%.2f"|format(summary.total_hourly) }}</div><div class="label">Per Hour</div></div>
        <div class="stat"><div class="value">${{ "%.2f"|format(summary.total_monthly) }}</div><div class="label">Per Month (730h)</div></div>
    </div>
    {% endif %}
</div>
{% if summary and summary.by_type %}
<div class="card">
    <h2>Cost by Resource Type</h2>
    <div class="grid-2">
        <div class="chart-wrap"><canvas id="pieChart"></canvas></div>
        <div class="chart-wrap"><canvas id="barChart"></canvas></div>
    </div>
    <br>
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
<script>
{% if summary and summary.by_type %}
(function() {
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    var tc = isDark ? '#e0e0e0' : '#555';
    var byType = {{ by_type_json|safe }};
    new Chart(document.getElementById('pieChart'), {
        type: 'pie',
        data: { labels: byType.map(function(t){return t.type;}), datasets: [{ data: byType.map(function(t){return t.total_monthly;}), backgroundColor: ['#ec407a','#f48fb1','#ce93d8','#ba68c8','#e040fb','#ea80fc','#f8bbd0'] }] },
        options: { plugins: { legend: { labels: { color: tc } } } }
    });
    new Chart(document.getElementById('barChart'), {
        type: 'bar',
        data: { labels: byType.map(function(t){return t.type;}), datasets: [{ label: 'Monthly Cost', data: byType.map(function(t){return t.total_monthly;}), backgroundColor: '#ec407a' }] },
        options: { scales: { y: { beginAtZero: true, ticks: { color: tc } }, x: { ticks: { color: tc } } }, plugins: { legend: { display: false } } }
    });
})();
{% endif %}
</script>
"""

@app.route("/cost-summary")
def cost_summary():
    if not session.get("user_id"):
        return redirect("/login")
    data = api_get("/api/cost-summary")
    error = None
    summary = {}
    by_type_json = "[]"
    if isinstance(data, dict) and "error" not in data:
        summary = data
        by_type_json = json.dumps(data.get("by_type", []))
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]
    return render_page(COST_TEMPLATE, summary=summary, error=error, by_type_json=by_type_json)

DEPLOY_TEMPLATE = """
<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h1>Deployment History</h1>
        <a href="/deploy" class="btn btn-primary">+ New Deployment</a>
    </div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if deploy_list %}
    <table><thead><tr><th>ID</th><th>Resources</th><th>Status</th><th>Created</th><th>Completed</th></tr></thead>
        <tbody>
        {% for d in deploy_list %}
        <tr>
            <td>#{{ d.id }}</td>
            <td>{{ d.resource_ids|length }} resource(s)</td>
            <td>{% if d.status == 'completed' %}<span class="badge badge-success">{{ d.status }}</span>{% elif d.status == 'in_progress' %}<span class="badge badge-warning">{{ d.status }}</span>{% else %}<span class="badge badge-info">{{ d.status }}</span>{% endif %}</td>
            <td>{{ d.created_at[:10] if d.created_at else '--' }}</td>
            <td>{{ d.completed_at[:10] if d.completed_at else '--' }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty">No deployments yet. <a href="/deploy">Trigger a deployment</a></div>
    {% endif %}
</div>
"""

DEPLOY_FORM_TEMPLATE = """
<div class="card">
    <h1>Trigger Infrastructure Deployment</h1>
    <p class="meta">Select resources to deploy. Deployment simulates a 5-second provisioning.</p>
    <form method="post">
        {% if resource_list %}
        <table><tr><th>Select</th><th>Name</th><th>Type</th><th>Region</th><th>Tags</th><th>Cost</th></tr>
            {% for r in resource_list %}
            <tr>
                <td><input type="checkbox" name="resource_ids" value="{{ r.id }}"></td>
                <td>{{ r.name }}</td>
                <td><span class="badge badge-info">{{ r.type }}</span></td>
                <td>{{ r.region }}</td>
                <td>{{ r.tags_html|safe }}</td>
                <td>${{ "%.4f"|format(r.cost_per_hour) }}/hr</td>
            </tr>
            {% endfor %}
        </table>
        <br><button type="submit" class="btn btn-primary">Deploy Selected</button>
        {% else %}
        <div class="empty">No resources available. <a href="/resources/add">Add resources first</a></div>
        {% endif %}
        <a href="/deployments" class="btn btn-outline">Cancel</a>
    </form>
</div>
"""

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
    return render_page(DEPLOY_TEMPLATE, deploy_list=deploy_list, error=error)

@app.route("/deploy", methods=["GET", "POST"])
def deploy():
    if not session.get("user_id"):
        return redirect("/login")
    if request.method == "POST":
        selected = request.form.getlist("resource_ids")
        if not selected:
            return render_page("""<div class="card"><h1>Deploy Resources</h1><div class="error">Select at least one resource.</div><a href="/deploy" class="btn btn-outline">Try again</a></div>""")
        ids = [int(x) for x in selected]
        result, status = api_post("/api/deployments", {"resource_ids": ids})
        if status in (200, 201):
            return redirect("/deployments")
        return render_page("""<div class="card"><h1>Deploy Resources</h1><div class="error">{{ result.error }}</div><a href="/deploy" class="btn btn-outline">Try again</a></div>""", result=result)
    resources_data = api_get("/api/resources")
    resource_list = resources_data if isinstance(resources_data, list) else []
    for r in resource_list:
        r["tags_html"] = tags_html(r.get("tags"))
    return render_page(DEPLOY_FORM_TEMPLATE, resource_list=resource_list)

LOGIN_TEMPLATE = """
<div class="card" style="max-width:400px;margin:40px auto;">
    <h1>Login</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
        <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
        <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
        <button type="submit" class="btn btn-primary" style="width:100%;">Sign In</button>
    </form>
    <p style="text-align:center;margin-top:12px;font-size:14px;">Don't have an account? <a href="/register">Register</a></p>
</div>
"""

REGISTER_TEMPLATE = """
<div class="card" style="max-width:400px;margin:40px auto;">
    <h1>Register</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
        <div class="form-group"><label>Username</label><input type="text" name="username" required></div>
        <div class="form-group"><label>Password</label><input type="password" name="password" required></div>
        <div class="form-group"><label>Confirm Password</label><input type="password" name="confirm_password" required></div>
        <button type="submit" class="btn btn-primary" style="width:100%;">Create Account</button>
    </form>
    <p style="text-align:center;margin-top:12px;font-size:14px;">Already have an account? <a href="/login">Login</a></p>
</div>
"""

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        result, status = api_post("/api/login", {"username": request.form["username"], "password": request.form["password"]})
        if status == 200 and "token" in result:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            session["token"] = result["token"]
            return redirect("/")
        return render_page(LOGIN_TEMPLATE, error=result.get("error", "Login failed"))
    return render_page(LOGIN_TEMPLATE)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        if request.form["password"] != request.form.get("confirm_password", ""):
            return render_page(REGISTER_TEMPLATE, error="Passwords do not match")
        result, status = api_post("/api/register", {"username": request.form["username"], "password": request.form["password"]})
        if status in (200, 201) and "token" in result:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            session["token"] = result["token"]
            return redirect("/")
        return render_page(REGISTER_TEMPLATE, error=result.get("error", "Registration failed"))
    return render_page(REGISTER_TEMPLATE)

@app.route("/toggle-theme", methods=["POST"])
def toggle_theme():
    session["dark_mode"] = not session.get("dark_mode", False)
    return ("", 204)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

@app.route("/export/csv/resources")
def export_resources_csv():
    if not session.get("user_id"):
        return redirect("/login")
    data = api_get("/api/resources")
    resources = data if isinstance(data, list) else []
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["Name", "Type", "Region", "CostPerHour", "Status", "Tags"])
    for r in resources:
        tags = "; ".join(f"{k}:{v}" for k, v in r.get("tags", {}).items()) if r.get("tags") else ""
        w.writerow([r["name"], r["type"], r["region"], r["cost_per_hour"], r["status"], tags])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=resources.csv"})

@app.route("/export/csv/costs")
def export_costs_csv():
    if not session.get("user_id"):
        return redirect("/login")
    data = api_get("/api/cost-summary")
    summary = data if isinstance(data, dict) and "error" not in data else {}
    output = io.StringIO()
    w = csv.writer(output)
    w.writerow(["Name", "Type", "CostPerHour", "MonthlyCost"])
    for r in summary.get("resources", []):
        w.writerow([r["name"], r["type"], r["cost_per_hour"], r.get("monthly_cost", 0)])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=costs.csv"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
