from flask import Flask, session, request, redirect, render_template_string, Response
import requests
import os
import csv
import io
import json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

COST_PER_HOUR_BY_TYPE = {
    "Virtual Machine": 0.0860,
    "Storage Account": 0.0180,
    "Load Balancer": 0.0250,
    "Database": 0.0150,
    "Kubernetes Cluster": 0.1000,
    "Serverless Function": 0.0000,
    "CDN Profile": 0.0100,
}

RESOURCE_TYPE_ICONS = {
    "Virtual Machine": "🖥️",
    "Kubernetes Cluster": "⎈",
    "Load Balancer": "⚖️",
    "Storage Account": "💾",
    "Database": "🗄️",
    "CDN Profile": "🌐",
    "Serverless Function": "⚡",
}

RESOURCE_TYPES = [
    "Virtual Machine", "Storage Account", "Load Balancer",
    "Database", "Kubernetes Cluster", "Serverless Function", "CDN Profile",
]

REGIONS = [
    ("us-east-1", "US East (N. Virginia)"),
    ("us-west-2", "US West (Oregon)"),
    ("eu-west-1", "EU (Ireland)"),
    ("ap-southeast-1", "Asia Pacific (Singapore)"),
]

STATUSES = ["running", "stopped", "terminated"]

DEFAULT_BUDGET = 200
HOURS_PER_MONTH = 730

LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <title>Cloud Infrastructure Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        :root {
            --bg: #090d14;
            --sidebar-bg: #0e1419;
            --card-bg: #111922;
            --card-border: #1e2a36;
            --text: #e1e7ef;
            --text-muted: #8892a6;
            --text-dim: #4a5568;
            --primary: #7c6ff7;
            --primary-hover: #6a5cf0;
            --primary-glow: rgba(124,111,247,0.15);
            --success: #4ade80;
            --success-bg: rgba(74,222,128,0.12);
            --warning: #fbbf24;
            --warning-bg: rgba(251,191,36,0.12);
            --danger: #f87171;
            --danger-bg: rgba(248,113,113,0.12);
            --info: #38bdf8;
            --tag-bg: rgba(124,111,247,0.15);
            --tag-text: #a78bfa;
            --input-bg: #0e1419;
            --input-border: #1e2a36;
            --focus-ring: rgba(124,111,247,0.3);
            --font-mono: 'SF Mono','Fira Code','Cascadia Code',monospace;
            --font-sans: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        }
        * { box-sizing:border-box; margin:0; padding:0; }
        body { font-family:var(--font-sans); background:var(--bg); color:var(--text); min-height:100vh; }
        .layout { display:flex; min-height:100vh; }
        .sidebar { width:220px; background:var(--sidebar-bg); border-right:1px solid var(--card-border); display:flex; flex-direction:column; position:fixed; top:0; left:0; bottom:0; z-index:10; }
        .sidebar-brand { padding:20px 18px 16px; font-weight:700; font-size:15px; letter-spacing:-0.3px; color:var(--primary); border-bottom:1px solid var(--card-border); display:flex; align-items:center; gap:8px; }
        .sidebar-brand svg { flex-shrink:0; }
        .sidebar-nav { flex:1; padding:12px 8px; display:flex; flex-direction:column; gap:2px; }
        .sidebar-nav a { display:flex; align-items:center; gap:10px; padding:9px 12px; border-radius:6px; font-size:14px; color:var(--text-muted); text-decoration:none; transition:all .15s; font-weight:500; }
        .sidebar-nav a:hover { background:rgba(255,255,255,0.04); color:var(--text); }
        .sidebar-nav a.active { background:var(--primary-glow); color:var(--primary); }
        .sidebar-nav a .nav-icon { width:18px; text-align:center; font-size:15px; }
        .sidebar-footer { padding:12px 8px; border-top:1px solid var(--card-border); }
        .sidebar-footer .user-info { display:flex; align-items:center; gap:8px; padding:8px 12px; border-radius:6px; font-size:13px; color:var(--text-muted); }
        .sidebar-footer .user-info .avatar { width:24px; height:24px; border-radius:50%; background:var(--primary); color:#fff; display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:600; }
        .sidebar-footer a { display:block; padding:8px 12px; border-radius:6px; font-size:13px; color:var(--danger); text-decoration:none; margin-top:2px; }
        .sidebar-footer a:hover { background:var(--danger-bg); }
        .main { margin-left:220px; flex:1; min-height:100vh; }
        .content { padding:24px 28px; }
        .auth-wrap { max-width:420px; margin:80px auto; padding:0 16px; }
        .card { background:var(--card-bg); border:1px solid var(--card-border); border-radius:10px; padding:24px; margin-bottom:20px; }
        h1 { font-size:22px; font-weight:600; margin-bottom:16px; letter-spacing:-0.3px; }
        h2 { font-size:15px; font-weight:600; color:var(--text-muted); margin-bottom:14px; letter-spacing:0.3px; text-transform:uppercase; }
        table { width:100%; border-collapse:collapse; }
        th { padding:10px 14px; text-align:left; font-size:11px; font-weight:600; color:var(--text-dim); text-transform:uppercase; letter-spacing:0.5px; border-bottom:1px solid var(--card-border); background:transparent; }
        td { padding:12px 14px; border-bottom:1px solid var(--card-border); font-size:13px; }
        tbody tr { transition:background .12s; }
        tbody tr:hover { background:rgba(255,255,255,0.02); }
        tbody tr:last-child td { border-bottom:none; }
        .btn { display:inline-flex; align-items:center; gap:6px; padding:8px 16px; border-radius:6px; font-size:13px; font-weight:500; cursor:pointer; border:none; text-decoration:none; transition:all .15s; }
        .btn-primary { background:var(--primary); color:#fff; }
        .btn-primary:hover { background:var(--primary-hover); box-shadow:0 0 16px var(--primary-glow); }
        .btn-danger { background:var(--danger-bg); color:var(--danger); }
        .btn-danger:hover { background:rgba(248,113,113,0.2); }
        .btn-outline { background:transparent; color:var(--text-muted); border:1px solid var(--card-border); }
        .btn-outline:hover { border-color:var(--primary); color:var(--primary); }
        .btn-sm { padding:5px 10px; font-size:12px; }
        .btn-ghost { background:transparent; color:var(--text-dim); padding:5px 8px; border-radius:4px; font-size:13px; }
        .btn-ghost:hover { background:rgba(255,255,255,0.05); color:var(--text); }
        .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        .grid-4 { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
        .stat-card { text-align:left; padding:18px 20px; border-radius:10px; border:1px solid var(--card-border); background:var(--card-bg); position:relative; overflow:hidden; }
        .stat-card .stat-icon { font-size:22px; margin-bottom:10px; }
        .stat-card .stat-value { font-size:24px; font-weight:700; letter-spacing:-0.5px; font-family:var(--font-mono); }
        .stat-card .stat-label { font-size:12px; color:var(--text-muted); margin-top:2px; font-weight:500; text-transform:uppercase; letter-spacing:0.3px; }
        .stat-card .stat-sub { font-size:11px; color:var(--text-dim); margin-top:4px; font-family:var(--font-mono); }
        .stat-card.g1 .stat-value { color:#a78bfa; }
        .stat-card.g2 .stat-value { color:#4ade80; }
        .stat-card.g3 .stat-value { color:#fbbf24; }
        .stat-card.g4 .stat-value { color:#38bdf8; }
        .stat-card::after { content:''; position:absolute; top:0; right:0; width:80px; height:80px; border-radius:50%; opacity:0.06; transform:translate(30%,-30%); }
        .stat-card.g1::after { background:#a78bfa; }
        .stat-card.g2::after { background:#4ade80; }
        .stat-card.g3::after { background:#fbbf24; }
        .stat-card.g4::after { background:#38bdf8; }
        .chart-row { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
        .chart-box { text-align:center; padding:8px 0; }
        .chart-box canvas { max-height:220px; margin:0 auto; }
        .chart-wrap { max-width:360px; margin:0 auto; }
        .badge { display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; letter-spacing:0.2px; }
        .badge-success { background:rgba(74,222,128,0.12); color:#4ade80; }
        .badge-warning { background:rgba(251,191,36,0.12); color:#fbbf24; }
        .badge-danger { background:rgba(248,113,113,0.12); color:#f87171; }
        .badge-info { background:rgba(124,111,247,0.15); color:#38bdf8; }
        .badge-neutral { background:rgba(255,255,255,0.04); color:#8892a6; }
        .tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-family:var(--font-mono); background:rgba(124,111,247,0.15); color:#a78bfa; margin:1px 2px; }
        .status-dot { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:6px; vertical-align:middle; }
        .status-dot.running, .status-dot.completed { background:#4ade80; box-shadow:0 0 6px rgba(74,222,128,0.5); }
        .status-dot.stopped, .status-dot.in_progress { background:#fbbf24; box-shadow:0 0 6px rgba(251,191,36,0.4); }
        .status-dot.terminated, .status-dot.failed { background:#f87171; }
        .filter-pills { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; }
        .filter-pill { padding:4px 12px; border-radius:20px; font-size:12px; font-weight:500; cursor:pointer; border:1px solid var(--card-border); background:transparent; color:var(--text-muted); transition:all .15s; font-family:var(--font-sans); }
        .filter-pill:hover { border-color:var(--primary); color:var(--primary); }
        .filter-pill.active { background:var(--primary-glow); border-color:var(--primary); color:var(--primary); }
        .progress-bar { height:6px; background:rgba(255,255,255,0.06); border-radius:3px; overflow:hidden; margin-top:8px; }
        .progress-bar .fill { height:100%; border-radius:3px; transition:width .4s; }
        .progress-bar .fill.safe { background:var(--success); }
        .progress-bar .fill.warn { background:var(--warning); }
        .progress-bar .fill.danger { background:var(--danger); }
        .budget-input { background:transparent; border:1px solid var(--card-border); color:var(--text); padding:4px 8px; border-radius:4px; font-size:12px; font-family:var(--font-mono); width:80px; text-align:center; outline:none; }
        .budget-input:focus { border-color:var(--primary); }
        .filter-input { padding:7px 12px; border:1px solid var(--input-border); border-radius:6px; font-size:13px; background:var(--input-bg); color:var(--text); font-family:var(--font-mono); width:200px; outline:none; transition:border-color .15s; }
        .filter-input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
        .filter-input::placeholder { color:var(--text-dim); }
        .actions { display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
        .actions .btn-ghost { opacity:0; transition:opacity .12s; }
        tbody tr:hover .actions .btn-ghost { opacity:1; }
        .empty { text-align:center; color:var(--text-muted); padding:48px 0; font-size:14px; }
        .empty a { color:var(--primary); text-decoration:none; }
        .empty a:hover { text-decoration:underline; }
        .error { background:var(--danger-bg); color:var(--danger); padding:12px 16px; border-radius:6px; margin-bottom:16px; font-size:13px; border:1px solid rgba(248,113,113,0.15); }
        .form-group { margin-bottom:14px; }
        .form-group label { display:block; font-size:12px; font-weight:600; margin-bottom:5px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.3px; }
        .form-group input, .form-group select, .form-group textarea { width:100%; padding:9px 12px; border:1px solid var(--input-border); border-radius:6px; font-size:13px; background:var(--input-bg); color:var(--text); outline:none; font-family:var(--font-mono); transition:border-color .15s; }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
        .section-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
        .section-header h1 { margin-bottom:0; }
        .resource-name { font-weight:500; }
        .resource-meta { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); margin-top:2px; }
        .age { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); }
        .meta { color:var(--text-dim); font-size:12px; margin-bottom:16px; font-family:var(--font-mono); }
        .mono { font-family:var(--font-mono); font-size:13px; }
        .inline-form { display:inline; }
        .panel-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:50; opacity:0; pointer-events:none; transition:opacity .2s; }
        .panel-overlay.open { opacity:1; pointer-events:auto; }
        .slide-panel { position:fixed; top:0; right:0; bottom:0; width:480px; max-width:90vw; background:var(--card-bg); border-left:1px solid var(--card-border); z-index:51; transform:translateX(100%); transition:transform .25s; overflow-y:auto; padding:24px; }
        .slide-panel.open { transform:translateX(0); }
        .slide-panel .close-btn { float:right; background:none; border:none; color:var(--text-dim); font-size:20px; cursor:pointer; padding:4px 8px; border-radius:4px; }
        .slide-panel .close-btn:hover { color:var(--text); background:rgba(255,255,255,0.05); }
        .slide-panel h1 { font-size:18px; margin-bottom:4px; }
        .slide-panel .panel-meta { color:var(--text-dim); font-size:12px; font-family:var(--font-mono); margin-bottom:16px; }
        .slide-panel .panel-section { margin-bottom:16px; }
        .slide-panel .panel-section h2 { font-size:11px; margin-bottom:8px; }
        .slide-panel .prop-row { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid var(--card-border); font-size:13px; }
        .slide-panel .prop-row .prop-label { color:var(--text-muted); }
        .slide-panel .prop-row .prop-value { font-family:var(--font-mono); color:var(--text); }
        @media (max-width:900px) {
            .sidebar { width:56px; }
            .sidebar-brand span, .sidebar-nav a span, .sidebar-footer .user-info span, .sidebar-footer a span { display:none; }
            .sidebar-nav a { justify-content:center; padding:9px; }
            .sidebar-footer .user-info { justify-content:center; }
            .main { margin-left:56px; }
            .grid-4 { grid-template-columns:repeat(2,1fr); }
            .chart-row { grid-template-columns:1fr; }
        }
        @media (max-width:600px) {
            .content { padding:16px; }
            .grid-4 { grid-template-columns:1fr; }
        }
    </style>
</head>
<body>
{% if session.get('user_id') %}
<div class="layout">
    <aside class="sidebar">
        <div class="sidebar-brand">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            <span>CloudDash</span>
        </div>
        <nav class="sidebar-nav">
            <a href="/"
               class="{{ 'active' if request.path == '/' else '' }}">
                <span class="nav-icon">⎔</span><span>Resources</span>
            </a>
            <a href="/cost-summary"
               class="{{ 'active' if request.path == '/cost-summary' else '' }}">
                <span class="nav-icon">$</span><span>Costs</span>
            </a>
            <a href="/deployments"
               class="{{ 'active' if request.path == '/deployments' else '' }}">
                <span class="nav-icon">⇪</span><span>Deployments</span>
            </a>
        </nav>
        <div class="sidebar-footer">
            <div class="user-info">
                <div class="avatar">{{ session.get('username','U')[:1].upper() }}</div>
                <span>{{ session.get('username') }}</span>
            </div>
            <a href="/logout"><span>⏻</span> <span>Logout</span></a>
        </div>
    </aside>
    <main class="main">
        <div class="content">
            {% block content %}{% endblock %}
        </div>
    </main>
</div>
{% else %}
<div class="auth-wrap">
    {% block content %}{% endblock %}
</div>
{% endif %}
<script>
function filterTable(inputId, tableId) {
    var query = document.getElementById(inputId).value.toLowerCase();
    var rows = document.getElementById(tableId).querySelectorAll('tbody tr');
    rows.forEach(function(row) {
        var text = row.textContent.toLowerCase();
        row.style.display = text.includes(query) ? '' : 'none';
    });
}

function timeAgo(isoString) {
    if (!isoString) return '\u2014';
    var date = new Date(isoString.replace('Z', '+00:00'));
    var seconds = Math.floor((Date.now() - date) / 1000);
    if (seconds < 60) return seconds + 's ago';
    var minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + 'm ago';
    var hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + 'h ago';
    var days = Math.floor(hours / 24);
    if (days < 30) return days + 'd ago';
    return Math.floor(days / 30) + 'mo ago';
}

function renderAges() {
    document.querySelectorAll('[data-age]').forEach(function(el) {
        el.textContent = timeAgo(el.getAttribute('data-age'));
    });
}
document.addEventListener('DOMContentLoaded', renderAges);
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
        response = requests.get(f"{BACKEND_URL}{path}", headers=headers, timeout=5)
        if response.status_code < 500:
            return response.json()
        return {"error": "server error"}
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
        response = requests.post(f"{BACKEND_URL}{path}", json=data, headers=headers, timeout=5)
        return response.json(), response.status_code
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
        response = requests.put(f"{BACKEND_URL}{path}", json=data, headers=headers, timeout=5)
        return response.json(), response.status_code
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
        response = requests.delete(f"{BACKEND_URL}{path}", headers=headers, timeout=5)
        return response.json(), response.status_code
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend"}, 503
    except Exception as e:
        return {"error": str(e)}, 500


def render_page(content, **context):
    html = LAYOUT.replace("{% block content %}{% endblock %}", content)
    return render_template_string(html, **context)


def format_tags(tags):
    if not tags:
        return ""
    return " ".join(
        f'<span class="tag">{key}:{value}</span>'
        for key, value in sorted(tags.items())
    )


def derive_health(status):
    if status == "running":
        return "healthy"
    elif status == "stopped":
        return "degraded"
    return "offline"


def status_badge_class(status):
    if status in ("running", "healthy", "completed"):
        return "success"
    elif status in ("stopped", "degraded", "in_progress"):
        return "warning"
    return "danger"


def resource_form_html(method, action, values=None, error=None):
    name = values.get("name", "") if values else ""
    resource_type = values.get("type", "") if values else ""
    region = values.get("region", "us-east-1") if values else "us-east-1"
    status = values.get("status", "running") if values else "running"

    tags_text = ""
    if values and values.get("tags"):
        if isinstance(values["tags"], dict):
            tags_text = "\n".join(f"{k}:{v}" for k, v in values["tags"].items())
        else:
            tags_text = values["tags"]

    is_edit = method == "PUT"
    title = "Edit Resource" if is_edit else "Add Cloud Resource"
    submit_label = "Update Resource" if is_edit else "Create Resource"

    type_options = "".join(
        f'<option value="{t}"{" selected" if t == resource_type else ""}>{t}</option>'
        for t in RESOURCE_TYPES
    )
    region_options = "".join(
        f'<option value="{v}"{" selected" if v == region else ""}>{l}</option>'
        for v, l in REGIONS
    )
    status_options = "".join(
        f'<option value="{s}"{" selected" if s == status else ""}>{s}</option>'
        for s in STATUSES
    )

    error_html = f'<div class="error">{error}</div>' if error else ""

    return f"""<div class="card">
  <h1>{title}</h1>
  <p class="meta">Tags format: one per line as key:value</p>
  {error_html}
  <form method="post">
    <div class="form-group">
      <label>Name</label>
      <input type="text" name="name" value="{name}" required>
    </div>
    <div class="form-group">
      <label>Type</label>
      <select name="type" required>{type_options}</select>
    </div>
    <div class="form-group">
      <label>Region</label>
      <select name="region">{region_options}</select>
    </div>
    <div class="form-group">
      <label>Status</label>
      <select name="status">{status_options}</select>
    </div>
    <div class="form-group">
      <label>Tags (key:value per line)</label>
      <textarea name="tags" rows="4">{tags_text}</textarea>
    </div>
    <button type="submit" class="btn btn-primary">{submit_label}</button>
    <a href="/" class="btn btn-outline">Cancel</a>
  </form>
</div>"""


def parse_tags(form):
    tags = {}
    for line in form.get("tags", "").strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            tags[key.strip()] = value.strip()
    return tags


def cost_percentage(pct):
    if pct < 70:
        return "safe"
    elif pct < 90:
        return "warn"
    return "danger"


DASHBOARD_PAGE = """
<div class="grid-4">
    <div class="stat-card g1">
        <div class="stat-icon">🖥️</div>
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">Total Resources</div>
    </div>
    <div class="stat-card g2">
        <div class="stat-icon">❤️</div>
        <div class="stat-value">{{ health.healthy }}</div>
        <div class="stat-label">Healthy</div>
        <div class="stat-sub">{{ health.degraded }} degraded &middot; {{ health.offline }} offline</div>
    </div>
    <div class="stat-card g3">
        <div class="stat-icon">$</div>
        <div class="stat-value">${{ "%.0f"|format(stats.monthly_cost) }}</div>
        <div class="stat-label">Est. Monthly Cost</div>
        <div class="stat-sub">${{ "%.2f"|format(stats.hourly_cost) }}/hr</div>
    </div>
    <div class="stat-card g4">
        <div class="stat-icon">⇪</div>
        <div class="stat-value">{{ stats.deployments }}</div>
        <div class="stat-label">Deployments</div>
    </div>
</div>

{% if budget %}
<div class="card" style="padding:16px 20px;">
    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
        <div>
            <span style="font-size:13px;font-weight:600;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.3px;">Budget Utilization</span>
            <div style="font-size:11px;color:var(--text-dim);margin-top:2px;">
                ${{ "%.0f"|format(stats.monthly_cost) }} of ${{ "%.0f"|format(budget) }} used
            </div>
        </div>
        <div style="text-align:right;">
            <span style="font-size:20px;font-weight:700;font-family:var(--font-mono);color:{% if budget_pct < 70 %}var(--success){% elif budget_pct < 90 %}var(--warning){% else %}var(--danger){% endif %};">{{ budget_pct }}%</span>
            <form method="post" action="/set-budget" style="display:inline-flex;align-items:center;gap:4px;margin-left:12px;">
                <span style="font-size:11px;color:var(--text-dim);">$</span>
                <input class="budget-input" type="number" name="budget" value="{{ "%.0f"|format(budget) }}" min="1" step="10">
                <button class="btn-ghost" style="font-size:11px;">Set</button>
            </form>
        </div>
    </div>
    <div class="progress-bar">
        <div class="fill {{ cost_level }}" style="width:{{ budget_pct }}%;"></div>
    </div>
</div>
{% endif %}

{% if has_charts %}
<div class="card chart-row">
    <div class="chart-box">
        <h2>By Type</h2>
        <canvas id="dashPieChart"></canvas>
    </div>
    <div class="chart-box">
        <h2>By Status</h2>
        <canvas id="dashStatusChart"></canvas>
    </div>
</div>
{% endif %}

<div class="card">
    <div class="section-header">
        <h1>Infrastructure Inventory
            <span style="font-size:12px;font-weight:400;color:var(--text-dim);font-family:var(--font-mono);">
                @{{ session.get('username') }}
            </span>
        </h1>
        <div class="actions">
            <input class="filter-input" id="filterInput"
                   placeholder="Search resources..."
                   oninput="filterTable('filterInput','resourceTable')">
            <a href="/resources/add" class="btn btn-primary">+ Add Resource</a>
            <a href="/export/csv/resources" class="btn btn-outline">CSV</a>
        </div>
    </div>

    {% if error %}<div class="error">{{ error }}</div>{% endif %}

    {% if resources %}
    <div class="bulk-bar" id="bulkBar" style="display:none;align-items:center;gap:8px;margin-bottom:12px;padding:8px 12px;background:var(--primary-glow);border-radius:6px;border:1px solid rgba(124,111,247,0.2);">
        <span style="font-size:13px;color:var(--text-muted);"><span id="bulkCount">0</span> selected</span>
        <button class="btn btn-sm btn-primary" onclick="bulkAction('stop')">Stop</button>
        <button class="btn btn-sm btn-primary" onclick="bulkAction('terminate')">Terminate</button>
        <button class="btn btn-sm btn-danger" onclick="bulkAction('delete')">Delete</button>
        <button class="btn btn-sm btn-outline" onclick="clearSelection()">Clear</button>
    </div>
    <form id="bulkForm" method="post" action="/resources/bulk" style="display:none;">
        <input type="hidden" name="action" id="bulkActionInput">
        <input type="hidden" name="ids" id="bulkIdsInput">
    </form>
    <div class="filter-pills" id="typePills"></div>
    <table id="resourceTable">
        <thead>
            <tr>
                <th style="width:32px;"><input type="checkbox" id="selectAll" onchange="toggleAll()"></th>
                <th>Name</th>
                <th>Type</th>
                <th>Region</th>
                <th>Cost</th>
                <th>Tags</th>
                <th>Health</th>
                <th>Status</th>
                <th>Age</th>
                <th></th>
            </tr>
        </thead>
        <tbody>
            {% for resource in resources %}
            <tr data-type="{{ resource.type }}" data-health="{{ resource.health }}" data-id="{{ resource.id }}">
                <td><input type="checkbox" class="row-checkbox" onchange="updateBulkBar()"></td>
                <td>
                    <div class="resource-name">{{ resource.type_icon }} {{ resource.name }}</div>
                    <div class="resource-meta">ID: {{ resource.id }}</div>
                </td>
                <td><span class="badge badge-neutral">{{ resource.type }}</span></td>
                <td class="mono">{{ resource.region }}</td>
                <td class="mono">${{ "%.4f"|format(resource.cost_per_hour) }}</td>
                <td>{{ resource.tags_html|safe }}</td>
                <td>
                    <span class="status-dot {{ resource.health }}"></span>
                    <span class="badge badge-{{ resource.health_class }}">{{ resource.health }}</span>
                </td>
                <td>
                    <span class="badge badge-{{ resource.status_class }}">{{ resource.status }}</span>
                </td>
                <td><span class="age" data-age="{{ resource.created_at }}">{{ resource.created_at[:10] if resource.created_at else '--' }}</span></td>
                <td class="actions">
                    <a href="/resources/{{ resource.id }}/edit" class="btn-ghost" title="Edit">&#9998;</a>
                    <form class="inline-form" method="post"
                          action="/resources/{{ resource.id }}/delete"
                          onsubmit="return confirm('Delete this resource?')">
                        <button class="btn-ghost" title="Delete" style="color:var(--danger)">&#10005;</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty">
        <div style="font-size:40px;margin-bottom:12px;">⎔</div>
        <div>No infrastructure resources yet.</div>
        <div style="margin-top:16px;">
            <a href="/resources/add" class="btn btn-primary">+ Add Your First Resource</a>
        </div>
    </div>
    {% endif %}
</div>

{% if recent_deploys %}
<div class="card">
    <div class="section-header" style="margin-bottom:12px;">
        <h2>Recent Deployments</h2>
        <a href="/deployments" class="btn btn-outline btn-sm">View All</a>
    </div>
    <table>
        <tr>
            <th>ID</th>
            <th>Resources</th>
            <th>Status</th>
            <th>Age</th>
        </tr>
        {% for deploy in recent_deploys %}
        <tr>
            <td class="mono">#{{ deploy.id }}</td>
            <td>{{ deploy.resource_ids|length }} resource(s)</td>
            <td>
                <span class="status-dot {{ deploy.status }}"></span>
                <span class="badge badge-{{ deploy.status_class }}">{{ deploy.status }}</span>
            </td>
            <td><span class="age" data-age="{{ deploy.created_at }}">{{ deploy.created_at[:10] if deploy.created_at else '--' }}</span></td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}

<script>
{% if has_charts %}
(function() {
    var textColor = '#8892a6';
    var palette = ['#7c6ff7','#a78bfa','#c084fc','#e879f9','#f472b6','#fb923c','#fbbf24'];

    new Chart(document.getElementById('dashPieChart'), {
        type: 'doughnut',
        data: {
            labels: {{ type_labels|safe }},
            datasets: [{ data: {{ type_counts|safe }}, backgroundColor: palette }]
        },
        options: {
            plugins: {
                legend: { position: 'bottom', labels: { color: textColor, boxWidth: 12, font: { size: 11 } } }
            },
            responsive: true,
            maintainAspectRatio: true
        }
    });

    var statusColors = {'running':'#4ade80','stopped':'#fbbf24','terminated':'#f87171'};
    var statusLabels = {{ status_labels|safe }};
    var statusValues = {{ status_counts|safe }};

    new Chart(document.getElementById('dashStatusChart'), {
        type: 'doughnut',
        data: {
            labels: statusLabels,
            datasets: [{
                data: statusValues,
                backgroundColor: statusLabels.map(function(s) {
                    return statusColors[s] || '#8892a6';
                })
            }]
        },
        options: {
            plugins: {
                legend: { position: 'bottom', labels: { color: textColor, boxWidth: 12, font: { size: 11 } } }
            },
            responsive: true,
            maintainAspectRatio: true
        }
    });
})();
{% endif %}

function toggleAll() {
    var checked = document.getElementById('selectAll').checked;
    document.querySelectorAll('.row-checkbox').forEach(function(cb) { cb.checked = checked; });
    updateBulkBar();
}

function updateBulkBar() {
    var checkboxes = document.querySelectorAll('.row-checkbox:checked');
    var bar = document.getElementById('bulkBar');
    var count = document.getElementById('bulkCount');
    count.textContent = checkboxes.length;
    bar.style.display = checkboxes.length > 0 ? 'flex' : 'none';
}

function clearSelection() {
    document.querySelectorAll('.row-checkbox').forEach(function(cb) { cb.checked = false; });
    document.getElementById('selectAll').checked = false;
    updateBulkBar();
}

function bulkAction(action) {
    var ids = [];
    document.querySelectorAll('.row-checkbox:checked').forEach(function(cb) {
        var row = cb.closest('tr');
        if (row) ids.push(row.getAttribute('data-id'));
    });
    if (!ids.length) return;
    var msg = action === 'delete' ? 'Delete selected resources?' : (action.charAt(0).toUpperCase() + action.slice(1) + ' selected resources?');
    if (!confirm(msg)) return;
    var form = document.getElementById('bulkForm');
    document.getElementById('bulkActionInput').value = action;
    document.getElementById('bulkIdsInput').value = ids.join(',');
    form.submit();
}

(function() {
    var types = {};
    document.querySelectorAll('#resourceTable tbody tr').forEach(function(row) {
        types[row.getAttribute('data-type')] = true;
    });
    var container = document.getElementById('typePills');
    if (!container || Object.keys(types).length < 2) return;

    var allButton = document.createElement('button');
    allButton.className = 'filter-pill active';
    allButton.textContent = 'All';
    allButton.onclick = function() {
        document.querySelectorAll('.filter-pill').forEach(function(p) { p.classList.remove('active'); });
        allButton.classList.add('active');
        document.querySelectorAll('#resourceTable tbody tr').forEach(function(r) { r.style.display = ''; });
    };
    container.appendChild(allButton);

    Object.keys(types).sort().forEach(function(type) {
        var button = document.createElement('button');
        button.className = 'filter-pill';
        button.textContent = type;
        button.onclick = function() {
            document.querySelectorAll('.filter-pill').forEach(function(p) { p.classList.remove('active'); });
            button.classList.add('active');
            document.querySelectorAll('#resourceTable tbody tr').forEach(function(r) {
                r.style.display = r.getAttribute('data-type') === type ? '' : 'none';
            });
        };
        container.appendChild(button);
    });
})();

function openPanel(id) {
    fetch('/api/resources/' + id)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || data.error) return;
            var r = data.resource;
            var deploys = data.deployments || [];
            var tags = '';
            if (r.tags) {
                tags = Object.keys(r.tags).map(function(k) {
                    return k + ': ' + r.tags[k];
                }).join('<br>');
            }
            var deployRows = deploys.length ? deploys.map(function(d) {
                var sc = d.status === 'completed' ? 'success' : (d.status === 'in_progress' ? 'warning' : 'danger');
                return '<div class="prop-row"><span class="prop-label">#' + d.id + '</span><span class="badge badge-' + sc + '">' + d.status + '</span><span class="prop-value" style="font-size:11px;">' + (d.created_at ? d.created_at.slice(0,10) : '--') + '</span></div>';
            }).join('') : '<div style="color:var(--text-dim);font-size:13px;">No deployments for this resource.</div>';
            document.getElementById('panelContent').innerHTML =
                '<h1>' + r.name + '</h1>' +
                '<div class="panel-meta">ID: ' + r.id + '</div>' +
                '<div class="panel-section">' +
                    '<div class="prop-row"><span class="prop-label">Type</span><span class="badge badge-neutral">' + r.type + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Region</span><span class="prop-value">' + r.region + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Status</span><span class="badge badge-' + (r.status === 'running' ? 'success' : (r.status === 'stopped' ? 'warning' : 'danger')) + '">' + r.status + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Cost/hr</span><span class="prop-value">$' + r.cost_per_hour.toFixed(4) + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Cost/mo</span><span class="prop-value">$' + (r.cost_per_hour * 730).toFixed(2) + '</span></div>' +
                    (tags ? '<div class="prop-row"><span class="prop-label">Tags</span><span class="prop-value" style="font-family:var(--font-sans);">' + tags + '</span></div>' : '') +
                    '<div class="prop-row"><span class="prop-label">Created</span><span class="prop-value">' + (r.created_at ? r.created_at.slice(0,10) : '--') + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Updated</span><span class="prop-value">' + (r.updated_at ? r.updated_at.slice(0,10) : '--') + '</span></div>' +
                '</div>' +
                '<div class="panel-section"><h2>Deployment History</h2>' + deployRows + '</div>';
            document.getElementById('slidePanel').classList.add('open');
            document.getElementById('panelOverlay').classList.add('open');
        });
}

function closePanel() {
    document.getElementById('slidePanel').classList.remove('open');
    document.getElementById('panelOverlay').classList.remove('open');
}

document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('#resourceTable tbody tr').forEach(function(row) {
        row.style.cursor = 'pointer';
        row.addEventListener('click', function(e) {
            if (e.target.closest('a') || e.target.closest('button') || e.target.closest('input') || e.target.closest('form')) return;
            var id = row.getAttribute('data-id');
            if (id) openPanel(parseInt(id));
        });
    });
});
</script>

<div class="panel-overlay" id="panelOverlay" onclick="closePanel()"></div>
<div class="slide-panel" id="slidePanel">
    <button class="close-btn" onclick="closePanel()">&#10005;</button>
    <div id="panelContent"></div>
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
        for resource in data:
            resource["tags_html"] = format_tags(resource.get("tags"))
            resource["type_icon"] = RESOURCE_TYPE_ICONS.get(resource["type"], "⎔")
            resource["health"] = derive_health(resource["status"])
            resource["health_class"] = status_badge_class(resource["health"])
            resource["status_class"] = status_badge_class(resource["status"])
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
        "deployments": 0,
    }
    health = {"healthy": 0, "degraded": 0, "offline": 0}
    type_labels = "[]"
    type_counts = "[]"
    status_labels = "[]"
    status_counts = "[]"
    recent_deploys = []

    budget = session.get("budget", DEFAULT_BUDGET)
    budget_pct = 0
    has_charts = False

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

        budget_pct = min(100, round(stats["monthly_cost"] / budget * 100, 1))
        type_labels = json.dumps(list(groups.keys()))
        type_counts = json.dumps(list(groups.values()))
        status_labels = json.dumps(list(status_groups.keys()))
        status_counts = json.dumps(list(status_groups.values()))
        has_charts = True

    deploy_data = api_get("/api/deployments")
    if isinstance(deploy_data, list):
        stats["deployments"] = len(deploy_data)
        for deploy in deploy_data[:5]:
            deploy["status_class"] = status_badge_class(deploy["status"])
        recent_deploys = deploy_data[:5]

    return render_page(
        DASHBOARD_PAGE,
        resources=resources,
        error=error,
        stats=stats,
        health=health,
        budget=budget,
        budget_pct=budget_pct,
        cost_level=cost_percentage(budget_pct),
        has_charts=has_charts,
        type_labels=type_labels,
        type_counts=type_counts,
        status_labels=status_labels,
        status_counts=status_counts,
        recent_deploys=recent_deploys,
    )


ADD_RESOURCE_PAGE = """
<div class="card">
    <h1>Add Cloud Resource</h1>
    <p class="meta">Tags format: one per line as key:value</p>
    <form method="post">
        <div class="form-group">
            <label>Name</label>
            <input type="text" name="name" required>
        </div>
        <div class="form-group">
            <label>Type</label>
            <select name="type" required>
                {% for t in resource_types %}
                <option value="{{ t }}">{{ t }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="form-group">
            <label>Region</label>
            <select name="region">
                {% for value, label in regions %}
                <option value="{{ value }}">{{ label }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="form-group">
            <label>Status</label>
            <select name="status">
                {% for s in statuses %}
                <option value="{{ s }}">{{ s }}</option>
                {% endfor %}
            </select>
        </div>
        <div class="form-group">
            <label>Tags (key:value per line)</label>
            <textarea name="tags" rows="4"></textarea>
        </div>
        <button type="submit" class="btn btn-primary">Create Resource</button>
        <a href="/" class="btn btn-outline">Cancel</a>
    </form>
</div>
"""

ERROR_PAGE = """
<div class="card">
    <h1>{{ title }}</h1>
    <div class="error">{{ message }}</div>
    <a href="{{ back_url }}" class="btn btn-outline">Go back</a>
</div>
"""


@app.route("/resources/add", methods=["GET", "POST"])
def add_resource():
    if not session.get("user_id"):
        return redirect("/login")

    if request.method == "POST":
        payload = {
            "name": request.form["name"],
            "type": request.form["type"],
            "region": request.form.get("region", "us-east-1"),
            "status": request.form.get("status", "running"),
        }
        tags = parse_tags(request.form)
        if tags:
            payload["tags"] = tags

        result, status_code = api_post("/api/resources", payload)
        if status_code in (200, 201):
            return redirect("/")
        return render_page(
            ERROR_PAGE,
            title="Error",
            message=result.get("error", "Failed to create resource"),
            back_url="/resources/add",
        )

    return render_page(
        ADD_RESOURCE_PAGE,
        resource_types=RESOURCE_TYPES,
        regions=REGIONS,
        statuses=STATUSES,
    )


@app.route("/resources/<int:resource_id>/edit", methods=["GET", "POST"])
def edit_resource(resource_id):
    if not session.get("user_id"):
        return redirect("/login")

    if request.method == "POST":
        payload = {
            "name": request.form["name"],
            "type": request.form["type"],
            "region": request.form.get("region", "us-east-1"),
            "status": request.form.get("status", "running"),
        }
        tags = parse_tags(request.form)
        if tags:
            payload["tags"] = tags

        result, status_code = api_put(f"/api/resources/{resource_id}", payload)
        if status_code in (200, 201):
            return redirect("/")
        return render_page(
            ERROR_PAGE,
            title="Error",
            message=result.get("error", "Failed to update resource"),
            back_url=f"/resources/{resource_id}/edit",
        )

    data = api_get("/api/resources")
    resource = None
    if isinstance(data, list):
        resource = next((r for r in data if r["id"] == resource_id), None)
    if not resource:
        return redirect("/")

    return render_page(
        resource_form_html("PUT", f"/resources/{resource_id}/edit", resource),
    )


@app.route("/resources/<int:resource_id>/delete", methods=["POST"])
def delete_resource(resource_id):
    if not session.get("user_id"):
        return redirect("/login")
    api_delete(f"/api/resources/{resource_id}")
    return redirect("/")


def account_stats_html(profile):
    return f"""
<div class="stat"><div class="value">${profile["total_hourly"]:.2f}</div><div class="label">Per Hour</div></div>
<div class="stat"><div class="value">${profile["total_monthly"]:.2f}</div><div class="label">Per Month (730h)</div></div>
"""


COST_PAGE = """
<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h1>Cost Summary</h1>
        <a href="/export/csv/costs" class="btn btn-outline">CSV</a>
    </div>
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

<div class="card">
    <h2>Cost Trend (Last 30 Days)</h2>
    <canvas id="trendChart" style="max-height:220px;margin:8px 0 16px;"></canvas>
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
        <tr>
            <th>Type</th>
            <th>Count</th>
            <th>Cost/hr</th>
            <th>Cost/month</th>
        </tr>
        {% for entry in summary.by_type %}
        <tr>
            <td><span class="badge badge-neutral">{{ entry.type }}</span></td>
            <td>{{ entry.count }}</td>
            <td>${{ "%.4f"|format(entry.total_hourly) }}</td>
            <td>${{ "%.2f"|format(entry.total_monthly) }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}

{% if summary and summary.resources %}
<div class="card">
    <h2>Resource Breakdown</h2>
    <table>
        <tr>
            <th>Name</th>
            <th>Type</th>
            <th>Cost/hr</th>
            <th>Cost/month</th>
        </tr>
        {% for entry in summary.resources %}
        <tr>
            <td>{{ entry.name }}</td>
            <td><span class="badge badge-neutral">{{ entry.type }}</span></td>
            <td>${{ "%.4f"|format(entry.cost_per_hour) }}</td>
            <td>${{ "%.2f"|format(entry.monthly_cost) }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}

<script>
{% if summary and summary.total_hourly is defined %}
(function() {
    var textColor = '#8892a6';
    fetch('/api/cost-history')
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data || !data.length) return;
            var labels = data.map(function(e) { return e.date.slice(5); });
            var values = data.map(function(e) { return e.total_cost; });
            var gradient = document.getElementById('trendChart').getContext('2d').createLinearGradient(0,0,0,220);
            gradient.addColorStop(0, 'rgba(124,111,247,0.3)');
            gradient.addColorStop(1, 'rgba(124,111,247,0)');
            new Chart(document.getElementById('trendChart'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Daily Cost',
                        data: values,
                        borderColor: '#7c6ff7',
                        backgroundColor: gradient,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointBackgroundColor: '#7c6ff7'
                    }]
                },
                options: {
                    scales: {
                        x: { ticks: { color: textColor, maxTicksLimit: 10, font: { size: 10 } } },
                        y: { beginAtZero: true, ticks: { color: textColor, font: { size: 10 }, callback: function(v) { return '$' + v.toFixed(0); } } }
                    },
                    plugins: {
                        legend: { labels: { color: textColor } }
                    },
                    responsive: true,
                    maintainAspectRatio: true
                }
            });
        });
})();
{% endif %}

{% if summary and summary.by_type %}
(function() {
    var textColor = '#8892a6';
    var breakdown = {{ breakdown_json|safe }};

    new Chart(document.getElementById('pieChart'), {
        type: 'pie',
        data: {
            labels: breakdown.map(function(t) { return t.type; }),
            datasets: [{
                data: breakdown.map(function(t) { return t.total_monthly; }),
                backgroundColor: ['#7c6ff7','#a78bfa','#c084fc','#e879f9','#f472b6','#fb923c','#fbbf24']
            }]
        },
        options: {
            plugins: { legend: { labels: { color: textColor } } }
        }
    });

    new Chart(document.getElementById('barChart'), {
        type: 'bar',
        data: {
            labels: breakdown.map(function(t) { return t.type; }),
            datasets: [{
                label: 'Monthly Cost',
                data: breakdown.map(function(t) { return t.total_monthly; }),
                backgroundColor: '#7c6ff7'
            }]
        },
        options: {
            scales: {
                y: { beginAtZero: true, ticks: { color: textColor } },
                x: { ticks: { color: textColor } }
            },
            plugins: { legend: { display: false } }
        }
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
    breakdown_json = "[]"

    if isinstance(data, dict) and "error" not in data:
        summary = data
        breakdown_json = json.dumps(data.get("by_type", []))
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    return render_page(COST_PAGE, summary=summary, error=error, breakdown_json=breakdown_json)


DEPLOY_HISTORY_PAGE = """
<div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
        <h1>Deployment History</h1>
        <a href="/deploy" class="btn btn-primary">+ New Deployment</a>
    </div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if deploy_list %}
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>Resources</th>
                <th>Status</th>
                <th>Created</th>
                <th>Completed</th>
            </tr>
        </thead>
        <tbody>
        {% for deploy in deploy_list %}
        <tr>
            <td class="mono">#{{ deploy.id }}</td>
            <td>{{ deploy.resource_ids|length }} resource(s)</td>
            <td>
                <span class="status-dot {{ deploy.status }}"></span>
                <span class="badge badge-{{ deploy.status_class }}">{{ deploy.status }}</span>
            </td>
            <td>{{ deploy.created_at[:10] if deploy.created_at else '--' }}</td>
            <td>{{ deploy.completed_at[:10] if deploy.completed_at else '--' }}</td>
        </tr>
        {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="empty">No deployments yet. <a href="/deploy">Trigger a deployment</a></div>
    {% endif %}
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
        for deploy in data:
            deploy["status_class"] = status_badge_class(deploy["status"])
        deploy_list = data
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    return render_page(DEPLOY_HISTORY_PAGE, deploy_list=deploy_list, error=error)


DEPLOY_FORM_PAGE = """
<div class="card">
    <h1>Trigger Infrastructure Deployment</h1>
    <p class="meta">
        Select resources to deploy. Deployment simulates a 5-second provisioning process.
    </p>
    <form method="post">
        {% if resource_list %}
        <table>
            <tr>
                <th>Select</th>
                <th>Name</th>
                <th>Type</th>
                <th>Region</th>
                <th>Tags</th>
                <th>Cost</th>
            </tr>
            {% for resource in resource_list %}
            <tr>
                <td>
                    <input type="checkbox" name="resource_ids" value="{{ resource.id }}">
                </td>
                <td>{{ resource.name }}</td>
                <td><span class="badge badge-neutral">{{ resource.type }}</span></td>
                <td>{{ resource.region }}</td>
                <td>{{ resource.tags_html|safe }}</td>
                <td>${{ "%.4f"|format(resource.cost_per_hour) }}/hr</td>
            </tr>
            {% endfor %}
        </table>
        <br>
        <button type="submit" class="btn btn-primary">Deploy Selected</button>
        {% else %}
        <div class="empty">No resources available. <a href="/resources/add">Add resources first</a></div>
        {% endif %}
        <a href="/deployments" class="btn btn-outline">Cancel</a>
    </form>
</div>
"""


@app.route("/deploy", methods=["GET", "POST"])
def deploy():
    if not session.get("user_id"):
        return redirect("/login")

    if request.method == "POST":
        selected_ids = request.form.getlist("resource_ids")
        if not selected_ids:
            return render_page(
                """<div class="card"><h1>Deploy Resources</h1><div class="error">Select at least one resource.</div><a href="/deploy" class="btn btn-outline">Try again</a></div>"""
            )

        ids = [int(x) for x in selected_ids]
        result, status_code = api_post("/api/deployments", {"resource_ids": ids})
        if status_code in (200, 201):
            return redirect("/deployments")
        return render_page(
            """<div class="card"><h1>Deploy Resources</h1><div class="error">{{ message }}</div><a href="/deploy" class="btn btn-outline">Try again</a></div>""",
            message=result.get("error", "Deployment failed"),
        )

    resources_data = api_get("/api/resources")
    resource_list = resources_data if isinstance(resources_data, list) else []
    for resource in resource_list:
        resource["tags_html"] = format_tags(resource.get("tags"))

    return render_page(DEPLOY_FORM_PAGE, resource_list=resource_list)


LOGIN_PAGE = """
<div class="card" style="max-width:400px;margin:40px auto;">
    <h1>Login</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
        <div class="form-group">
            <label>Username</label>
            <input type="text" name="username" required>
        </div>
        <div class="form-group">
            <label>Password</label>
            <input type="password" name="password" required>
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%;">Sign In</button>
    </form>
    <p style="text-align:center;margin-top:12px;font-size:14px;">
        Don't have an account? <a href="/register">Register</a>
    </p>
</div>
"""


@app.route("/login", methods=["GET", "POST"])
def login():
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
        return render_page(
            LOGIN_PAGE,
            error=result.get("error", "Login failed"),
        )
    return render_page(LOGIN_PAGE)


REGISTER_PAGE = """
<div class="card" style="max-width:400px;margin:40px auto;">
    <h1>Register</h1>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post">
        <div class="form-group">
            <label>Username</label>
            <input type="text" name="username" required>
        </div>
        <div class="form-group">
            <label>Password</label>
            <input type="password" name="password" required>
        </div>
        <div class="form-group">
            <label>Confirm Password</label>
            <input type="password" name="confirm_password" required>
        </div>
        <button type="submit" class="btn btn-primary" style="width:100%;">Create Account</button>
    </form>
    <p style="text-align:center;margin-top:12px;font-size:14px;">
        Already have an account? <a href="/login">Login</a>
    </p>
</div>
"""


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form.get("confirm_password", "")

        if password != confirm:
            return render_page(
                REGISTER_PAGE,
                error="Passwords do not match",
            )

        result, status_code = api_post(
            "/api/register",
            {
                "username": request.form["username"],
                "password": password,
            },
        )
        if status_code in (200, 201) and "token" in result:
            session["user_id"] = result["user_id"]
            session["username"] = result["username"]
            session["token"] = result["token"]
            return redirect("/")
        return render_page(
            REGISTER_PAGE,
            error=result.get("error", "Registration failed"),
        )
    return render_page(REGISTER_PAGE)


@app.route("/api/resources/<int:resource_id>")
def resource_detail_proxy(resource_id):
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    data = api_get(f"/api/resources/{resource_id}")
    return app.response_class(
        response=json.dumps(data),
        mimetype="application/json",
    )


@app.route("/api/cost-history")
def cost_history_proxy():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    data = api_get("/api/cost-history")
    return app.response_class(
        response=json.dumps(data),
        mimetype="application/json",
    )


@app.route("/set-budget", methods=["POST"])
def set_budget():
    if not session.get("user_id"):
        return redirect("/login")
    try:
        amount = int(float(request.form.get("budget", DEFAULT_BUDGET)))
        session["budget"] = max(1, amount)
    except (ValueError, TypeError):
        pass
    return redirect("/")


@app.route("/resources/bulk", methods=["POST"])
def bulk_action():
    if not session.get("user_id"):
        return redirect("/login")
    action = request.form.get("action")
    ids_str = request.form.get("ids", "")
    ids = [int(x.strip()) for x in ids_str.split(",") if x.strip()]
    if action and ids:
        api_post("/api/resources/batch", {"action": action, "ids": ids})
    return redirect("/")


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
    writer = csv.writer(output)
    writer.writerow(["Name", "Type", "Region", "CostPerHour", "Status", "Tags"])

    for resource in resources:
        tags = ""
        if resource.get("tags"):
            tags = "; ".join(f"{k}:{v}" for k, v in resource["tags"].items())
        writer.writerow([
            resource["name"],
            resource["type"],
            resource["region"],
            resource["cost_per_hour"],
            resource["status"],
            tags,
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=resources.csv"},
    )


@app.route("/export/csv/costs")
def export_costs_csv():
    if not session.get("user_id"):
        return redirect("/login")

    data = api_get("/api/cost-summary")
    summary = data if isinstance(data, dict) and "error" not in data else {}

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Type", "CostPerHour", "MonthlyCost"])

    for resource in summary.get("resources", []):
        writer.writerow([
            resource["name"],
            resource["type"],
            resource["cost_per_hour"],
            resource.get("monthly_cost", 0),
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=costs.csv"},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
