from flask import Flask, session, request, redirect, render_template_string, Response, url_for
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
        .topbar { padding:16px 28px; border-bottom:1px solid var(--card-border); display:flex; justify-content:space-between; align-items:center; background:var(--bg); }
        .topbar h1 { font-size:18px; font-weight:600; color:var(--text); margin:0; letter-spacing:-0.2px; }
        .topbar .topbar-actions { display:flex; align-items:center; gap:10px; }
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
        .grid-4 { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
        .stat-card { text-align:left; padding:18px 20px; border-radius:10px; border:1px solid var(--card-border); background:var(--card-bg); position:relative; overflow:hidden; }
        .stat-card .stat-icon { font-size:22px; margin-bottom:10px; }
        .stat-card .stat-value { font-size:24px; font-weight:700; letter-spacing:-0.5px; font-family:var(--font-mono); }
        .stat-card .stat-label { font-size:12px; color:var(--text-muted); margin-top:2px; font-weight:500; text-transform:uppercase; letter-spacing:0.3px; }
        .stat-card.g1 .stat-value { color:#a78bfa; }
        .stat-card.g2 .stat-value { color:#4ade80; }
        .stat-card.g3 .stat-value { color:#fbbf24; }
        .stat-card.g4 .stat-value { color:#38bdf8; }
        .stat-card::after { content:''; position:absolute; top:0; right:0; width:80px; height:80px; border-radius:50%; opacity:0.06; transform:translate(30%,-30%); }
        .stat-card.g1::after { background:#a78bfa; }
        .stat-card.g2::after { background:#4ade80; }
        .stat-card.g3::after { background:#fbbf24; }
        .stat-card.g4::after { background:#38bdf8; }
        .stat-card .stat-sub { font-size:11px; color:var(--text-dim); margin-top:4px; font-family:var(--font-mono); }
        .chart-row { display:grid; grid-template-columns:1fr 1fr; gap:20px; }
        .chart-box { text-align:center; padding:8px 0; }
        .chart-box canvas { max-height:220px; margin:0 auto; }
        .badge { display:inline-flex; align-items:center; gap:4px; padding:3px 10px; border-radius:20px; font-size:11px; font-weight:600; letter-spacing:0.2px; }
        .badge-success { background:var(--success-bg); color:var(--success); }
        .badge-warning { background:var(--warning-bg); color:var(--warning); }
        .badge-danger { background:var(--danger-bg); color:var(--danger); }
        .badge-info { background:var(--primary-glow); color:var(--info); }
        .badge-neutral { background:rgba(255,255,255,0.04); color:var(--text-muted); }
        .tag { display:inline-block; padding:2px 8px; border-radius:4px; font-size:11px; font-family:var(--font-mono); background:var(--tag-bg); color:var(--tag-text); margin:1px 2px; }
        .status-dot { display:inline-block; width:7px; height:7px; border-radius:50%; margin-right:6px; vertical-align:middle; }
        .status-dot.running, .status-dot.completed { background:var(--success); box-shadow:0 0 6px rgba(74,222,128,0.5); }
        .status-dot.stopped, .status-dot.in_progress { background:var(--warning); box-shadow:0 0 6px rgba(251,191,36,0.4); }
        .status-dot.terminated { background:var(--danger); }
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
        .success { background:var(--success-bg); color:var(--success); padding:12px 16px; border-radius:6px; margin-bottom:16px; font-size:13px; }
        .form-group { margin-bottom:14px; }
        .form-group label { display:block; font-size:12px; font-weight:600; margin-bottom:5px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.3px; }
        .form-group input, .form-group select, .form-group textarea { width:100%; padding:9px 12px; border:1px solid var(--input-border); border-radius:6px; font-size:13px; background:var(--input-bg); color:var(--text); outline:none; font-family:var(--font-mono); transition:border-color .15s; }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
        .form-group textarea { resize:vertical; }
        .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        .meta { color:var(--text-dim); font-size:12px; margin-bottom:16px; font-family:var(--font-mono); }
        .chart-wrap { max-width:360px; margin:0 auto; }
        .stat { text-align:center; padding:16px; }
        .stat .value { font-size:26px; font-weight:700; color:var(--primary); font-family:var(--font-mono); letter-spacing:-0.5px; }
        .stat .label { font-size:12px; color:var(--text-muted); margin-top:2px; text-transform:uppercase; letter-spacing:0.3px; font-weight:600; }
        .inline-form { display:inline; }
        .mono { font-family:var(--font-mono); font-size:13px; }
        .section-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
        .section-header h1 { margin-bottom:0; }
        .type-icon { font-size:16px; margin-right:6px; vertical-align:middle; }
        .resource-name { font-weight:500; }
        .resource-meta { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); margin-top:2px; }
        .age { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); }
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
            .topbar { padding:12px 16px; flex-direction:column; gap:8px; align-items:stretch; }
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
            <a href="/" class="{{ 'active' if request.path == '/' else '' }}">
                <span class="nav-icon">⎔</span><span>Resources</span>
            </a>
            <a href="/cost-summary" class="{{ 'active' if request.path == '/cost-summary' else '' }}">
                <span class="nav-icon">$</span><span>Costs</span>
            </a>
            <a href="/deployments" class="{{ 'active' if request.path == '/deployments' else '' }}">
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
    var q = document.getElementById(inputId).value.toLowerCase();
    var rows = document.getElementById(tableId).querySelectorAll('tbody tr');
    rows.forEach(function(r) { r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none'; });
}
function timeAgo(iso) {
    if (!iso) return '—';
    var d = new Date(iso.replace('Z','+00:00'));
    var s = Math.floor((Date.now() - d) / 1000);
    if (s < 60) return s + 's ago';
    var m = Math.floor(s / 60); if (m < 60) return m + 'm ago';
    var h = Math.floor(m / 60); if (h < 24) return h + 'h ago';
    var days = Math.floor(h / 24); if (days < 30) return days + 'd ago';
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

STATUS_DOT = '<span class="status-dot %s"></span>'
TYPE_ICONS = {
    "Virtual Machine": "🖥️",
    "Kubernetes Cluster": "⎈",
    "Load Balancer": "⚖️",
    "Storage Account": "💾",
    "Database": "🗄️",
    "CDN Profile": "🌐",
    "Serverless Function": "⚡",
}

DASHBOARD_TEMPLATE = """
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
        <div class="stat-sub">{{ health.degraded }} degraded · {{ health.offline }} offline</div>
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
            <div style="font-size:11px;color:var(--text-dim);margin-top:2px;">${{ "%.0f"|format(stats.monthly_cost) }} of ${{ "%.0f"|format(budget) }} used</div>
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
        <div class="fill {% if budget_pct < 70 %}safe{% elif budget_pct < 90 %}warn{% else %}danger{% endif %}" style="width:{{ budget_pct }}%;"></div>
    </div>
</div>
{% endif %}

{% if dash_type_labels != "[]" %}
<div class="card chart-row">
    <div class="chart-box"><h2>By Type</h2><canvas id="dashPieChart"></canvas></div>
    <div class="chart-box"><h2>By Status</h2><canvas id="dashStatusChart"></canvas></div>
</div>
{% endif %}

<div class="card">
    <div class="section-header">
        <h1>Infrastructure Inventory</h1>
        <div class="actions">
            <input class="filter-input" id="filterInput" placeholder="Search resources..." oninput="filterTable('filterInput','resourceTable')">
            <a href="/resources/add" class="btn btn-primary">+ Add Resource</a>
            <a href="/export/csv/resources" class="btn btn-outline">CSV</a>
        </div>
    </div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if resources %}
    <div class="filter-pills" id="typePills"></div>
    <table id="resourceTable">
        <thead><tr><th>Name</th><th>Type</th><th>Region</th><th>Cost</th><th>Tags</th><th>Health</th><th>Status</th><th>Age</th><th></th></tr></thead>
        <tbody>
            {% for r in resources %}
            <tr data-type="{{ r.type }}" data-health="{{ r.health }}">
                <td>
                    <div class="resource-name">{{ r.type_icon|safe }} {{ r.name }}</div>
                    <div class="resource-meta">ID: {{ r.id }}</div>
                </td>
                <td><span class="badge badge-neutral">{{ r.type }}</span></td>
                <td class="mono">{{ r.region }}</td>
                <td class="mono">${{ "%.4f"|format(r.cost_per_hour) }}</td>
                <td>{{ r.tags_html|safe }}</td>
                <td><span class="status-dot {{ r.health }}"></span><span class="badge badge-{% if r.health == 'healthy' %}success{% elif r.health == 'degraded' %}warning{% else %}neutral{% endif %}">{{ r.health }}</span></td>
                <td><span class="badge badge-{% if r.status == 'running' %}success{% elif r.status == 'stopped' %}warning{% else %}danger{% endif %}">{{ r.status }}</span></td>
                <td><span class="age" data-age="{{ r.created_at }}">{{ r.created_at[:10] if r.created_at else '--' }}</span></td>
                <td class="actions">
                    <a href="/resources/{{ r.id }}/edit" class="btn-ghost" title="Edit">✎</a>
                    <form class="inline-form" method="post" action="/resources/{{ r.id }}/delete" onsubmit="return confirm('Delete this resource?')">
                        <button class="btn-ghost" title="Delete" style="color:var(--danger)">✕</button>
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
        <div style="margin-top:16px;"><a href="/resources/add" class="btn btn-primary">+ Add Your First Resource</a></div>
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
        <tr><th>ID</th><th>Resources</th><th>Status</th><th>Age</th></tr>
        {% for d in recent_deploys %}
        <tr>
            <td class="mono">#{{ d.id }}</td>
            <td>{{ d.resource_ids|length }} resource(s)</td>
            <td>
                <span class="status-dot {{ d.status }}"></span>
                <span class="badge badge-{% if d.status == 'completed' %}success{% elif d.status == 'in_progress' %}warning{% else %}neutral{% endif %}">{{ d.status }}</span>
            </td>
            <td><span class="age" data-age="{{ d.created_at }}">{{ d.created_at[:10] if d.created_at else '--' }}</span></td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}

<script>
{% if dash_type_labels != "[]" %}
(function() {
    var tc = '#8892a6';
    var colors = ['#7c6ff7','#a78bfa','#c084fc','#e879f9','#f472b6','#fb923c','#fbbf24'];
    new Chart(document.getElementById('dashPieChart'), {
        type: 'doughnut',
        data: { labels: {{ dash_type_labels|safe }}, datasets: [{ data: {{ dash_type_counts|safe }}, backgroundColor: colors }] },
        options: { plugins: { legend: { position: 'bottom', labels: { color: tc, boxWidth: 12, font: { size: 11 } } } }, responsive: true, maintainAspectRatio: true }
    });
    var statusColors = {'running':'#4ade80','stopped':'#fbbf24','terminated':'#f87171'};
    var statusLabels = {{ dash_status_labels|safe }};
    var statusData = {{ dash_status_counts|safe }};
    new Chart(document.getElementById('dashStatusChart'), {
        type: 'doughnut',
        data: { labels: statusLabels, datasets: [{ data: statusData, backgroundColor: statusLabels.map(function(s){return statusColors[s]||'#8892a6';}) }] },
        options: { plugins: { legend: { position: 'bottom', labels: { color: tc, boxWidth: 12, font: { size: 11 } } } }, responsive: true, maintainAspectRatio: true }
    });
})();
{% endif %}

// Type filter pills
(function() {
    var types = {};
    document.querySelectorAll('#resourceTable tbody tr').forEach(function(r) {
        types[r.getAttribute('data-type')] = true;
    });
    var pills = document.getElementById('typePills');
    if (!pills || Object.keys(types).length < 2) return;
    var all = document.createElement('button');
    all.className = 'filter-pill active'; all.textContent = 'All';
    all.onclick = function(){ document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active');}); all.classList.add('active'); document.querySelectorAll('#resourceTable tbody tr').forEach(function(r){r.style.display='';}); };
    pills.appendChild(all);
    Object.keys(types).sort().forEach(function(t) {
        var b = document.createElement('button');
        b.className = 'filter-pill'; b.textContent = t;
        b.onclick = function(){ document.querySelectorAll('.filter-pill').forEach(function(p){p.classList.remove('active');}); b.classList.add('active'); document.querySelectorAll('#resourceTable tbody tr').forEach(function(r){r.style.display=r.getAttribute('data-type')===t?'':'none';}); };
        pills.appendChild(b);
    });
})();
</script>
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
            r["type_icon"] = TYPE_ICONS.get(r["type"], "⎔")
            if r["status"] == "running":
                r["health"] = "healthy"
            elif r["status"] == "stopped":
                r["health"] = "degraded"
            else:
                r["health"] = "offline"
        resources = data
    elif isinstance(data, dict) and "error" in data:
        error = data["error"]

    stats = {"total": 0, "running": 0, "stopped": 0, "terminated": 0, "monthly_cost": 0, "hourly_cost": 0, "deployments": 0}
    health = {"healthy": 0, "degraded": 0, "offline": 0}
    dash_type_labels = "[]"
    dash_type_counts = "[]"
    dash_status_labels = "[]"
    dash_status_counts = "[]"
    recent_deploys = []
    budget = session.get("budget", 200)
    budget_pct = 0

    if resources:
        by_type = {}
        by_status = {}
        hourly_total = 0
        for r in resources:
            by_type[r["type"]] = by_type.get(r["type"], 0) + 1
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
            hourly_total += r.get("cost_per_hour", 0)
            health[r["health"]] = health.get(r["health"], 0) + 1
        stats["total"] = len(resources)
        stats["running"] = by_status.get("running", 0)
        stats["stopped"] = by_status.get("stopped", 0)
        stats["terminated"] = by_status.get("terminated", 0)
        stats["hourly_cost"] = round(hourly_total, 4)
        stats["monthly_cost"] = round(hourly_total * 730, 2)
        budget_pct = min(100, round(stats["monthly_cost"] / budget * 100, 1))
        dash_type_labels = json.dumps(list(by_type.keys()))
        dash_type_counts = json.dumps(list(by_type.values()))
        dash_status_labels = json.dumps(list(by_status.keys()))
        dash_status_counts = json.dumps(list(by_status.values()))

    deploy_data = api_get("/api/deployments")
    if isinstance(deploy_data, list):
        stats["deployments"] = len(deploy_data)
        recent_deploys = deploy_data[:5]

    return render_page(DASHBOARD_TEMPLATE, resources=resources, error=error,
        stats=stats, health=health,
        budget=budget, budget_pct=budget_pct,
        dash_type_labels=dash_type_labels,
        dash_type_counts=dash_type_counts,
        dash_status_labels=dash_status_labels,
        dash_status_counts=dash_status_counts,
        recent_deploys=recent_deploys)

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

@app.route("/set-budget", methods=["POST"])
def set_budget():
    if not session.get("user_id"):
        return redirect("/login")
    try:
        session["budget"] = max(1, int(float(request.form.get("budget", 200))))
    except (ValueError, TypeError):
        pass
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
