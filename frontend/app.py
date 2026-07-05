from flask import Flask, session, request, redirect, render_template_string, Response
import requests
import os
import csv
import io
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

@app.after_request
def no_cache(response):
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

LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <title>CloudDash</title>
    <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%237c6ff7' stroke-width='2'%3E%3Cpath d='M22 12h-4l-3 9L9 3l-3 9H2'/%3E%3C/svg%3E">
    <link rel="preconnect" href="https://cdn.jsdelivr.net">
    {% if google_client_id %}<link rel="preconnect" href="https://accounts.google.com">{% endif %}
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
    <style>
        :root {
            --bg: #060a10;
            --sidebar-bg: #090d14;
            --card-bg: rgba(9,13,20,0.75);
            --card-border: rgba(255,255,255,0.06);
            --card-hover-border: rgba(124,111,247,0.3);
            --text: #e2e8f0;
            --text-muted: #7f8ea3;
            --text-dim: #3d4a5c;
            --primary: #7c6ff7;
            --primary-hover: #6a5cf5;
            --primary-glow: rgba(124,111,247,0.12);
            --primary-subtle: rgba(124,111,247,0.04);
            --success: #4ade80;
            --success-bg: rgba(74,222,128,0.08);
            --warning: #fbbf24;
            --warning-bg: rgba(251,191,36,0.08);
            --danger: #f87171;
            --danger-bg: rgba(248,113,113,0.08);
            --info: #38bdf8;
            --tag-bg: rgba(124,111,247,0.12);
            --tag-text: #a78bfa;
            --input-bg: rgba(9,13,20,0.75);
            --input-border: rgba(255,255,255,0.08);
            --focus-ring: rgba(124,111,247,0.25);
            --glass-bg: rgba(9,13,20,0.85);
            --glass-border: rgba(255,255,255,0.04);
            --glass-hover: rgba(255,255,255,0.06);
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.2);
            --shadow-lg: 0 8px 32px rgba(0,0,0,0.3);
            --shadow-glow: 0 0 20px rgba(124,111,247,0.08);
            --font-mono: 'SF Mono','Fira Code','Cascadia Code',monospace;
            --font-sans: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
        }
        [data-theme="light"] {
            --bg: #ffffff;
            --sidebar-bg: #f8f9fc;
            --card-bg: rgba(255,255,255,0.9);
            --card-border: rgba(0,0,0,0.06);
            --card-hover-border: rgba(124,111,247,0.25);
            --text: #0f172a;
            --text-muted: #475569;
            --text-dim: #94a3b8;
            --primary: #6d5ee0;
            --primary-hover: #5a4bd8;
            --primary-glow: rgba(109,94,224,0.12);
            --primary-subtle: rgba(109,94,224,0.06);
            --success: #16a34a;
            --success-bg: rgba(22,163,74,0.1);
            --warning: #d97706;
            --warning-bg: rgba(217,119,6,0.1);
            --danger: #dc2626;
            --danger-bg: rgba(220,38,38,0.1);
            --info: #0284c7;
            --tag-bg: rgba(109,94,224,0.1);
            --tag-text: #5a4bd8;
            --input-bg: #ffffff;
            --input-border: rgba(0,0,0,0.1);
            --focus-ring: rgba(109,94,224,0.2);
            --glass-bg: rgba(255,255,255,0.85);
            --glass-border: rgba(0,0,0,0.04);
            --glass-hover: rgba(0,0,0,0.02);
            --shadow-sm: 0 1px 3px rgba(0,0,0,0.06);
            --shadow-md: 0 4px 12px rgba(0,0,0,0.05);
            --shadow-lg: 0 8px 32px rgba(0,0,0,0.08);
            --shadow-glow: 0 0 24px rgba(109,94,224,0.1);
        }
        * { box-sizing:border-box; margin:0; padding:0; }
        body {
            font-family:var(--font-sans); background:var(--bg); color:var(--text);
            min-height:100vh; overflow-x:hidden;
            background-image:
                radial-gradient(ellipse at 15% 20%, rgba(124,111,247,0.06) 0%, transparent 55%),
                radial-gradient(ellipse at 85% 15%, rgba(56,189,248,0.04) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(168,85,247,0.03) 0%, transparent 50%),
                radial-gradient(ellipse at 20% 60%, rgba(74,222,128,0.02) 0%, transparent 40%),
                radial-gradient(ellipse at 80% 70%, rgba(251,191,36,0.02) 0%, transparent 40%);
            position:relative;
        }
        body::before, body::after {
            content:''; position:fixed; border-radius:50%; pointer-events:none; z-index:0;
            animation:floatOrb 20s ease-in-out infinite;
        }
        body::before {
            width:500px; height:500px;
            background:radial-gradient(circle, rgba(124,111,247,0.05) 0%, transparent 70%);
            top:-100px; left:-100px;
        }
        body::after {
            width:400px; height:400px;
            background:radial-gradient(circle, rgba(56,189,248,0.04) 0%, transparent 70%);
            bottom:-80px; right:-80px;
            animation-delay:-10s;
        }
        @keyframes floatOrb {
            0%,100%{transform:translate(0,0) scale(1)}
            33%{transform:translate(30px,-30px) scale(1.05)}
            66%{transform:translate(-20px,20px) scale(0.95)}
        }
        .layout, .auth-wrap { position:relative; z-index:1; }
        ::selection { background:var(--primary); color:#fff; }
        ::-webkit-scrollbar { width:5px; height:5px; }
        ::-webkit-scrollbar-track { background:transparent; }
        ::-webkit-scrollbar-thumb { background:var(--text-dim); border-radius:3px; }
        ::-webkit-scrollbar-thumb:hover { background:var(--text-muted); }
        .layout { display:flex; flex-direction:column; min-height:100vh; }
        .navbar {
            display:flex; align-items:center; gap:12px;
            padding:0 20px; height:56px;
            background:color-mix(in srgb, var(--glass-bg) 85%, transparent);
            border-bottom:1px solid var(--glass-border);
            backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
            position:sticky; top:0; z-index:50;
        }
        .navbar-brand {
            display:flex; align-items:center; gap:10px;
            font-weight:800; font-size:15px; letter-spacing:-0.3px;
            background:linear-gradient(135deg, var(--primary), #a78bfa);
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;
            background-clip:text;
            margin-right:16px; flex-shrink:0;
        }
        .navbar-brand svg { stroke:var(--primary); flex-shrink:0; }
        .navbar-nav { display:flex; align-items:center; gap:4px; flex:1; }
        .navbar-nav a {
            display:flex; align-items:center; gap:6px; padding:7px 16px;
            border-radius:8px; font-size:13px; font-weight:500;
            color:var(--text-muted); text-decoration:none;
            transition:all .2s; white-space:nowrap; position:relative;
        }
        .navbar-nav a:hover { background:var(--primary-subtle); color:var(--text); }
        .navbar-nav a.active {
            background:linear-gradient(135deg, var(--primary-glow), transparent);
            color:var(--primary); font-weight:600;
            box-shadow:inset 0 0 0 1px rgba(124,111,247,0.08);
        }
        .navbar-right { display:flex; align-items:center; gap:8px; flex-shrink:0; }
        .navbar-center { display:flex; align-items:center; justify-content:center; flex:1; }
        .sub-picker select {
            background:var(--input-bg); border:1px solid var(--input-border);
            border-radius:8px; padding:4px 28px 4px 10px; font-size:12px;
            color:var(--text-muted); max-width:220px;
            -webkit-appearance:none; appearance:none;
            cursor:pointer; font-family:var(--font-sans);
            background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%238896a6' fill='none' stroke-width='1.5'/%3E%3C/svg%3E");
            background-repeat:no-repeat; background-position:right 8px center;
            transition:border-color .15s;
        }
        .sub-picker select:hover { border-color:var(--primary); }
        .theme-toggle {
            display:flex; align-items:center; justify-content:center;
            width:34px; height:34px; border-radius:8px; font-size:16px;
            color:var(--text-muted); background:transparent; border:none;
            cursor:pointer; transition:all .2s; flex-shrink:0;
        }
        .theme-toggle:hover { background:var(--primary-subtle); color:var(--text); }
        .navbar-settings {
            display:flex; align-items:center; justify-content:center;
            width:48px; height:48px; border-radius:10px; font-size:26px;
            color:var(--text-muted); text-decoration:none; transition:all .15s;
        }
        .navbar-settings:hover { background:var(--primary-subtle); color:var(--text); }
        .navbar-user {
            display:flex; align-items:center; gap:8px;
            font-size:13px; color:var(--text-muted);
            position:relative; cursor:pointer; padding:4px 10px 4px 4px;
            border-radius:8px; transition:background .15s; outline:none;
        }
        .navbar-user:hover { background:rgba(255,255,255,0.04); }
        .navbar-user .avatar {
            width:30px; height:30px; border-radius:8px;
            background:linear-gradient(135deg, var(--primary), #a78bfa);
            color:#fff; display:flex; align-items:center; justify-content:center;
            font-size:12px; font-weight:700; box-shadow:0 0 12px rgba(124,111,247,0.25);
            pointer-events:none; transition:box-shadow .2s;
        }
        .navbar-user:hover .avatar { box-shadow:0 0 20px rgba(124,111,247,0.35); }
        .user-dropdown {
            display:none; position:absolute; top:100%; right:0; margin-top:6px;
            min-width:180px; background:var(--glass-bg); border:1px solid var(--glass-border);
            backdrop-filter:blur(24px); -webkit-backdrop-filter:blur(24px);
            border-radius:12px; padding:6px; box-shadow:var(--shadow-lg);
            z-index:1000;
        }
        .navbar-user:focus-within .user-dropdown,
        .navbar-user:hover .user-dropdown { display:block; animation:dropIn .15s ease; }
        @keyframes dropIn { from{opacity:0;transform:translateY(-4px)} to{opacity:1;transform:translateY(0)} }
        .user-dropdown a {
            display:flex; align-items:center; gap:8px; padding:8px 12px;
            border-radius:8px; font-size:13px; color:var(--text); text-decoration:none;
            transition:all .15s;
        }
        .user-dropdown a:hover { background:var(--primary-subtle); color:var(--primary); }
        .user-dropdown a:last-child { color:var(--danger); }
        .user-dropdown a:last-child:hover { background:var(--danger-bg); }
        .drop-arrow { font-size:13px; margin-left:3px; opacity:0.5; }
        .main { flex:1; }
        .content { padding:20px 28px; }
        .table-scroll { overflow-x:auto; -webkit-overflow-scrolling:touch; border-radius:10px; }
        .auth-wrap { max-width:420px; margin:60px auto; padding:0 16px; }
        .auth-card { max-width:400px; margin:12px auto 40px; padding:36px 32px 32px; }
        .auth-card.shake { animation:shake .4s ease; }
        @keyframes shake { 0%,100%{transform:translateX(0)} 20%{transform:translateX(-8px)} 40%{transform:translateX(8px)} 60%{transform:translateX(-6px)} 80%{transform:translateX(6px)} }
        .auth-form { display:flex; flex-direction:column; gap:6px; margin-bottom:8px; }
        .auth-form .form-group { margin-bottom:4px; }
        .auth-form .form-group input {
            padding:12px 16px; border-radius:10px; font-size:14px;
            transition:all .2s; width:100%;
        }
        .auth-form .form-group input:focus {
            border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring);
        }
        .pw-wrap { position:relative; }
        .pw-wrap input { padding-right:44px !important; }
        .pw-toggle {
            position:absolute; right:4px; top:50%; transform:translateY(-50%);
            background:none; border:none; color:var(--text-dim); cursor:pointer;
            padding:8px; font-size:16px; border-radius:6px; line-height:1;
            transition:color .15s;
        }
        .pw-toggle:hover { color:var(--text); }
        .auth-form .btn-primary {
            width:100%; padding:12px; font-size:15px; font-weight:600;
            justify-content:center; margin-top:6px; position:relative;
        }
        .auth-form .btn-primary .spinner {
            display:none; width:16px; height:16px; border:2px solid rgba(255,255,255,0.3);
            border-top-color:#fff; border-radius:50%; animation:spin .6s linear infinite;
            position:absolute; left:50%; margin-left:-8px;
        }
        .auth-form .btn-primary.loading .spinner { display:block; }
        .auth-form .btn-primary.loading .btn-text { visibility:hidden; }
        @keyframes spin { to{transform:rotate(360deg)} }
        .remember-row {
            display:flex; align-items:center; gap:8px; margin-top:2px; margin-bottom:4px;
        }
        .remember-row input[type="checkbox"] {
            width:16px; height:16px; accent-color:var(--primary); cursor:pointer;
            border-radius:4px; margin:0;
        }
        .remember-row label {
            font-size:13px; color:var(--text-muted); cursor:pointer; font-weight:400;
            text-transform:none; letter-spacing:0; margin:0;
        }
        .auth-divider { display:flex; align-items:center; gap:12px; margin:16px 0; color:var(--text-dim); font-size:12px; }
        .auth-divider::before, .auth-divider::after { content:''; flex:1; height:1px; background:var(--card-border); }
        .auth-footer { text-align:center; margin-top:20px; font-size:13px; color:var(--text-muted); }
        .auth-footer a { color:var(--primary); text-decoration:none; font-weight:600; transition:color .15s; }
        .auth-footer a:hover { color:var(--primary-hover); text-decoration:underline; }
        .social-login { display:flex; flex-direction:column; align-items:stretch; gap:10px; }
        .btn-social { display:inline-flex; align-items:center; justify-content:center; gap:10px; padding:10px 20px; border-radius:10px; font-size:14px; font-weight:600; text-decoration:none; transition:all .2s; cursor:pointer; border:1px solid var(--card-border); background:var(--input-bg); color:var(--text); width:100%; }
        .btn-social:hover { border-color:var(--primary); background:var(--primary-subtle); transform:translateY(-1px); }
        .btn-github { border-color:rgba(124,111,247,0.3); background:#2a1f5e; color:#e6e6e6; height:44px; box-sizing:border-box; }
        .btn-github:hover { border-color:var(--primary); background:rgba(124,111,247,0.2); }
        .btn-github svg { flex-shrink:0; }
        .g_id_signin { width:100%; }
        .g_id_signin > * { width:100% !important; height:44px !important; }
        .card {
            background:var(--glass-bg);
            border:1px solid var(--glass-border);
            backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
            border-radius:14px; padding:20px; margin-bottom:20px;
            position:relative; transition:all .3s cubic-bezier(.22,1,.36,1);
            box-shadow:var(--shadow-sm);
        }
        .card:hover {
            border-color:var(--card-hover-border);
            box-shadow:var(--shadow-lg), var(--shadow-glow);
            transform:translateY(-1px);
        }
        .card::before {
            content:''; position:absolute; top:0; left:0; right:0;
            height:1px;
            background:linear-gradient(90deg, transparent, rgba(124,111,247,0.2), transparent);
            opacity:0; transition:opacity .4s;
        }
        .card:hover::before { opacity:1; }
        .card::after {
            content:''; position:absolute; inset:0;
            border-radius:14px;
            background:linear-gradient(135deg, rgba(124,111,247,0.03), transparent 50%);
            opacity:0; transition:opacity .4s;
            pointer-events:none;
        }
        .card:hover::after { opacity:1; }
        h1 { font-size:22px; font-weight:700; margin-bottom:12px; letter-spacing:-0.5px; color:var(--text); }
        h2 { font-size:11px; font-weight:700; color:var(--text-muted); margin-bottom:14px; letter-spacing:0.6px; text-transform:uppercase; }
        table { width:100%; border-collapse:separate; border-spacing:0; }
        th {
            padding:12px 14px; text-align:left; font-size:10px; font-weight:700;
            color:var(--text-dim); text-transform:uppercase; letter-spacing:0.7px;
            border-bottom:1px solid var(--glass-border); background:transparent;
            position:sticky; top:0; z-index:2;
        }
        td { padding:14px 14px; border-bottom:1px solid rgba(255,255,255,0.02); font-size:13px; }
        tbody tr { transition:all .15s; cursor:pointer; }
        tbody tr:hover { background:rgba(124,111,247,0.03); }
        tbody tr:active { background:rgba(124,111,247,0.06); }
        tbody tr:last-child td { border-bottom:none; }
        tbody tr:nth-child(even) { background:rgba(255,255,255,0.01); }
        tbody tr:nth-child(even):hover { background:rgba(124,111,247,0.03); }
        .btn {
            display:inline-flex; align-items:center; gap:6px;
            padding:9px 20px; border-radius:10px; font-size:13px; font-weight:600;
            cursor:pointer; border:none; text-decoration:none; transition:all .2s;
        }
        .btn-primary {
            background:linear-gradient(135deg, var(--primary), #8b7bf7);
            color:#fff; box-shadow:0 2px 10px rgba(124,111,247,0.25);
        }
        .btn-primary:hover {
            background:linear-gradient(135deg, var(--primary-hover), #7c6ff7);
            box-shadow:0 4px 20px rgba(124,111,247,0.35);
            transform:translateY(-1px);
        }
        .btn-outline { background:transparent; color:var(--text-muted); border:1px solid var(--input-border); }
        .btn-outline:hover { border-color:var(--primary); color:var(--primary); box-shadow:0 0 16px var(--primary-glow); }
        .btn-sm { padding:6px 14px; font-size:12px; border-radius:8px; }
        .btn-action { padding:5px 12px; font-size:11px; border-radius:8px; cursor:pointer; font-weight:600; border:1px solid var(--glass-border); background:var(--glass-bg); color:var(--text-muted); transition:all .15s; }
        .btn-action:hover { border-color:var(--primary); color:var(--primary); background:var(--primary-subtle); }
        .btn-action.start:hover { border-color:var(--success); color:var(--success); background:var(--success-bg); }
        .btn-action.stop:hover { border-color:var(--danger); color:var(--danger); background:var(--danger-bg); }
        .row-actions { display:flex; gap:4px; }
        .grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:16px; }
        .grid-4 { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
        .grid-6 { display:grid; grid-template-columns:repeat(6,1fr); gap:12px; margin-bottom:20px; }
        .stat-card {
            padding:18px 20px; border-radius:14px;
            border:1px solid var(--glass-border);
            background:var(--glass-bg);
            backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px);
            position:relative; overflow:hidden;
            transition:all .3s cubic-bezier(.22,1,.36,1);
            box-shadow:var(--shadow-sm);
        }
        .stat-card:hover {
            border-color:var(--card-hover-border);
            box-shadow:var(--shadow-lg), var(--shadow-glow);
            transform:translateY(-2px);
        }
        .stat-card .stat-icon { font-size:24px; margin-bottom:12px; opacity:0.8; }
        .stat-value {
            font-size:26px; font-weight:800; letter-spacing:-0.8px;
            font-family:var(--font-mono); line-height:1.1;
        }
        .stat-label {
            font-size:11px; color:var(--text-muted); margin-top:6px;
            font-weight:600; text-transform:uppercase; letter-spacing:0.6px;
        }
        .stat-sub { font-size:11px; color:var(--text-dim); margin-top:6px; font-family:var(--font-mono); }
        .stat-card.g1 .stat-value { color:var(--primary); }
        .stat-card.g2 .stat-value { color:var(--success); }
        .stat-card.g3 .stat-value { color:var(--warning); }
        .stat-card.g5 .stat-value { color:#06b6d4; }
        .stat-card.g6 .stat-value { color:#a78bfa; }
        .stat-card::before {
            content:''; position:absolute; bottom:0; left:0; right:0;
            height:3px;
        }
        .stat-card.g1::before { background:linear-gradient(90deg, var(--primary), rgba(124,111,247,0.3)); }
        .stat-card.g2::before { background:linear-gradient(90deg, var(--success), rgba(74,222,128,0.3)); }
        .stat-card.g3::before { background:linear-gradient(90deg, var(--warning), rgba(251,191,36,0.3)); }
        .stat-card.g4::before { background:linear-gradient(90deg, var(--info), rgba(56,189,248,0.3)); }
        .stat-card.g5::before { background:linear-gradient(90deg, #06b6d4, rgba(6,182,212,0.3)); }
        .stat-card.g6::before { background:linear-gradient(90deg, #a78bfa, rgba(167,139,250,0.3)); }
        .stat-card::after {
            content:''; position:absolute; top:0; right:0;
            width:160px; height:160px; border-radius:50%;
            opacity:0.03; transform:translate(40%,-40%);
            transition:opacity .5s; pointer-events:none;
        }
        .stat-card:hover::after { opacity:0.07; }
        .stat-card.g1::after { background:var(--primary); }
        .stat-card.g2::after { background:var(--success); }
        .stat-card.g3::after { background:var(--warning); }
        .stat-card.g4::after { background:var(--info); }
        .stat-card.g5::after { background:#06b6d4; }
        .stat-card.g6::after { background:#a78bfa; }
        .chart-wrap { max-width:360px; margin:0 auto; }
        .badge {
            display:inline-flex; align-items:center; gap:5px;
            padding:4px 12px; border-radius:20px;
            font-size:11px; font-weight:600; letter-spacing:0.2px;
            border:1px solid transparent;
        }
        .badge-success { background:var(--success-bg); color:var(--success); border-color:rgba(74,222,128,0.1); }
        .badge-warning { background:var(--warning-bg); color:var(--warning); border-color:rgba(251,191,36,0.1); }
        .badge-danger { background:var(--danger-bg); color:var(--danger); border-color:rgba(248,113,113,0.1); }
        .badge-neutral { background:rgba(255,255,255,0.02); color:#7f8fa6; border-color:rgba(255,255,255,0.04); }
        .tag {
            display:inline-block; padding:2px 8px; border-radius:4px;
            font-size:11px; font-family:var(--font-mono);
            background:var(--tag-bg); color:var(--tag-text); margin:1px 2px;
        }
        .status-dot {
            display:inline-block; width:9px; height:9px; border-radius:50%;
            margin-right:6px; vertical-align:middle;
            position:relative;
        }
        .status-dot.running, .status-dot.completed { background:var(--success); box-shadow:0 0 10px rgba(74,222,128,0.5); }
        .status-dot.stopped, .status-dot.in_progress { background:var(--warning); box-shadow:0 0 10px rgba(251,191,36,0.4); }
        .status-dot.terminated, .status-dot.failed { background:var(--danger); box-shadow:0 0 10px rgba(248,113,113,0.3); }
        .status-dot.running::after { content:''; position:absolute; inset:-2px; border-radius:50%; border:1px solid rgba(74,222,128,0.2); animation:ping 2s infinite; }
        @keyframes ping { 0%{transform:scale(1);opacity:1} 100%{transform:scale(1.5);opacity:0} }
        .type-filter select {
            padding:6px 12px; border-radius:8px; font-size:12px;
            border:1px solid var(--input-border); background:var(--input-bg);
            color:var(--text); font-family:var(--font-mono); cursor:pointer;
            outline:none; margin-bottom:16px; appearance:none;
            -webkit-appearance:none;
            background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6' fill='none' stroke='%238892a6' stroke-width='1.5'/%3E%3C/svg%3E");
            background-repeat:no-repeat; background-position:right 10px center; padding-right:28px;
            transition:all .15s;
        }
        .type-filter select:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
        .filter-input {
            padding:10px 16px 10px 38px; border:1px solid var(--input-border);
            border-radius:10px; font-size:13px; background:var(--input-bg);
            color:var(--text); font-family:var(--font-sans); width:240px;
            outline:none; transition:all .2s;
            background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%233d4a5c' stroke-width='2'%3E%3Ccircle cx='11' cy='11' r='8'/%3E%3Cpath d='M21 21l-4.3-4.3'/%3E%3C/svg%3E");
            background-repeat:no-repeat; background-position:12px center;
        }
        .filter-input:focus { border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring); }
        .filter-input::placeholder { color:var(--text-dim); }
        .settings-form h2 { font-size:15px; margin-bottom:12px; color:var(--text); }
        .settings-divider { border:none; border-top:1px solid var(--card-border); margin:24px 0; }
        .success { background:var(--success-bg); color:var(--success); padding:8px 14px; border-radius:8px; font-size:13px; margin-bottom:12px; }
        .actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
        .empty { text-align:center; color:var(--text-muted); padding:64px 0; font-size:14px; }
        .empty a { color:var(--primary); text-decoration:none; }
        .empty a:hover { text-decoration:underline; }
        .error { background:var(--danger-bg); color:var(--danger); padding:12px 16px; border-radius:8px; margin-bottom:16px; font-size:13px; border:1px solid rgba(248,113,113,0.12); }
        .form-group { margin-bottom:16px; }
        .form-group label {
            display:block; font-size:11px; font-weight:600; margin-bottom:6px;
            color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px;
        }
        .form-group input, .form-group select, .form-group textarea {
            width:100%; padding:10px 14px; border:1px solid var(--input-border);
            border-radius:8px; font-size:13px; background:var(--input-bg);
            color:var(--text); outline:none; font-family:var(--font-mono);
            transition:border-color .2s, box-shadow .2s;
        }
        .form-group input:focus, .form-group select:focus, .form-group textarea:focus {
            border-color:var(--primary); box-shadow:0 0 0 3px var(--focus-ring);
        }
        .section-header {
            display:flex; justify-content:space-between; align-items:center;
            margin-bottom:20px; flex-wrap:wrap; gap:12px;
        }
        .section-header h1 { margin-bottom:0; }
        .section-header .section-subtitle {
            font-size:13px; color:var(--text-muted); margin-top:4px; margin-bottom:0;
        }
        .resource-name { font-weight:600; font-size:14px; }
        .resource-meta { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); margin-top:3px; }
        .age { font-size:11px; color:var(--text-dim); font-family:var(--font-mono); }
        .meta { color:var(--text-dim); font-size:12px; margin-bottom:16px; font-family:var(--font-mono); }
        .mono { font-family:var(--font-mono); font-size:13px; }
        .panel-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.5); z-index:50; opacity:0; pointer-events:none; transition:opacity .3s; backdrop-filter:blur(4px); -webkit-backdrop-filter:blur(4px); }
        .panel-overlay.open { opacity:1; pointer-events:auto; }
        .slide-panel {
            position:fixed; top:0; right:0; bottom:0; width:480px; max-width:90vw;
            background:var(--sidebar-bg); border-left:1px solid var(--glass-border);
            box-shadow:-8px 0 30px rgba(0,0,0,0.3);
            z-index:51; transform:translateX(100%); transition:transform .35s cubic-bezier(.22,1,.36,1);
            overflow-y:auto; padding:24px;
        }
        .slide-panel.open { transform:translateX(0); }
        .slide-panel .close-btn {
            float:right; background:none; border:none; color:var(--text-dim);
            font-size:22px; cursor:pointer; padding:4px 8px; border-radius:6px;
            transition:all .15s;
        }
        .slide-panel .close-btn:hover { color:var(--text); background:rgba(255,255,255,0.04); }
        .slide-panel h1 { font-size:18px; margin-bottom:4px; }
        .slide-panel .panel-meta { color:var(--text-dim); font-size:12px; font-family:var(--font-mono); margin-bottom:16px; }
        .slide-panel .panel-section { margin-bottom:20px; }
        .slide-panel .panel-section h2 { font-size:11px; margin-bottom:10px; letter-spacing:0.5px; }
        .slide-panel .prop-row { display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px solid rgba(255,255,255,0.03); font-size:13px; }
        .slide-panel .prop-row:last-child { border-bottom:none; }
        .slide-panel .prop-row .prop-label { color:var(--text-muted); }
        .slide-panel .prop-row .prop-value { font-family:var(--font-mono); color:var(--text); }
        .sys-bar {
            display:flex; justify-content:space-between; align-items:center;
            padding:10px 18px; margin-bottom:24px;
            background:var(--glass-bg); border:1px solid var(--glass-border);
            backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px);
            border-radius:12px; font-size:12px;
            transition:all .25s; box-shadow:var(--shadow-sm);
        }
        .sys-bar:hover { border-color:var(--card-hover-border); box-shadow:var(--shadow-md); }
        .sys-bar-left { display:flex; align-items:center; gap:10px; }
        .sys-pulse {
            width:8px; height:8px; border-radius:50%;
            background:var(--success);
            box-shadow:0 0 12px rgba(74,222,128,0.6);
            animation:pulse 2s infinite;
        }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.4} }
        .sys-text { color:var(--text-muted); font-weight:500; }
        .sys-bar-right { display:flex; align-items:center; gap:20px; }
        .sys-stat { display:flex; align-items:center; gap:6px; color:var(--text-dim); font-size:12px; }
        .sys-dot { width:6px; height:6px; border-radius:50%; }
        .sys-mono { font-family:var(--font-mono); color:var(--text-dim); font-size:11px; }
        .sub-select { background:rgba(255,255,255,0.03); border:1px solid var(--card-border); color:var(--text); font-size:11px; padding:4px 8px; border-radius:6px; cursor:pointer; max-width:180px; outline:none; transition:border-color .15s; }
        .sub-select:focus { border-color:var(--primary); }
        .sub-select option { background:#0c121c; color:var(--text); }

        /* 404 page */
        .error-page { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:60vh; text-align:center; padding:40px 20px; }
        .error-page .error-code { font-size:80px; font-weight:800; font-family:var(--font-mono); background:linear-gradient(135deg, var(--primary), #a78bfa, var(--info)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; line-height:1; margin-bottom:16px; }
        .error-page .error-icon { font-size:48px; margin-bottom:16px; opacity:0.6; }
        .error-page h2 { font-size:18px; color:var(--text); margin-bottom:8px; text-transform:none; letter-spacing:0; }
        .error-page p { color:var(--text-muted); font-size:14px; max-width:400px; margin-bottom:24px; line-height:1.5; }

        @media (max-width:900px) {
            .grid-6 { grid-template-columns:repeat(3,1fr); }
        }
        @media (max-width:768px) {
            .content { padding:16px 18px; }
            .grid-4 { grid-template-columns:repeat(2,1fr); gap:10px; }
            .grid-6 { grid-template-columns:repeat(3,1fr); gap:10px; }
            .grid-2 { grid-template-columns:1fr; }
            .chart-row { grid-template-columns:1fr; }
        }
        @media (max-width:600px) {
            .navbar-nav a span:last-child { display:none; }
            .navbar { padding:0 12px; gap:6px; }
            .navbar-brand { font-size:13px; margin-right:8px; }
            .navbar-user span { display:none; }
            .content { padding:12px 14px; }
            .grid-4 { grid-template-columns:repeat(2,1fr); gap:8px; }
            .grid-6 { grid-template-columns:repeat(2,1fr); gap:8px; }
            .stat-card { padding:14px 16px; }
            .stat-value { font-size:22px; }
            .actions .btn { font-size:11px; padding:6px 10px; }
            .filter-input { width:160px; }
            .error-page .error-code { font-size:56px; }
        }
        @media (max-width:400px) {
            .grid-4 { grid-template-columns:1fr; }
            .grid-6 { grid-template-columns:1fr; }
            .section-header { flex-direction:column; align-items:stretch; }
        }

        /* Skeleton shimmer */
        .skeleton { display:block; background:linear-gradient(90deg, var(--glass-bg) 25%, rgba(255,255,255,0.04) 50%, var(--glass-bg) 75%); background-size:200% 100%; animation:shimmer 1.5s infinite; border-radius:8px; backdrop-filter:blur(8px); }
        @keyframes shimmer { 0%{background-position:200% 0} 100%{background-position:-200% 0} }
        .skeleton-h2 { height:14px; width:120px; margin-bottom:14px; }
        .skeleton-card { height:100px; border-radius:14px; margin-bottom:16px; }
        .skeleton-stat { height:82px; border-radius:14px; }
        .skeleton-row { height:20px; margin-bottom:10px; }
        .skeleton-container { position:relative; }
        .skeleton-overlay { position:absolute; inset:0; z-index:2; display:none; background:var(--bg); border-radius:14px; padding:16px; }
        .skeleton-overlay.active { display:block; }
        .skeleton-table { width:100%; }
        .skeleton-table .skeleton-row { width:100%; }

        /* Toast notifications */
        .toast-container { position:fixed; top:64px; right:20px; z-index:100; display:flex; flex-direction:column; gap:8px; pointer-events:none; }
        .toast { display:flex; align-items:center; gap:10px; padding:12px 16px; border-radius:12px; font-size:13px; color:#fff; box-shadow:var(--shadow-lg); pointer-events:auto; animation:toastIn .3s ease; min-width:280px; max-width:400px; backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px); }
        .toast-success { background:rgba(74,222,128,0.12); border:1px solid rgba(74,222,128,0.2); color:var(--success); }
        .toast-error { background:rgba(248,113,113,0.12); border:1px solid rgba(248,113,113,0.2); color:var(--danger); }
        .toast-info { background:rgba(124,111,247,0.12); border:1px solid rgba(124,111,247,0.2); color:var(--primary); }
        .toast-icon { font-size:16px; flex-shrink:0; }
        .toast-msg { flex:1; }
        .toast-close { background:none; border:none; color:inherit; opacity:0.5; cursor:pointer; padding:2px; font-size:14px; }
        .toast-close:hover { opacity:1; }
        @keyframes toastIn { from{transform:translateX(100%);opacity:0} to{transform:translateX(0);opacity:1} }
        .toast-out { animation:toastOut .3s ease forwards; }
        @keyframes toastOut { from{transform:translateX(0);opacity:1} to{transform:translateX(100%);opacity:0} }

        /* Page fade-in */
        .content { animation:fadeIn .3s cubic-bezier(.22,1,.36,1); }
        @keyframes fadeIn { from{opacity:0;transform:translateY(12px)} to{opacity:1;transform:translateY(0)} }

        /* Copy button */
        .copy-btn { background:none; border:none; color:var(--text-dim); cursor:pointer; padding:2px 6px; border-radius:4px; font-size:11px; transition:all .15s; opacity:0.3; font-family:var(--font-mono); }
        .copy-btn:hover { opacity:1; color:var(--primary); background:var(--primary-glow); }
        tr:hover .copy-btn { opacity:0.7; }

        /* Pagination */
        .pagination { display:flex; align-items:center; gap:6px; justify-content:center; padding:20px 0 4px; }
        .pagination button { background:transparent; border:1px solid var(--glass-border); color:var(--text-muted); padding:6px 14px; border-radius:8px; cursor:pointer; font-size:12px; transition:all .15s; font-weight:500; }
        .pagination button:hover { border-color:var(--primary); color:var(--primary); background:var(--primary-subtle); }
        .pagination button.active { background:linear-gradient(135deg, var(--primary-glow), transparent); border-color:var(--primary); color:var(--primary); font-weight:600; }
        .pagination button:disabled { opacity:0.3; cursor:default; }
        .pagination .page-info { font-size:11px; color:var(--text-dim); margin:0 8px; font-family:var(--font-mono); }

        /* Sortable table headers */
        th.sortable { cursor:pointer; user-select:none; }
        th.sortable:hover { color:var(--text); }
        th.sortable .sort-arrow { display:inline-block; margin-left:4px; opacity:0.2; font-size:8px; transition:opacity .15s; }
        th.sortable:hover .sort-arrow { opacity:0.6; }
        th.sortable.asc .sort-arrow, th.sortable.desc .sort-arrow { opacity:1; color:var(--primary); }

        /* Brand login header */
        .auth-brand { text-align:center; margin-bottom:28px; }
        .auth-brand svg { margin-bottom:8px; }
        .auth-brand h1 { font-size:22px; margin:0; background:linear-gradient(135deg, var(--primary), #a78bfa); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }

        /* Chart row on dashboard */
        .chart-row { display:grid; grid-template-columns:1fr 1.5fr; gap:16px; margin-bottom:20px; }
        .chart-box {
            background:var(--glass-bg); border:1px solid var(--glass-border);
            backdrop-filter:blur(8px); -webkit-backdrop-filter:blur(8px);
            border-radius:14px; padding:20px; box-shadow:var(--shadow-sm);
        }
        .chart-box h2 { margin-bottom:12px; }
        @media (max-width:700px) { .chart-row { grid-template-columns:1fr; } }

        /* Donut center text */
        .donut-center { text-align:center; margin-top:-60px; font-size:12px; color:var(--text-dim); pointer-events:none; }
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
                <span>$</span><span>Monthly Estimate</span>
            </a>
        </div>
        <div class="navbar-center">
        </div>
        <div class="navbar-right">
            <button class="theme-toggle" id="themeToggle" onclick="var h=document.documentElement;if(h.getAttribute('data-theme')==='light'){h.removeAttribute('data-theme');try{localStorage.setItem('theme','dark')}catch(e){}this.textContent='🌙'}else{h.setAttribute('data-theme','light');try{localStorage.setItem('theme','light')}catch(e){}this.textContent='☀️'}" title="Toggle theme">🌙</button>
            <div class="navbar-user" id="userMenu" tabindex="0">
                <div class="avatar">{{ session.get('username','U')[:1].upper() }}</div>
                <span>{{ session.get('username') }} <span class="drop-arrow">▾</span></span>
                <div class="user-dropdown" id="userDropdown">
                    <a href="/settings">⚙ Settings</a>
                    <a href="/logout">⏻ Logout</a>
                </div>
            </div>
        </div>
    </nav>
    <main class="main">
        <div class="content">
            {% block content %}{% endblock %}
        </div>
    </main>
</div>
<div class="toast-container" id="toastContainer"></div>
{% else %}
<div class="auth-wrap">
    <div style="text-align:right;margin-bottom:8px;">
        <button class="theme-toggle" id="themeToggle" onclick="var h=document.documentElement;if(h.getAttribute('data-theme')==='light'){h.removeAttribute('data-theme');try{localStorage.setItem('theme','dark')}catch(e){}this.textContent='🌙'}else{h.setAttribute('data-theme','light');try{localStorage.setItem('theme','light')}catch(e){}this.textContent='☀️'}" title="Toggle theme">🌙</button>
    </div>
    {% block content %}{% endblock %}
</div>
{% endif %}
<script>
var currentPage = 1;

function statusBadge(s) {
    if (s === 'running') return 'success';
    if (s === 'stopped') return 'danger';
    if (s === 'starting') return 'info';
    if (s === 'stopping') return 'warning';
    return 'warning';
}
function actionButton(r) {
    if (r.type !== 'Virtual Machine') return '<span class="badge badge-neutral" style="font-size:11px;cursor:default;">—</span>';
    var s = r.status;
    if (s === 'running') return '<a href="/api/resources/' + r.id + '/stop-redirect" class="btn-action stop" onclick="this.textContent=\'Stopping...\';this.style.pointerEvents=\'none\';this.style.opacity=\'0.5\';">Stop</a>';
    if (s === 'stopping') return '<span class="badge badge-neutral" style="font-size:11px;cursor:default;">Stopping...</span>';
    if (s === 'starting') return '<span class="badge badge-neutral" style="font-size:11px;cursor:default;">Starting...</span>';
    return '<a href="/api/resources/' + r.id + '/start-redirect" class="btn-action start" onclick="this.textContent=\'Starting...\';this.style.pointerEvents=\'none\';this.style.opacity=\'0.5\';">Start</a>';
}

function switchSubscription(id) {
    fetch('/set-subscription', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({subscription_id: id})
    }).then(function() { location.reload(); });
}

function filterTable(inputId, tableId) {
    var query = document.getElementById(inputId).value.toLowerCase();
    var rows = document.getElementById(tableId).querySelectorAll('tbody tr');
    if (query) {
        currentPage = 1;
        rows.forEach(function(row) {
            var text = row.textContent.toLowerCase();
            row.style.display = text.includes(query) ? '' : 'none';
        });
        document.getElementById('pagination').innerHTML = '';
    } else {
        rows.forEach(function(r) { r.style.display = ''; });
        applyPagination();
    }
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

function showToast(message, type) {
    type = type || 'info';
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var icons = {success:'\u2713', error:'\u2717', info:'\u2139'};
    var t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.innerHTML = '<span class="toast-icon">' + (icons[type] || '') + '</span><span class="toast-msg">' + message + '</span><button class="toast-close" onclick="this.parentElement.classList.add(\'toast-out\');setTimeout(function(){this.parentElement.remove()}.bind(this),300)">&times;</button>';
    container.appendChild(t);
    setTimeout(function() { t.classList.add('toast-out'); setTimeout(function() { t.remove(); }, 300); }, 4000);
}

function copyId(id, btn) {
    navigator.clipboard.writeText(id).then(function() {
        btn.textContent = 'copied';
        setTimeout(function() { btn.textContent = 'copy'; }, 1500);
    });
}

function sortTable(col, th) {
    var tbody = document.querySelector('#resourceTable tbody');
    if (!tbody) return;
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var dir = th.classList.contains('asc') ? -1 : 1;
    document.querySelectorAll('#resourceTable th.sortable').forEach(function(h) { h.classList.remove('asc','desc'); });
    th.classList.add(dir === 1 ? 'asc' : 'desc');
    var text = function(r, c) { var v = r.querySelector('td:nth-child(' + c + ')'); return v ? v.textContent.trim().toLowerCase() : ''; };
    var colIdx = {name:2, type:3, region:4, cost:5, cost_inr:6, health:7, status:8, age:9};
    var idx = colIdx[col] || 2;
    rows.sort(function(a, b) {
        var va = text(a, idx), vb = text(b, idx);
        if (col === 'cost') { va = parseFloat(va.replace(/[^0-9.]/g,'')) || 0; vb = parseFloat(vb.replace(/[^0-9.]/g,'')) || 0; }
        else if (col === 'age') { va = a.querySelector('.age') ? (a.querySelector('.age').getAttribute('data-age') || '') : va; vb = b.querySelector('.age') ? (b.querySelector('.age').getAttribute('data-age') || '') : vb; }
        return va < vb ? -dir : va > vb ? dir : 0;
    });
    rows.forEach(function(r) { tbody.appendChild(r); });
    applyPagination();
}

var PAGE_SIZE = 25;
var currentPage = 1;

function applyPagination() {
    var tbody = document.querySelector('#resourceTable tbody');
    var pag = document.getElementById('pagination');
    if (!tbody || !pag) return;
    var rows = tbody.querySelectorAll('tr');
    var total = rows.length;
    var pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (currentPage > pages) currentPage = pages;
    var start = (currentPage - 1) * PAGE_SIZE;
    var end = Math.min(start + PAGE_SIZE, total);
    rows.forEach(function(r, i) { r.style.display = (i >= start && i < end) ? '' : 'none'; });
    if (total <= PAGE_SIZE) { pag.innerHTML = ''; return; }
    var h = '<button onclick="currentPage=1;applyPagination()"' + (currentPage === 1 ? ' disabled' : '') + '>&laquo;</button>';
    h += '<button onclick="currentPage=Math.max(1,currentPage-1);applyPagination()"' + (currentPage === 1 ? ' disabled' : '') + '>&lsaquo;</button>';
    h += '<span class="page-info">' + start + '-' + end + ' of ' + total + '</span>';
    h += '<button onclick="currentPage=Math.min(' + pages + ',currentPage+1);applyPagination()"' + (currentPage === pages ? ' disabled' : '') + '>&rsaquo;</button>';
    h += '<button onclick="currentPage=' + pages + ';applyPagination()"' + (currentPage === pages ? ' disabled' : '') + '>&raquo;</button>';
    pag.innerHTML = h;
}

function initCharts() {
    var types = {};
    document.querySelectorAll('#resourceTable tbody tr').forEach(function(r) { types[r.getAttribute('data-type')] = (types[r.getAttribute('data-type')] || 0) + 1; });
    var keys = Object.keys(types);
    if (keys.length < 2) return;
    document.getElementById('chartRow').style.display = 'grid';
    var colors = keys.map(function(k) { return window.typeColors[k] || '#8892a6'; });
    new Chart(document.getElementById('typeChart'), {
        type: 'doughnut',
        data: { labels: keys, datasets: [{ data: keys.map(function(k) { return types[k]; }), backgroundColor: colors, borderColor: 'var(--card-bg)', borderWidth: 2 }] },
        options: { plugins: { legend: { position: 'bottom', labels: { color: '#8892a6', padding: 12, font: { size: 10 } } } }, cutout: '70%', maintainAspectRatio: false }
    });
    document.getElementById('donutTotal').textContent = keys.reduce(function(s, k) { return s + types[k]; }, 0) + ' total';
    fetch('/api/cost-history').then(function(r) { return r.json(); }).then(function(data) {
        if (!data || !data.length) return;
        var labels = data.map(function(e) { return e.date.slice(5); });
        var values = data.map(function(e) { return e.total_cost; });
        var ctx = document.getElementById('costSparkline').getContext('2d');
        var grad = ctx.createLinearGradient(0,0,0,160);
        grad.addColorStop(0, 'rgba(124,111,247,0.3)'); grad.addColorStop(1, 'rgba(124,111,247,0)');
        new Chart(ctx, {
            type: 'line',
            data: { labels: labels, datasets: [{ label: 'Daily Cost', data: values, borderColor: '#7c6ff7', backgroundColor: grad, fill: true, tension: 0.3, pointRadius: 2, pointBackgroundColor: '#7c6ff7' }] },
            options: { scales: { x: { display: true, ticks: { color: '#8892a6', maxTicksLimit: 8, font: { size: 9 } }, grid: { display: false } }, y: { beginAtZero: true, ticks: { color: '#8892a6', font: { size: 9 }, callback: function(v) { return '$' + v.toFixed(0); } }, grid: { color: 'rgba(255,255,255,0.03)' } } }, plugins: { legend: { display: false } }, maintainAspectRatio: false }
        });
    });
}
(function() {
    var saved;
    try { saved = localStorage.getItem('theme'); } catch(e) {}
    if (!saved) saved = window.matchMedia('(prefers-color-scheme:light)').matches ? 'light' : 'dark';
    if (saved === 'light') document.documentElement.setAttribute('data-theme','light');
    var btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = saved === 'light' ? '☀️' : '🌙';
})();
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


def render_page(content, **context):
    html = LAYOUT.replace("{% block content %}{% endblock %}", content)
    return render_template_string(html, **context)


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

<div class="skeleton-container" id="statSkelContainer">
<div class="skeleton-overlay" id="statSkelOverlay">
    <div style="display:grid;grid-template-columns:repeat(6,1fr);gap:12px;">
        <div class="skeleton skeleton-stat"></div>
        <div class="skeleton skeleton-stat"></div>
        <div class="skeleton skeleton-stat"></div>
        <div class="skeleton skeleton-stat"></div>
        <div class="skeleton skeleton-stat"></div>
        <div class="skeleton skeleton-stat"></div>
    </div>
</div>
<div class="grid-6">
    <div class="stat-card g1">
        <div class="stat-icon">🖥️</div>
        <div class="stat-value"><span class="countup" data-target="{{ stats.total }}">{{ stats.total }}</span></div>
        <div class="stat-label">Total Resources</div>
    </div>
    <div class="stat-card g2">
        <div class="stat-icon">❤️</div>
        <div class="stat-value"><span class="countup" data-target="{{ health.healthy }}">{{ health.healthy }}</span></div>
        <div class="stat-label">Healthy</div>
        <div class="stat-sub"><span class="countup" data-target="{{ health.degraded }}">{{ health.degraded }}</span> degraded &middot; <span class="countup" data-target="{{ health.offline }}">{{ health.offline }}</span> offline</div>
    </div>
    <div class="stat-card g3">
        <div class="stat-icon">$</div>
        <div class="stat-value countup" data-target="{{ stats.monthly_cost }}" data-prefix="$" data-decimals="0">${{ stats.monthly_cost|int }}</div>
        <div class="stat-label">Est. Monthly Cost (USD)</div>
        <div class="stat-sub">${{ "%.2f"|format(stats.hourly_cost) }}/hr</div>
    </div>
    <div class="stat-card g4">
        <div class="stat-icon">₹</div>
        <div class="stat-value countup" data-target="{{ stats.monthly_cost_inr }}" data-prefix="₹" data-decimals="0">₹{{ stats.monthly_cost_inr|int }}</div>
        <div class="stat-label">Est. Monthly Cost (INR)</div>
        <div class="stat-sub">₹{{ "%.2f"|format(stats.hourly_cost_inr) }}/hr</div>
    </div>
    <div class="stat-card g5">
        <div class="stat-icon">📊</div>
        <div class="stat-value countup" data-target="{{ stats.cost_sofar }}" data-prefix="$" data-decimals="0">${{ stats.cost_sofar|int }}</div>
        <div class="stat-label">Cost This Month (USD)</div>
        <div class="stat-sub">${{ "%.2f"|format(stats.hourly_cost) }}/hr &middot; {{ "%d"|format(hours_sofar) }}h elapsed</div>
    </div>
    <div class="stat-card g6">
        <div class="stat-icon">₹</div>
        <div class="stat-value countup" data-target="{{ stats.cost_sofar_inr }}" data-prefix="₹" data-decimals="0">₹{{ stats.cost_sofar_inr|int }}</div>
        <div class="stat-label">Cost This Month (INR)</div>
        <div class="stat-sub">₹{{ "%.2f"|format(stats.hourly_cost_inr) }}/hr &middot; ~₹{{ stats.monthly_cost_inr|int }}/mo est.</div>
    </div>
</div>
</div>

<div class="chart-row" id="chartRow" style="display:none;">
    <div class="chart-box">
        <h2>Resource Types</h2>
        <canvas id="typeChart"></canvas>
        <div class="donut-center" id="donutTotal"></div>
    </div>
    <div class="chart-box">
        <h2>Cost Trend (30d)</h2>
        <canvas id="costSparkline" style="height:160px;"></canvas>
    </div>
</div>

<div class="card">
    <div class="section-header">
        <div>
            <h1>Infrastructure
                <span style="font-size:14px;font-weight:500;color:var(--text-dim);font-family:var(--font-mono);">
                    @{{ session.get('username') }}
                </span>
            </h1>
            <div class="section-subtitle">Monitor, manage and track your cloud resources</div>
        </div>
        <div class="actions">
            <input class="filter-input" id="filterInput"
                   placeholder="Search resources..."
                   oninput="filterTable('filterInput','resourceTable')">
            <button class="btn btn-outline btn-sm" onclick="batchAction('stop')">Stop All</button>
            <button class="btn btn-outline btn-sm" onclick="batchAction('start')">Start All</button>
            <a href="/export/csv/resources" class="btn btn-outline">CSV</a>
        </div>
    </div>

    {% if error %}<div class="error">{{ error }}</div>{% endif %}

    {% if resources %}
    <div class="skeleton-container" id="tableSkelContainer">
    <div class="skeleton-overlay" id="tableSkelOverlay">
        <div class="skeleton skeleton-h2"></div>
        <div class="skeleton skeleton-row" style="width:40%;margin-bottom:12px;"></div>
        <div class="skeleton skeleton-card" style="height:200px;"></div>
    </div>
    <div class="type-filter"><select id="typeFilter" onchange="filterByType(this.value)"><option value="">All Types</option></select></div>
    <div class="table-scroll"><table id="resourceTable">
        <thead>
            <tr>
                <th style="width:32px;">#</th>
                <th class="sortable" data-col="name">Name <span class="sort-arrow">▲</span></th>
                <th class="sortable" data-col="type">Type <span class="sort-arrow">▲</span></th>
                <th class="sortable" data-col="region">Region <span class="sort-arrow">▲</span></th>
                <th class="sortable" data-col="cost">Cost <span class="sort-arrow">▲</span></th>
                <th class="sortable" data-col="cost_inr">Cost (INR) <span class="sort-arrow">▲</span></th>
                <th class="sortable" data-col="health">Health <span class="sort-arrow">▲</span></th>
                <th class="sortable" data-col="status">Status <span class="sort-arrow">▲</span></th>
                <th class="sortable" data-col="age">Age <span class="sort-arrow">▲</span></th>
                <th style="width:100px;">Actions</th>
            </tr>
        </thead>
        <tbody>
            {% for resource in resources %}
            <tr data-type="{{ resource.type }}" data-health="{{ resource.health }}" data-id="{{ resource.id }}">
                <td class="mono" style="color:var(--text-dim);font-size:11px;">{{ loop.index }}</td>
                <td>
                    <div class="resource-name">{{ resource.name }}</div>
                    <div class="resource-meta">ID: {{ resource.id }} <button class="copy-btn" onclick="event.stopPropagation();copyId('{{ resource.id }}',this)">copy</button></div>
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
                <td class="mono" style="text-align:right;">
                    {% if resource.cost_per_hour == 0 %}
                    <span class="badge badge-neutral" style="font-size:11px;">Free</span>
                    {% else %}
                    <div>₹{{ "%.0f"|format(resource.cost_inr_per_hour * 730) }}/mo</div>
                    <div style="font-size:10px;color:var(--text-dim);">₹{{ "%.2f"|format(resource.cost_inr_per_hour) }}/hr</div>
                    {% endif %}
                </td>
                <td>
                    <span class="status-dot {{ resource.health }}"></span>
                    <span class="badge badge-{{ resource.health_class }}">{{ resource.health }}</span>
                </td>
                <td>
                    <span class="badge badge-{{ resource.status_class }}">{{ resource.status }}</span>
                </td>
                <td><span class="age" data-age="{{ resource.created_at }}">{{ resource.created_at[:10] if resource.created_at else '--' }}</span></td>
                <td>
                    <div class="row-actions">
                        {% if resource.type == 'Virtual Machine' %}
                        {% if resource.status == 'running' %}
                        <a href="/api/resources/{{ resource.id }}/stop-redirect" class="btn-action stop" onclick="this.textContent='Stopping...';this.style.pointerEvents='none';this.style.opacity='0.5';">Stop</a>
                        {% else %}
                        <a href="/api/resources/{{ resource.id }}/start-redirect" class="btn-action start" onclick="this.textContent='Starting...';this.style.pointerEvents='none';this.style.opacity='0.5';">Start</a>
                        {% endif %}
                        {% else %}
                        <span class="badge badge-neutral" style="font-size:11px;cursor:default;">—</span>
                        {% endif %}
                    </div>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table></div>
    <div class="pagination" id="pagination"></div>
    </div>
    {% else %}
    <div class="empty">
        <div style="font-size:40px;margin-bottom:12px;">⎔</div>
        <div>No infrastructure resources yet.</div>
        <div style="margin-top:16px;">
        </div>
    </div>
    {% endif %}
</div>

<script>
window.typeColors = {{ type_colors_json|safe }};
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
            document.getElementById('panelContent').innerHTML =
                '<h1>' + r.name + '</h1>' +
                '<div class="panel-meta">ID: ' + r.id + '</div>' +
                '<div class="panel-section">' +
                    '<div class="prop-row"><span class="prop-label">Type</span><span class="badge" style="background:' + (window.typeColors[r.type] || '#8892a6') + '18;color:' + (window.typeColors[r.type] || '#8892a6') + ';">' + r.type + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Region</span><span class="prop-value">' + r.region + '</span></div>' +
                    (r.resource_group ? '<div class="prop-row"><span class="prop-label">Resource Group</span><span class="prop-value mono">' + r.resource_group + '</span></div>' : '') +
                    (r.subscription_id ? '<div class="prop-row"><span class="prop-label">Subscription</span><span class="prop-value mono" style="font-size:11px;">' + r.subscription_id + '</span></div>' : '') +
                    (r.sku ? '<div class="prop-row"><span class="prop-label">SKU</span><span class="prop-value mono">' + r.sku + '</span></div>' : '') +
                    '<div class="prop-row"><span class="prop-label">Status</span><span class="badge badge-' + statusBadge(r.status) + '">' + r.status + '</span></div>' +
                    (r.cost_per_hour === 0 ? '<div class="prop-row"><span class="prop-label">Cost</span><span class="badge badge-neutral">Free</span></div>' :
                    '<div class="prop-row"><span class="prop-label">Cost/hr</span><span class="prop-value">$' + r.cost_per_hour.toFixed(4) + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Cost/mo</span><span class="prop-value">$' + (r.cost_per_hour * 730).toFixed(2) + '</span></div>') +
                    '<div class="prop-row"><span class="prop-label">Created</span><span class="prop-value">' + (r.created_at ? r.created_at.slice(0,10) : '--') + '</span></div>' +
                    '<div class="prop-row"><span class="prop-label">Updated</span><span class="prop-value">' + (r.updated_at ? r.updated_at.slice(0,10) : '--') + '</span></div>' +
                '</div>' +
                '<div class="panel-actions" style="padding:16px;display:flex;gap:8px;">' +
                    (r.status === 'running'
                        ? '<a href="/api/resources/' + r.id + '/stop-redirect" class="btn btn-primary btn-sm" style="text-decoration:none;color:#fff;" onclick="this.textContent=\'Stopping...\';this.style.pointerEvents=\'none\';this.style.opacity=\'0.5\';">Stop</a>'
                        : r.status === 'stopping'
                        ? '<span class="btn btn-primary btn-sm" style="opacity:0.5;cursor:not-allowed;">Stopping...</span>'
                        : r.status === 'starting'
                        ? '<span class="btn btn-primary btn-sm" style="opacity:0.5;cursor:not-allowed;">Starting...</span>'
                        : '<a href="/api/resources/' + r.id + '/start-redirect" class="btn btn-primary btn-sm" style="text-decoration:none;color:#fff;" onclick="this.textContent=\'Starting...\';this.style.pointerEvents=\'none\';this.style.opacity=\'0.5\';">Start</a>') +
                '</div>';
            document.getElementById('slidePanel').classList.add('open');
            document.getElementById('panelOverlay').classList.add('open');
        });
}

function closePanel() {
    document.getElementById('slidePanel').classList.remove('open');
    document.getElementById('panelOverlay').classList.remove('open');
}

document.addEventListener('DOMContentLoaded', function() {
    applyPagination();
    initCharts();
    document.getElementById('resourceTable').addEventListener('click', function(e) {
        if (e.target.closest('button') || e.target.closest('a')) return;
        var row = e.target.closest('tr[data-id]');
        if (row && !e.target.closest('input') && !e.target.closest('form'))
            openPanel(parseInt(row.getAttribute('data-id')));
    });
    document.querySelectorAll('#resourceTable th.sortable').forEach(function(th) {
        th.addEventListener('click', function() { sortTable(th.getAttribute('data-col'), th); });
    });
    startAutoRefresh();
});


function batchAction(action) {
    var ids = [];
    document.querySelectorAll('#resourceTable tbody tr').forEach(function(r) {
        if (r.getAttribute('data-type') === 'Virtual Machine') ids.push(r.getAttribute('data-id'));
    });
    if (!ids.length) return;
    fetch('/api/resources/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: action, ids: ids })
    }).then(function(r) { return r.json(); }).then(function(data) {
        if (data.error) { showToast(data.error, 'error'); return; }
        showToast('All resources ' + (action === 'stop' ? 'stopped' : 'started'), 'success');
        refreshDashboard();
    }).catch(function() { showToast('Batch action failed', 'error'); });
}
function refreshDashboard() {
    fetch('/api/resources').then(function(r) { return r.json(); }).then(function(data) {
        if (!Array.isArray(data)) return;
        var tbody = document.querySelector('#resourceTable tbody');
        if (!tbody) return;
        var html = '';
        var running = 0;
        data.forEach(function(r, i) {
            running += r.status === 'running' ? 1 : 0;
            html += '<tr data-type="' + r.type + '" data-health="' + (r.health || 'unknown') + '" data-id="' + r.id + '">' +
                '<td class="mono" style="color:var(--text-dim);font-size:11px;">' + (i+1) + '</td>' +
                '<td><div class="resource-name">' + r.name + '</div><div class="resource-meta">ID: ' + r.id + ' <button class="copy-btn" onclick="event.stopPropagation();copyId(\'' + r.id + '\',this)">copy</button></div></td>' +
                '<td><span class="badge" style="background:' + (window.typeColors[r.type] || '#8892a6') + '15;color:' + (window.typeColors[r.type] || '#8892a6') + ';">' + r.type + '</span></td>' +
                '<td class="mono">' + (r.region || '') + '</td>' +
                '<td class="mono" style="text-align:right;">' + (r.cost_per_hour === 0 ? '<span class="badge badge-neutral" style="font-size:11px;">Free</span>' : '<div>$' + (r.cost_per_hour * 730).toFixed(2) + '/mo</div><div style="font-size:10px;color:var(--text-dim);">$' + r.cost_per_hour.toFixed(4) + '/hr</div>') + '</td>' +
                '<td class="mono" style="text-align:right;">' + (r.cost_per_hour === 0 ? '<span class="badge badge-neutral" style="font-size:11px;">Free</span>' : '<div>₹' + (r.cost_per_hour * 730 * 85).toFixed(0) + '/mo</div><div style="font-size:10px;color:var(--text-dim);">₹' + (r.cost_per_hour * 85).toFixed(2) + '/hr</div>') + '</td>' +
                '<td><span class="status-dot ' + (r.health || 'unknown') + '"></span><span class="badge badge-' + ((r.health === 'healthy' || r.health === 'running') ? 'success' : (r.health === 'degraded' || r.health === 'stopped' ? 'warning' : 'danger')) + '">' + (r.health || r.status) + '</span></td>' +
                '<td><span class="badge badge-' + statusBadge(r.status) + '">' + r.status + '</span></td>' +
                '<td><span class="age" data-age="' + (r.created_at || '') + '">' + (r.created_at ? r.created_at.slice(0,10) : '--') + '</span></td>' +
                '<td><div class="row-actions">' + actionButton(r) + '</div></td></tr>';
        });
        tbody.innerHTML = html;
        document.getElementById('statResources').textContent = data.length;
        document.getElementById('statRunning').textContent = running;
        renderAges();
        applyPagination();
    }).catch(function() {});
}

function startAutoRefresh() {
    setInterval(function() {
        refreshDashboard();
        var typeSelect = document.getElementById('typeFilter');
        if (typeSelect) {
            var types = {};
            document.querySelectorAll('#resourceTable tbody tr').forEach(function(r) {
                types[r.getAttribute('data-type')] = true;
            });
            var cur = typeSelect.value;
            typeSelect.innerHTML = '<option value="">All Types</option>';
            Object.keys(types).sort().forEach(function(t) {
                typeSelect.innerHTML += '<option value="' + t + '">' + t + '</option>';
            });
            typeSelect.value = cur;
            filterByType(cur);
        }
        var el = document.getElementById('refreshTime');
        if (el) el.textContent = '0s ago';
        fetch('/api/cost-summary').then(function(r) { return r.json(); }).then(function(c) {
            if (c && c.total_monthly) {
                var el = document.querySelector('.stat-card.g3 .stat-value');
                if (el) {
                    el.setAttribute('data-target', c.total_monthly.toFixed(0));
                    el.textContent = '$' + c.total_monthly.toFixed(0);
                }
                var inrEl = document.querySelector('.stat-card.g4 .stat-value');
                if (inrEl) {
                    var inrVal = c.total_monthly * 85;
                    inrEl.setAttribute('data-target', inrVal.toFixed(0));
                    inrEl.textContent = '₹' + inrVal.toFixed(0);
                }
                var now = new Date();
                var startOfMonth = new Date(now.getFullYear(), now.getMonth(), 1);
                var hoursSoFar = (now - startOfMonth) / (1000 * 60 * 60);
                var costSoFar = (c.total_hourly || 0) * hoursSoFar;
                var usdEl = document.querySelector('.stat-card.g5 .stat-value');
                if (usdEl) {
                    usdEl.setAttribute('data-target', costSoFar.toFixed(0));
                    usdEl.textContent = '$' + costSoFar.toFixed(0);
                }
                var inrSoFar = costSoFar * 85;
                var inrSoFarEl = document.querySelector('.stat-card.g6 .stat-value');
                if (inrSoFarEl) {
                    inrSoFarEl.setAttribute('data-target', inrSoFar.toFixed(0));
                    inrSoFarEl.textContent = '₹' + inrSoFar.toFixed(0);
                }
            }
        });
    }, 30000);
}
function showSkeletons() {
    var s = document.getElementById('statSkelOverlay');
    if (s) s.classList.add('active');
    var t = document.getElementById('tableSkelOverlay');
    if (t) t.classList.add('active');
}
function hideSkeletons() {
    var s = document.getElementById('statSkelOverlay');
    if (s) s.classList.remove('active');
    var t = document.getElementById('tableSkelOverlay');
    if (t) t.classList.remove('active');
}
var _origRefresh = refreshDashboard;
refreshDashboard = function() {
    showSkeletons();
    _origRefresh();
    setTimeout(hideSkeletons, 800);
};

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

    cost_data = api_get("/api/cost-summary")
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

    sub_data = api_get("/api/subscriptions")
    subscriptions = sub_data if isinstance(sub_data, list) else []

    if not session.get("subscription_id") and subscriptions:
        current = next((s for s in subscriptions if s.get("is_current")), None)
        if current:
            session["subscription_id"] = current["id"]

    return render_page(
        DASHBOARD_PAGE,
        resources=resources,
        error=error,
        stats=stats,
        health=health,
        type_colors_json=type_colors_json,
        hours_sofar=int(hours_so_far),
    )



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
    var costColors = {{ type_colors_json|safe }};

    new Chart(document.getElementById('barChart'), {
        type: 'bar',
        data: {
            labels: breakdown.map(function(t) { return t.type; }),
            datasets: [{
                label: 'Monthly Cost',
                data: breakdown.map(function(t) { return t.total_monthly; }),
                backgroundColor: breakdown.map(function(t) { return costColors[t.type] || '#7c6ff7'; })
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

    cost_type_colors = {t["type"]: type_color(t["type"]) for t in summary.get("by_type", [])}
    cost_type_colors_json = json.dumps(cost_type_colors)

    return render_page(COST_PAGE, summary=summary, error=error, breakdown_json=breakdown_json, type_colors_json=cost_type_colors_json)


SETTINGS_PAGE = """
<div class="card" style="max-width:520px;">
    <h1 style="margin-bottom:8px;">Settings</h1>
    <p class="meta" style="margin-bottom:20px;">Manage your account preferences</p>

    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    {% if success %}<div class="success">{{ success }}</div>{% endif %}

    <form class="settings-form" id="prefsForm">
        <h2>Preferences</h2>
        <div class="form-group">
            <label>Page Size</label>
            <select name="page_size" id="prefPageSize">
                <option value="10">10 per page</option>
                <option value="25" selected>25 per page</option>
                <option value="50">50 per page</option>
                <option value="100">100 per page</option>
            </select>
        </div>
        <div class="form-group">
            <label>
                <input type="checkbox" name="auto_refresh" id="prefAutoRefresh" value="1">
                Auto-refresh dashboard every 30s
            </label>
        </div>
        <button type="button" class="btn btn-primary" onclick="savePreferences()">Save Preferences</button>
        <span id="prefStatus" style="margin-left:10px;font-size:13px;color:var(--text-dim);"></span>
    </form>
</div>
<script>
function savePreferences() {
    var prefs = {
        page_size: parseInt(document.getElementById('prefPageSize').value) || 25,
        auto_refresh: document.getElementById('prefAutoRefresh').checked
    };
    var status = document.getElementById('prefStatus');
    status.textContent = 'Saving...';
    fetch('/api/user/preferences', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(prefs)
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        status.textContent = data.error ? 'Error: ' + data.error : 'Saved!';
        if (!data.error) setTimeout(function() { status.textContent = ''; }, 2000);
    })
    .catch(function() {
        status.textContent = 'Failed to save';
    });
}

fetch('/api/user/preferences')
    .then(function(r) { return r.json(); })
    .then(function(prefs) {
        if (!prefs || prefs.error) return;
        if (prefs.page_size) document.getElementById('prefPageSize').value = prefs.page_size;
        if (prefs.auto_refresh) document.getElementById('prefAutoRefresh').checked = true;
    })
    .catch(function() {});
</script>
"""


@app.route("/settings")
def settings():
    if not session.get("user_id"):
        return redirect("/login")
    return render_page(SETTINGS_PAGE)


LOGIN_PAGE = """
<div class="card auth-card" id="loginCard">
    <div class="auth-brand">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#7c6ff7" stroke-width="1.5" style="filter:drop-shadow(0 0 12px rgba(124,111,247,0.3));"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
        <h1>CloudDash</h1>
        <p style="color:var(--text-muted);font-size:14px;margin-top:6px;font-weight:400;">Sign in to your dashboard</p>
    </div>
    {% if error %}<div class="error" id="loginError">{{ error }}</div>{% endif %}

    <form method="post" class="auth-form" id="loginForm">
        <div class="form-group">
            <label>Username</label>
            <input type="text" name="username" placeholder="Enter your username" required autocomplete="username">
        </div>
        <div class="form-group">
            <label>Password</label>
            <div class="pw-wrap">
                <input type="password" name="password" id="loginPassword" placeholder="Enter your password" required autocomplete="current-password">
                <button type="button" class="pw-toggle" onclick="togglePw(this)" tabindex="-1">👁️</button>
            </div>
        </div>
        <div class="remember-row">
            <input type="checkbox" id="rememberMe" name="remember" checked>
            <label for="rememberMe">Remember me</label>
        </div>
        <button type="submit" class="btn btn-primary" id="loginBtn">
            <span class="spinner"></span>
            <span class="btn-text">Sign In</span>
        </button>
    </form>

    {% if google_client_id or github_client_id %}
    <div class="auth-divider"><span>or continue with</span></div>

    <div class="social-login">
        {% if google_client_id %}
        <div id="g_id_onload"
             data-client_id="{{ google_client_id }}"
             data-callback="handleGoogleCredential"
             data-auto_select="false"
             data-itp_support="true">
        </div>
        <div class="g_id_signin"
             data-type="standard"
             data-theme="outline"
             data-size="large"
             data-text="sign_in_with"
             data-shape="rectangular"
             data-logo_alignment="left">
        </div>
        {% endif %}

        {% if github_client_id %}
        <a href="/auth/github" class="btn btn-social btn-github">
            <svg width="18" height="18" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
            Sign in with GitHub
        </a>
        {% endif %}
    </div>
    {% endif %}

    <p class="auth-footer">
        Don't have an account? <a href="/register">Register</a>
    </p>
</div>

<script>
function togglePw(btn) {
    var inp = btn.previousElementSibling;
    if (inp.type === 'password') { inp.type = 'text'; btn.textContent = '🙈'; }
    else { inp.type = 'password'; btn.textContent = '👁️'; }
}
document.getElementById('loginForm').addEventListener('submit', function() {
    document.getElementById('loginBtn').classList.add('loading');
});
{% if error %}
document.getElementById('loginCard').classList.add('shake');
{% endif %}
</script>

{% if google_client_id %}
<script async src="https://accounts.google.com/gsi/client"></script>
<script>
function handleGoogleCredential(response) {
    var btns = document.querySelectorAll('.g_id_signin, .btn-social, .btn-primary');
    btns.forEach(function(b) { if (b) b.style.display = 'none'; });
    fetch('/auth/google', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({credential: response.credential})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.error) {
            var errDiv = document.querySelector('.error') || document.createElement('div');
            errDiv.className = 'error';
            errDiv.textContent = data.error;
            document.querySelector('.card').insertBefore(errDiv, document.querySelector('.card').firstChild.nextSibling);
            btns.forEach(function(b) { if (b) b.style.display = ''; });
        } else {
            window.location.href = '/';
        }
    })
    .catch(function() {
        btns.forEach(function(b) { if (b) b.style.display = ''; });
    });
}
</script>
{% endif %}
"""


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
        return render_page(
            LOGIN_PAGE,
            error=result.get("error", "Login failed"),
        )
    return render_page(LOGIN_PAGE)


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
        return render_page(LOGIN_PAGE, error="GitHub sign-in is not configured")
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
        return render_page(LOGIN_PAGE, error="GitHub authorization failed: no code returned")

    result, status_code = api_post("/api/auth/github", {"code": code})
    if status_code == 200 and "token" in result:
        session["user_id"] = result["user_id"]
        session["username"] = result["username"]
        session["token"] = result["token"]
        return redirect("/")

    return render_page(LOGIN_PAGE, error=result.get("error", "GitHub sign-in failed"))


REGISTER_PAGE = """
<div class="card auth-card">
    <div class="auth-brand">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#7c6ff7" stroke-width="1.5" style="filter:drop-shadow(0 0 12px rgba(124,111,247,0.3));"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
        <h1>CloudDash</h1>
        <p style="color:var(--text-muted);font-size:14px;margin-top:6px;font-weight:400;">Create your account</p>
    </div>
    {% if error %}<div class="error">{{ error }}</div>{% endif %}
    <form method="post" class="auth-form">
        <div class="form-group">
            <label>Username</label>
            <input type="text" name="username" placeholder="Choose a username" required autocomplete="username">
        </div>
        <div class="form-group">
            <label>Password</label>
            <input type="password" name="password" placeholder="Create a password" required autocomplete="new-password">
        </div>
        <div class="form-group">
            <label>Confirm Password</label>
            <input type="password" name="confirm_password" placeholder="Repeat your password" required autocomplete="new-password">
        </div>
        <button type="submit" class="btn btn-primary">Create Account</button>
    </form>
    <p class="auth-footer">Already have an account? <a href="/login">Login</a></p>
</div>
"""


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect("/")

    if request.method == "POST":
        password = request.form["password"]
        confirm = request.form.get("confirm_password", "")

        if password != confirm:
            return render_page(REGISTER_PAGE, error="Passwords do not match")

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
        return render_page(REGISTER_PAGE, error=result.get("error", "Registration failed"))

    return render_page(REGISTER_PAGE)


@app.route("/api/resources")
def resource_list_proxy():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    data = api_get("/api/resources")
    return app.response_class(
        response=json.dumps(data),
        mimetype="application/json",
    )


@app.route("/api/resources/<int:resource_id>")
def resource_detail_proxy(resource_id):
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    data = api_get(f"/api/resources/{resource_id}")
    return app.response_class(
        response=json.dumps(data),
        mimetype="application/json",
    )


@app.route("/api/resources/<int:resource_id>/stop-redirect")
def resource_stop_redirect(resource_id):
    if not session.get("user_id"):
        return redirect("/login")
    api_post(f"/api/resources/{resource_id}/stop", {})
    return redirect("/")

@app.route("/api/resources/<int:resource_id>/start-redirect")
def resource_start_redirect(resource_id):
    if not session.get("user_id"):
        return redirect("/login")
    api_post(f"/api/resources/{resource_id}/start", {})
    return redirect("/")


@app.route("/api/resources/batch", methods=["POST"])
def resource_batch_proxy():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    data = request.get_json(force=True)
    result, status_code = api_post("/api/resources/batch", data)
    return app.response_class(
        response=json.dumps(result),
        status=status_code,
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


@app.route("/api/cost-summary")
def cost_summary_proxy():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    data = api_get("/api/cost-summary")
    return app.response_class(
        response=json.dumps(data),
        mimetype="application/json",
    )


@app.route("/api/subscriptions")
def subscriptions_proxy():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    data = api_get("/api/subscriptions")
    return app.response_class(
        response=json.dumps(data),
        mimetype="application/json",
    )


@app.route("/api/user/preferences", methods=["GET", "PUT"])
def user_preferences_proxy():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    if request.method == "PUT":
        data = request.get_json(force=True)
        result, status_code = api_put("/api/user/preferences", data)
        return app.response_class(
            response=json.dumps(result),
            status=status_code,
            mimetype="application/json",
        )
    data = api_get("/api/user/preferences")
    return app.response_class(
        response=json.dumps(data),
        mimetype="application/json",
    )


@app.route("/set-subscription", methods=["POST"])
def set_subscription():
    if not session.get("user_id"):
        return {"error": "unauthorized"}, 401
    if request.is_json:
        sub_id = request.json.get("subscription_id", "")
    else:
        sub_id = request.form.get("subscription_id", "")
    if sub_id:
        session["subscription_id"] = sub_id
    if request.is_json:
        return {"ok": True}
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
    writer.writerow(["Name", "Type", "Region", "CostPerHour", "Status"])

    for resource in resources:
        writer.writerow([
            resource["name"],
            resource["type"],
            resource["region"],
            resource["cost_per_hour"],
            resource["status"],
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


NOT_FOUND_PAGE = """
<div class="error-page">
    <div class="error-icon">☁️</div>
    <div class="error-code">404</div>
    <h2>This page drifted into the cloud</h2>
    <p>The resource you're looking for doesn't exist or has been swept away by the wind.</p>
    <a href="/" class="btn btn-primary">Back to Dashboard</a>
</div>
"""


@app.errorhandler(404)
def not_found(e):
    return render_page(NOT_FOUND_PAGE)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
