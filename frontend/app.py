from flask import Flask, session, request, redirect, render_template_string, Response
import requests
import os
import csv
import io
import json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

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
    "Disk": "#84cc16",
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

LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <title>Cloud Infrastructure Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        :root {
            --bg: #070b11;
            --sidebar-bg: #0b1017;
            --card-bg: #0e151e;
            --card-border: #1a2633;
            --text: #dfe6f0;
            --text-muted: #7f8fa6;
            --text-dim: #3d4a5c;
            --primary: #7c6ff7;
            --primary-hover: #6a5cf0;
            --primary-glow: rgba(124,111,247,0.12);
            --success: #4ade80;
            --success-bg: rgba(74,222,128,0.08);
            --warning: #fbbf24;
            --warning-bg: rgba(251,191,36,0.08);
            --danger: #f87171;
            --danger-bg: rgba(248,113,113,0.08);
            --info: #38bdf8;
            --tag-bg: rgba(124,111,247,0.12);
            --tag-text: #a78bfa;
            --input-bg: #0b1017;
            --input-border: #1a2633;
            --focus-ring: rgba(124,111,247,0.25);
            --font-mono: 'SF Mono','Fira Code','Cascadia Code',monospace;
            --font-sans: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        }
        * { box-sizing:border-box; margin:0; padding:0; }
        body {
            font-family:var(--font-sans); background:var(--bg); color:var(--text);
            min-height:100vh;
            background-image: radial-gradient(circle at 50% 0%, rgba(124,111,247,0.03) 0%, transparent 60%),
                              repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(255,255,255,0.015) 39px, rgba(255,255,255,0.015) 40px);
        }
        .layout { display:flex; flex-direction:column; min-height:100vh; }
        .navbar {
            display:flex; align-items:center; gap:8px;
            padding:0 20px; height:48px;
            background:var(--sidebar-bg);
            border-bottom:1px solid var(--card-border);
            position:sticky; top:0; z-index:50;
            background-image: linear-gradient(90deg, rgba(124,111,247,0.03) 0%, transparent 120px);
        }
        .navbar-brand {
            display:flex; align-items:center; gap:8px;
            font-weight:700; font-size:15px; color:var(--primary);
            margin-right:24px; flex-shrink:0;
        }
        .navbar-brand svg { flex-shrink:0; }
        .navbar-nav { display:flex; align-items:center; gap:2px; flex:1; }
        .navbar-nav a {
            display:flex; align-items:center; gap:6px; padding:6px 14px;
            border-radius:6px; font-size:13px; color:var(--text-muted);
            text-decoration:none; font-weight:500; transition:all .15s;
            white-space:nowrap;
        }
        .navbar-nav a:hover { background:rgba(255,255,255,0.03); color:var(--text); }
        .navbar-nav a.active {
            background:var(--primary-glow); color:var(--primary);
        }
        .navbar-right { display:flex; align-items:center; gap:12px; flex-shrink:0; }
        .navbar-user {
            display:flex; align-items:center; gap:8px;
            font-size:13px; color:var(--text-muted);
        }
        .navbar-user .avatar {
            width:26px; height:26px; border-radius:6px;
            background:linear-gradient(135deg, var(--primary), #a78bfa);
            color:#fff; display:flex; align-items:center; justify-content:center;
            font-size:11px; font-weight:700;
        }
        .navbar-logout {
            display:flex; align-items:center; gap:6px; padding:5px 10px;
            border-radius:6px; font-size:12px; color:var(--danger);
            text-decoration:none; transition:background .15s;
        }
        .navbar-logout:hover { background:var(--danger-bg); }
        .main { flex:1; }
        .content { padding:16px 20px; }
        .table-scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; }
        .auth-wrap { max-width:420px; margin:80px auto; padding:0 16px; }
        .card {
            background:var(--card-bg);
            border:1px solid var(--card-border);
            border-radius:10px; padding:18px; margin-bottom:16px;
            position:relative;
        }
        .card::before {
            content:''; position:absolute; top:0; left:0; right:0;
            height:1px;
            background:linear-gradient(90deg, transparent, rgba(124,111,247,0.15), transparent);
            opacity:0; transition:opacity .25s;
        }
        .card:hover::before { opacity:1; }
        h1 { font-size:20px; font-weight:600; margin-bottom:12px; letter-spacing:-0.3px; }
        h2 { font-size:15px; font-weight:600; color:var(--text-muted); margin-bottom:14px; letter-spacing:0.3px; text-transform:uppercase; }
        table { width:100%; border-collapse:separate; border-spacing:0; }
        th {
            padding:8px 10px; text-align:left; font-size:10px; font-weight:600;
            color:var(--text-dim); text-transform:uppercase; letter-spacing:0.5px;
            border-bottom:1px solid var(--card-border); background:transparent;
            position:sticky; top:0; z-index:2;
        }
        td { padding:10px 10px; border-bottom:1px solid rgba(255,255,255,0.04); font-size:12px; }
        tbody tr { transition:background .12s; }
        tbody tr:hover { background:rgba(124,111,247,0.035); }
        tbody tr:last-child td { border-bottom:none; }
        .btn {
            display:inline-flex; align-items:center; gap:6px;
            padding:8px 16px; border-radius:6px; font-size:13px; font-weight:500;
            cursor:pointer; border:none; text-decoration:none; transition:all .15s;
        }
        .btn-primary { background:var(--primary); color:#fff; }
        .btn-primary:hover { background:var(--primary-hover); box-shadow:0 0 20px var(--primary-glow); }
        .btn-danger { background:var(--danger-bg); color:var(--danger); }
        .btn-danger:hover { background:rgba(248,113,113,0.15); }
        .btn-outline { background:transparent; color:var(--text-muted); border:1px solid var(--card-border); }
        .btn-outline:hover { border-color:var(--primary); color:var(--primary); box-shadow:0 0 12px var(--primary-glow); }
        .btn-sm { padding:5px 10px; font-size:12px; }
        .btn-ghost { background:transparent; color:var(--text-dim); padding:5px 8px; border-radius:4px; font-size:13px; }
        .btn-ghost:hover { background:rgba(255,255,255,0.04); color:var(--text); }
        .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        .grid-4 { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:16px; }
        .stat-card {
            padding:14px 16px; border-radius:10px;
            border:1px solid var(--card-border); background:var(--card-bg);
            position:relative; overflow:hidden;
            transition:border-color .2s, box-shadow .2s;
        }
        .stat-card:hover { border-color:rgba(124,111,247,0.15); box-shadow:0 0 20px rgba(124,111,247,0.05); }
        .stat-card .stat-icon { font-size:20px; margin-bottom:8px; opacity:0.7; }
        .stat-value {
            font-size:22px; font-weight:700; letter-spacing:-0.5px;
            font-family:var(--font-mono); line-height:1.2;
        }
        .stat-label {
            font-size:11px; color:var(--text-muted); margin-top:3px;
            font-weight:600; text-transform:uppercase; letter-spacing:0.5px;
        }
        .stat-sub { font-size:11px; color:var(--text-dim); margin-top:4px; font-family:var(--font-mono); }
        .stat-card.g1 .stat-value { color:#a78bfa; }
        .stat-card.g2 .stat-value { color:#4ade80; }
        .stat-card.g3 .stat-value { color:#fbbf24; }
        .stat-card.g4 .stat-value { color:#38bdf8; }
        .stat-card::after {
            content:''; position:absolute; top:0; right:0;
            width:100px; height:100px; border-radius:50%;
            opacity:0.05; transform:translate(35%,-35%);
            transition:opacity .3s;
        }
        .stat-card:hover::after { opacity:0.1; }
        .stat-card.g1::after { background:#a78bfa; }
        .stat-card.g2::after { background:#4ade80; }
        .stat-card.g3::after { background:#fbbf24; }
        .stat-card.g4::after { background:#38bdf8; }
        .chart-wrap { max-width:360px; margin:0 auto; }
        .badge {
            display:inline-flex; align-items:center; gap:4px;
            padding:3px 10px; border-radius:20px;
            font-size:11px; font-weight:600; letter-spacing:0.2px;
        }
        .badge-success { background:var(--success-bg); color:var(--success); }
        .badge-warning { background:var(--warning-bg); color:var(--warning); }
        .badge-danger { background:var(--danger-bg); color:var(--danger); }
        .badge-info { background:var(--tag-bg); color:var(--info); }
        .badge-neutral { background:rgba(255,255,255,0.03); color:#7f8fa6; }
        .tag {
            display:inline-block; padding:2px 8px; border-radius:4px;
            font-size:11px; font-family:var(--font-mono);
            background:var(--tag-bg); color:var(--tag-text); margin:1px 2px;
        }
        .status-dot {
            display:inline-block; width:7px; height:7px; border-radius:50%;
            margin-right:6px; vertical-align:middle;
        }
        .status-dot.running, .status-dot.completed { background:var(--success); box-shadow:0 0 8px rgba(74,222,128,0.5); }
        .status-dot.stopped, .status-dot.in_progress { background:var(--warning); box-shadow:0 0 8px rgba(251,191,36,0.4); }
        .status-dot.terminated, .status-dot.failed { background:var(--danger); box-shadow:0 0 8px rgba(248,113,113,0.3); }
        .type-filter select {
            padding:6px 12px; border-radius:6px; font-size:12px;
            border:1px solid var(--card-border); background:var(--input-bg);
            color:var(--text); font-family:var(--font-mono); cursor:pointer;
            outline:none; margin-bottom:14px; appearance:none;
            -webkit-appearance:none;
            background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6' fill='none' stroke='%238892a6' stroke-width='1.5'/%3E%3C/svg%3E");
            background-repeat:no-repeat; background-position:right 10px center; padding-right:28px;
        }
        .type-filter select:focus { border-color:var(--primary); }
        .filter-input {
            padding:7px 12px; border:1px solid var(--input-border);
            border-radius:6px; font-size:13px; background:var(--input-bg);
            color:var(--text); font-family:var(--font-mono); width:200px;
            outline:none; transition:border-color .15s;
        }
        .filter-input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
        .filter-input::placeholder { color:var(--text-dim); }
        .actions { display:flex; gap:6px; align-items:center; flex-wrap:wrap; }
        .actions .btn-ghost { opacity:0; transition:opacity .12s; }
        tbody tr:hover .actions .btn-ghost { opacity:1; }
        .empty { text-align:center; color:var(--text-muted); padding:48px 0; font-size:14px; }
        .empty a { color:var(--primary); text-decoration:none; }
        .empty a:hover { text-decoration:underline; }
        .error { background:var(--danger-bg); color:var(--danger); padding:12px 16px; border-radius:6px; margin-bottom:16px; font-size:13px; border:1px solid rgba(248,113,113,0.12); }
        .form-group { margin-bottom:14px; }
        .form-group label {
            display:block; font-size:11px; font-weight:600; margin-bottom:5px;
            color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px;
        }
        .form-group input, .form-group select, .form-group textarea {
            width:100%; padding:9px 12px; border:1px solid var(--input-border);
            border-radius:6px; font-size:13px; background:var(--input-bg);
            color:var(--text); outline:none; font-family:var(--font-mono);
            transition:border-color .15s;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring);
        }
        .section-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; flex-wrap:wrap; gap:8px; }
        .section-header h1 { margin-bottom:0; }
        .resource-name { font-weight:500; }
        .resource-meta { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); margin-top:2px; }
        .age { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); }
        .meta { color:var(--text-dim); font-size:12px; margin-bottom:16px; font-family:var(--font-mono); }
        .mono { font-family:var(--font-mono); font-size:13px; }
        .inline-form { display:inline; }
        .panel-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:50; opacity:0; pointer-events:none; transition:opacity .25s; backdrop-filter:blur(2px); }
        .panel-overlay.open { opacity:1; pointer-events:auto; }
        .slide-panel {
            position:fixed; top:0; right:0; bottom:0; width:480px; max-width:90vw;
            background:var(--sidebar-bg); border-left:1px solid var(--card-border);
            z-index:51; transform:translateX(100%); transition:transform .3s cubic-bezier(.22,1,.36,1);
            overflow-y:auto; padding:24px;
        }
        .slide-panel.open { transform:translateX(0); }
        .slide-panel .close-btn {
            float:right; background:none; border:none; color:var(--text-dim);
            font-size:20px; cursor:pointer; padding:4px 8px; border-radius:4px;
        }
        .slide-panel .close-btn:hover { color:var(--text); background:rgba(255,255,255,0.04); }
        .slide-panel h1 { font-size:18px; margin-bottom:4px; }
        .slide-panel .panel-meta { color:var(--text-dim); font-size:12px; font-family:var(--font-mono); margin-bottom:16px; }
        .slide-panel .panel-section { margin-bottom:16px; }
        .slide-panel .panel-section h2 { font-size:11px; margin-bottom:8px; letter-spacing:0.5px; }
        .slide-panel .prop-row { display:flex; justify-content:space-between; padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.04); font-size:13px; }
        .slide-panel .prop-row .prop-label { color:var(--text-muted); }
        .slide-panel .prop-row .prop-value { font-family:var(--font-mono); color:var(--text); }
        .sys-bar {
            display:flex; justify-content:space-between; align-items:center;
            padding:8px 16px; margin-bottom:20px;
            background:var(--card-bg); border:1px solid var(--card-border);
            border-radius:8px; font-size:12px;
        }
        .sys-bar-left { display:flex; align-items:center; gap:8px; }
        .sys-pulse {
            width:8px; height:8px; border-radius:50%;
            background:var(--success);
            box-shadow:0 0 10px rgba(74,222,128,0.6);
            animation:pulse 2s infinite;
        }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        .sys-text { color:var(--text-muted); font-weight:500; }
        .sys-bar-right { display:flex; align-items:center; gap:14px; }
        .sys-stat { display:flex; align-items:center; gap:5px; color:var(--text-dim); }
        .sys-dot { width:5px; height:5px; border-radius:50%; }
        .sys-mono { font-family:var(--font-mono); color:var(--text-dim); font-size:11px; }
        .sub-select { background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); color:var(--text); font-size:11px; padding:3px 8px; border-radius:4px; cursor:pointer; max-width:180px; }
        .sub-select option { background:#1a1d2e; color:var(--text); }
        tbody tr:nth-child(even) { background:rgba(255,255,255,0.012); }
        ::-webkit-scrollbar { width:6px; height:6px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:var(--text-dim); border-radius:3px; }
        ::-webkit-scrollbar-thumb:hover { background:var(--text-muted); }
        @media (max-width:600px) {
            .navbar-nav a span:last-child { display:none; }
            .navbar-user span { display:none; }
            .content { padding:12px; }
            .grid-4 { grid-template-columns:repeat(2,1fr); }
        }
        @media (max-width:400px) {
            .grid-4 { grid-template-columns:1fr; }
        }
    </style>
</head>
<body>
{% if session.get('user_id') %}
<div class="layout">
    <nav class="navbar">
        <div class="navbar-brand">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            <span>CloudDash</span>
        </div>
        <div class="navbar-nav">
            <a href="/" class="{{ 'active' if request.path == '/' else '' }}">
                <span>⎔</span><span>Resources</span>
            </a>
            <a href="/cost-summary" class="{{ 'active' if request.path == '/cost-summary' else '' }}">
                <span>$</span><span>Costs</span>
            </a>
            <a href="/deployments" class="{{ 'active' if request.path == '/deployments' else '' }}">
                <span>⇪</span><span>Deployments</span>
            </a>
        </div>
        <div class="navbar-right">
            <div class="navbar-user">
                <div class="avatar">{{ session.get('username','U')[:1].upper() }}</div>
                <span>{{ session.get('username') }}</span>
            </div>
            <a href="/logout" class="navbar-logout">⏻ Logout</a>
        </div>
    </nav>
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
document.addEventListener('DOMContentLoaded', function() {
    renderAges();
    animateCounters();
    updateRefreshTime();
});

function animateCounters() {
    document.querySelectorAll('.countup').forEach(function(el) {
        var target = parseFloat(el.getAttribute('data-target'));
        if (isNaN(target)) return;
        var prefix = el.getAttribute('data-prefix') || '';
        var decimals = parseInt(el.getAttribute('data-decimals')) || 0;
        var duration = 600;
        var start = performance.now();
        function step(now) {
            var pct = Math.min((now - start) / duration, 1);
            var eased = 1 - Math.pow(1 - pct, 3);
            var val = eased * target;
            if (decimals === 0) el.textContent = prefix + Math.round(val);
            else el.textContent = prefix + val.toFixed(decimals);
            if (pct < 1) requestAnimationFrame(step);
            else el.textContent = prefix + target.toFixed(decimals);
        }
        requestAnimationFrame(step);
    });
}

function updateRefreshTime() {
    var el = document.getElementById('refreshTime');
    if (el) el.textContent = '0s ago';
    var start = Date.now();
    setInterval(function() {
        var secs = Math.floor((Date.now() - start) / 1000);
        var el = document.getElementById('refreshTime');
        if (el) el.textContent = secs + 's ago';
    }, 10000);
}

document.addEventListener('DOMContentLoaded', function() {
    renderAges();
    animateCounters();
    updateRefreshTime();
});
</script>
</body>
</html>
"""


def api_request(method, path, data=None):
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if session.get("user_id") and session.get("token"):
        headers["X-User-ID"] = str(session["user_id"])
        headers["X-Auth-Token"] = session["token"]
    try:
        response = requests.request(method, f"{BACKEND_URL}{path}", json=data, headers=headers, timeout=5)
        if method == "GET":
            return response.json() if response.status_code < 500 else {"error": "server error"}
        return response.json(), response.status_code
    except requests.exceptions.ConnectionError:
        return {"error": "Could not connect to backend"} if method == "GET" else ({"error": "Could not connect to backend"}, 503)
    except Exception as e:
        return {"error": str(e)} if method == "GET" else ({"error": str(e)}, 500)

api_get = lambda p: api_request("GET", p)
api_post = lambda p, d: api_request("POST", p, d)


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


DASHBOARD_PAGE = """
<div class="sys-bar">
    <div class="sys-bar-left">
        <span class="sys-pulse"></span>
        <span class="sys-text">All systems operational</span>
    </div>
    <div class="sys-bar-right">
        <span class="sys-stat"><span class="sys-dot" style="background:var(--success)"></span> <span id="statResources">{{ resources|length }}</span> resources</span>
        <span class="sys-stat"><span class="sys-dot" style="background:var(--primary)"></span> <span id="statRunning">{{ stats.running }}</span> running</span>
        {% if subscriptions %}
        <select id="subSelector" class="sub-select" onchange="switchSubscription(this.value)">
            {% for sub in subscriptions %}
            <option value="{{ sub.id }}"{% if sub.is_current %} selected{% endif %}>{{ sub.display_name }}</option>
            {% endfor %}
        </select>
        {% endif %}
        <span id="refreshTime" class="sys-mono">just now</span>
    </div>
</div>

<div class="grid-4">
    <div class="stat-card g1">
        <div class="stat-icon">🖥️</div>
        <div class="stat-value"><span class="countup" data-target="{{ stats.total }}">0</span></div>
        <div class="stat-label">Total Resources</div>
    </div>
    <div class="stat-card g2">
        <div class="stat-icon">❤️</div>
        <div class="stat-value"><span class="countup" data-target="{{ health.healthy }}">0</span></div>
        <div class="stat-label">Healthy</div>
        <div class="stat-sub"><span class="countup" data-target="{{ health.degraded }}">0</span> degraded &middot; <span class="countup" data-target="{{ health.offline }}">0</span> offline</div>
    </div>
    <div class="stat-card g3">
        <div class="stat-icon">$</div>
        <div class="stat-value countup" data-target="{{ stats.monthly_cost }}" data-prefix="$" data-decimals="0">$0</div>
        <div class="stat-label">Est. Monthly Cost</div>
        <div class="stat-sub">${{ "%.2f"|format(stats.hourly_cost) }}/hr</div>
    </div>
    <div class="stat-card g4">
        <div class="stat-icon">⇪</div>
        <div class="stat-value"><span class="countup" data-target="{{ stats.deployments }}">0</span></div>
        <div class="stat-label">Deployments</div>
    </div>
</div>


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
    <div class="type-filter"><select id="typeFilter" onchange="filterByType(this.value)"><option value="">All Types</option></select></div>
    <div class="table-scroll"><table id="resourceTable">
        <thead>
            <tr>
                <th style="width:32px;"><input type="checkbox" id="selectAll" onchange="toggleAll()"></th>
                <th style="width:32px;">#</th>
                <th>Name</th>
                <th>Type</th>
                <th>Region</th>
                <th>Cost</th>
                <th>Tags</th>
                <th>Health</th>
                <th>Status</th>
                <th>Age</th>
            </tr>
        </thead>
        <tbody>
            {% for resource in resources %}
            <tr data-type="{{ resource.type }}" data-health="{{ resource.health }}" data-id="{{ resource.id }}">
                <td><input type="checkbox" class="row-checkbox" onchange="updateBulkBar()"></td>
                <td class="mono" style="color:var(--text-dim);font-size:11px;">{{ loop.index }}</td>
                <td>
                    <div class="resource-name">{{ resource.name }}</div>
                    <div class="resource-meta">ID: {{ resource.id }}</div>
                </td>
                <td><span class="badge" style="background:{{ resource.type_color }}15;color:{{ resource.type_color }};">{{ resource.type }}</span></td>
                <td class="mono">{{ resource.region }}</td>
                <td class="mono" style="text-align:right;">
                    {% if resource.cost_per_hour == 0 %}
                    <span class="badge badge-neutral" style="font-size:11px;">Free</span>
                    {% else %}
                    <div>${{ "%.2f"|format(resource.cost_per_hour * 730) }}/mo</div>
                    <div style="font-size:10px;color:var(--text-dim);">${{ "%.4f"|format(resource.cost_per_hour) }}/hr</div>
                    {% endif %}
                </td>
                <td>{{ resource.tags_html|safe }}</td>
                <td>
                    <span class="status-dot {{ resource.health }}"></span>
                    <span class="badge badge-{{ resource.health_class }}">{{ resource.health }}</span>
                </td>
                <td>
                    <span class="badge badge-{{ resource.status_class }}">{{ resource.status }}</span>
                </td>
                <td><span class="age" data-age="{{ resource.created_at }}">{{ resource.created_at[:10] if resource.created_at else '--' }}</span></td>
            </tr>
            {% endfor %}
        </tbody>
    </table></div>
    {% else %}
    <div class="empty">
        <div style="font-size:40px;margin-bottom:12px;">⎔</div>
        <div>No infrastructure resources yet.</div>
        <div style="margin-top:16px;">
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
window.typeColors = {{ type_colors_json|safe }};
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
    var sel = document.getElementById('typeFilter');
    if (!sel || Object.keys(types).length < 2) { if (sel) sel.style.display = 'none'; return; }

    Object.keys(types).sort().forEach(function(type) {
        var opt = document.createElement('option');
        opt.value = type;
        opt.textContent = type;
        sel.appendChild(opt);
    });
})();

function filterByType(type) {
    document.querySelectorAll('#resourceTable tbody tr').forEach(function(r) {
        r.style.display = !type || r.getAttribute('data-type') === type ? '' : 'none';
    });
}

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
                    '<div class="prop-row"><span class="prop-label">Type</span><span class="badge" style="background:' + (window.typeColors[r.type] || '#8892a6') + '18;color:' + (window.typeColors[r.type] || '#8892a6') + ';">' + r.type + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Region</span><span class="prop-value">' + r.region + '</span></div>' +
                    (r.resource_group ? '<div class="prop-row"><span class="prop-label">Resource Group</span><span class="prop-value mono">' + r.resource_group + '</span></div>' : '') +
                    (r.subscription_id ? '<div class="prop-row"><span class="prop-label">Subscription</span><span class="prop-value mono" style="font-size:11px;">' + r.subscription_id + '</span></div>' : '') +
                    (r.sku ? '<div class="prop-row"><span class="prop-label">SKU</span><span class="prop-value mono">' + r.sku + '</span></div>' : '') +
                    '<div class="prop-row"><span class="prop-label">Status</span><span class="badge badge-' + (r.status === 'running' ? 'success' : (r.status === 'stopped' ? 'warning' : 'danger')) + '">' + r.status + '</span></div>' +
                    (r.cost_per_hour === 0 ? '<div class="prop-row"><span class="prop-label">Cost</span><span class="badge badge-neutral">Free</span></div>' :
                    '<div class="prop-row"><span class="prop-label">Cost/hr</span><span class="prop-value">$' + r.cost_per_hour.toFixed(4) + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Cost/mo</span><span class="prop-value">$' + (r.cost_per_hour * 730).toFixed(2) + '</span></div>') +
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
    startAutoRefresh();
});

function switchSubscription(id) {
    var form = document.createElement('form');
    form.method = 'post';
    form.action = '/set-subscription';
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'subscription_id';
    input.value = id;
    form.appendChild(input);
    document.body.appendChild(form);
    form.submit();
}

function startAutoRefresh() {
    setInterval(function() {
        fetch('/api/resources').then(function(r) { return r.json(); }).then(function(data) {
            if (!Array.isArray(data)) return;
            var tbody = document.querySelector('#resourceTable tbody');
            if (!tbody) return;
            var typeSelect = document.getElementById('typeFilter');
            var selectedType = typeSelect ? typeSelect.value : '';
            var types = {};
            var html = '';
            var running = 0;
            data.forEach(function(r, i) {
                types[r.type] = true;
                running += r.status === 'running' ? 1 : 0;
                html += '<tr data-type="' + r.type + '" data-health="' + (r.health || 'unknown') + '" data-id="' + r.id + '">' +
                    '<td><input type="checkbox" class="row-checkbox" onchange="updateBulkBar()"></td>' +
                    '<td class="mono" style="color:var(--text-dim);font-size:11px;">' + (i+1) + '</td>' +
                    '<td><div class="resource-name">' + r.name + '</div><div class="resource-meta">ID: ' + r.id + '</div></td>' +
                    '<td><span class="badge" style="background:' + (window.typeColors[r.type] || '#8892a6') + '15;color:' + (window.typeColors[r.type] || '#8892a6') + ';">' + r.type + '</span></td>' +
                    '<td class="mono">' + (r.region || '') + '</td>' +
                    '<td class="mono" style="text-align:right;">' + (r.cost_per_hour === 0 ? '<span class="badge badge-neutral" style="font-size:11px;">Free</span>' : '<div>$' + (r.cost_per_hour * 730).toFixed(2) + '/mo</div><div style="font-size:10px;color:var(--text-dim);">$' + r.cost_per_hour.toFixed(4) + '/hr</div>') + '</td>' +
                    '<td>' + (r.tags ? Object.keys(r.tags).map(function(k) { return '<span class="tag">' + k + ':' + r.tags[k] + '</span>'; }).join(' ') : '') + '</td>' +
                    '<td><span class="status-dot ' + (r.health || 'unknown') + '"></span><span class="badge badge-' + ((r.health === 'healthy' || r.health === 'running') ? 'success' : (r.health === 'degraded' || r.health === 'stopped' ? 'warning' : 'danger')) + '">' + (r.health || r.status) + '</span></td>' +
                    '<td><span class="badge badge-' + (r.status === 'running' ? 'success' : (r.status === 'stopped' ? 'warning' : 'danger')) + '">' + r.status + '</span></td>' +
                    '<td><span class="age" data-age="' + (r.created_at || '') + '">' + (r.created_at ? r.created_at.slice(0,10) : '--') + '</span></td></tr>';
            });
            tbody.innerHTML = html;
            document.getElementById('statResources').textContent = data.length;
            document.getElementById('statRunning').textContent = running;
            renderAges();
            if (typeSelect) {
                var cur = typeSelect.value;
                typeSelect.innerHTML = '<option value="">All Types</option>';
                Object.keys(types).sort().forEach(function(t) {
                    typeSelect.innerHTML += '<option value="' + t + '">' + t + '</option>';
                });
                typeSelect.value = cur;
                filterByType(selectedType);
            }
            var el = document.getElementById('refreshTime');
            if (el) el.textContent = '0s ago';
        });
        fetch('/api/cost-summary').then(function(r) { return r.json(); }).then(function(c) {
            if (c && c.total_monthly) {
                var el = document.querySelector('.stat-card.g3 .stat-value');
                if (el) {
                    el.setAttribute('data-target', c.total_monthly.toFixed(0));
                    el.textContent = '$' + c.total_monthly.toFixed(0);
                }
            }
        });
    }, 30000);
}
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
            resource["health"] = derive_health(resource["status"])
            resource["health_class"] = status_badge_class(resource["health"])
            resource["status_class"] = status_badge_class(resource["status"])
            resource["type_color"] = type_color(resource["type"])
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
    type_colors_json = "{}"
    recent_deploys = []

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

        type_colors_json = json.dumps({t: type_color(t) for t in groups.keys()})

    cost_data = api_get("/api/cost-summary")
    if isinstance(cost_data, dict) and "error" not in cost_data and cost_data.get("total_monthly"):
        stats["monthly_cost"] = round(cost_data["total_monthly"], 2)
        stats["hourly_cost"] = round(cost_data["total_hourly"], 4)

    sub_data = api_get("/api/subscriptions")
    subscriptions = sub_data if isinstance(sub_data, list) else []

    if not session.get("subscription_id") and subscriptions:
        current = next((s for s in subscriptions if s.get("is_current")), None)
        if current:
            session["subscription_id"] = current["id"]

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
        type_colors_json=type_colors_json,
        recent_deploys=recent_deploys,
        subscriptions=subscriptions,
    )


ERROR_PAGE = """
<div class="card">
    <h1>{{ title }}</h1>
    <div class="error">{{ message }}</div>
    <a href="{{ back_url }}" class="btn btn-outline">Go back</a>
</div>
"""


COST_PAGE = """
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
    <div class="chart-wrap"><canvas id="barChart"></canvas></div>
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


@app.route("/set-subscription", methods=["POST"])
def set_subscription():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    sub_id = request.form.get("subscription_id", "")
    if sub_id:
        session["subscription_id"] = sub_id
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
