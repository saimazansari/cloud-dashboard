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
        var duration = 800 + Math.random() * 400;
        var start = performance.now();
        function step(now) {
            var pct = Math.min((now - start) / duration, 1);
            var eased = 1 - Math.pow(1 - pct, 4);
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
        var countEl = document.getElementById('refreshCountdown');
        if (countEl) {
            var remaining = 30 - (secs % 30);
            countEl.textContent = remaining + 's';
        }
    }, 1000);
}

function showToast(message, type) {
    type = type || 'info';
    var container = document.getElementById('toastContainer');
    if (!container) return;
    var icons = {success:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>', error:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>', info:'<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'};
    var t = document.createElement('div');
    t.className = 'toast toast-' + type;
    t.innerHTML = '<span class="toast-icon">' + (icons[type] || '') + '</span><span class="toast-msg">' + message + '</span><button class="toast-close" onclick="this.parentElement.classList.add(\'toast-out\');setTimeout(function(){this.parentElement.remove()}.bind(this),300)">&times;</button>';
    container.appendChild(t);
    setTimeout(function() { t.classList.add('toast-out'); setTimeout(function() { t.remove(); }, 300); }, 5000);
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
        options: { animation: { duration: 800, easing: 'easeOutQuart' }, plugins: { legend: { position: 'bottom', labels: { color: '#8892a6', padding: 12, font: { size: 10 } } } }, cutout: '70%', maintainAspectRatio: false }
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
            options: { animation: { duration: 1200, easing: 'easeOutQuart' }, scales: { x: { display: true, ticks: { color: '#8892a6', maxTicksLimit: 8, font: { size: 9 } }, grid: { display: false } }, y: { beginAtZero: true, ticks: { color: '#8892a6', font: { size: 9 }, callback: function(v) { return '$' + v.toFixed(0); } }, grid: { color: 'rgba(255,255,255,0.03)' } } }, plugins: { legend: { display: false } }, maintainAspectRatio: false }
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
(function() {
    var glow = document.getElementById('cursorGlow');
    if (glow) {
        var ticking = false;
        document.addEventListener('mousemove', function(e) {
            if (!ticking) {
                requestAnimationFrame(function() {
                    glow.style.left = e.clientX + 'px';
                    glow.style.top = e.clientY + 'px';
                    ticking = false;
                });
                ticking = true;
            }
        });
        document.addEventListener('mouseleave', function() { glow.style.opacity = '0'; });
        document.addEventListener('mouseenter', function() { glow.style.opacity = '1'; });
    }
    (function() {
        var colors = ['124,111,247', '56,189,248', '236,72,153', '251,191,36', '168,85,247'];
        var container = document.body;
        for (var i = 0; i < 18; i++) {
            var p = document.createElement('div');
            p.className = 'bg-particle';
            var size = 2 + Math.random() * 4;
            p.style.cssText =
                'width:' + size + 'px;height:' + size + 'px;' +
                'left:' + (Math.random() * 100) + '%;' +
                'bottom:-10px;' +
                'background:rgba(' + colors[i % colors.length] + ',' + (0.2 + Math.random() * 0.3) + ');' +
                'box-shadow:0 0 ' + (size * 2) + 'px rgba(' + colors[i % colors.length] + ',0.3);' +
                'animation:particleRise ' + (8 + Math.random() * 14) + 's linear ' + (Math.random() * 20) + 's infinite;';
            container.appendChild(p);
        }
    })();
})();
(function() {
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey || e.metaKey || e.altKey) return;
        var n = parseInt(e.key);
        if (n >= 1 && n <= 6) {
            var cards = document.querySelectorAll('.stat-card');
            if (cards[n-1]) {
                cards[n-1].scrollIntoView({behavior:'smooth', block:'center'});
                cards[n-1].style.transform = 'scale(1.02)';
                cards[n-1].style.borderColor = 'var(--primary)';
                setTimeout(function() {
                    cards[n-1].style.transform = '';
                    cards[n-1].style.borderColor = '';
                }, 800);
            }
        }
    });
})();
(function() {
    var input = document.getElementById('filterInput');
    if (input) {
        input.setAttribute('placeholder', 'Search by name, type, region...');
    }
})();
(function() {
    document.querySelectorAll('.btn:not(.btn-action)').forEach(function(btn) {
        btn.addEventListener('click', function(e) {
            var rect = btn.getBoundingClientRect();
            var r = document.createElement('span');
            r.className = 'ripple';
            var size = Math.max(rect.width, rect.height);
            r.style.width = r.style.height = size + 'px';
            r.style.left = (e.clientX - rect.left - size/2) + 'px';
            r.style.top = (e.clientY - rect.top - size/2) + 'px';
            btn.appendChild(r);
            setTimeout(function() { r.remove(); }, 700);
        });
    });
})();
(function() {
    document.querySelectorAll('.stat-card, .card').forEach(function(card) {
        card.addEventListener('mousemove', function(e) {
            var rect = card.getBoundingClientRect();
            var x = e.clientX - rect.left;
            var y = e.clientY - rect.top;
            var cx = rect.width / 2;
            var cy = rect.height / 2;
            var rotX = ((y - cy) / cy) * -3;
            var rotY = ((x - cx) / cx) * 3;
            card.style.setProperty('--rotX', rotX + 'deg');
            card.style.setProperty('--rotY', rotY + 'deg');
            card.style.transform = 'translateY(-3px) perspective(600px) rotateX(' + rotX + 'deg) rotateY(' + rotY + 'deg)';
        });
        card.addEventListener('mouseleave', function() {
            card.style.transform = '';
        });
    });
})();