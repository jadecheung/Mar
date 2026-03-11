// Iranian Strikes Tracker — Dashboard JavaScript

const REFRESH_INTERVAL_MS = 60000;

function formatDate(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatWeaponType(wt) {
    const labels = {
        'ballistic_missile': 'Ballistic Missile',
        'cruise_missile': 'Cruise Missile',
        'drone': 'Drone / UAV',
        'hypersonic': 'Hypersonic',
        'missile': 'Missile (unspec.)',
    };
    return labels[wt] || wt;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

// --------------- KPI Cards ---------------

async function loadSummary() {
    try {
        const resp = await fetch('/api/strikes/summary');
        if (!resp.ok) throw new Error('No summary');
        const data = await resp.json();

        const t = data.totals || {};
        document.getElementById('total-launched').textContent = (t.launched || 0).toLocaleString();
        document.getElementById('total-intercepted').textContent = (t.intercepted || 0).toLocaleString();
        document.getElementById('total-hit').textContent = (t.hit || 0).toLocaleString();
        document.getElementById('total-events').textContent = (data.total_events || 0) + ' strike events tracked';
        document.getElementById('intercept-rate').textContent = (t.intercept_rate || 0).toFixed(1) + '% intercept rate';
        document.getElementById('hit-rate').textContent = (t.hit_rate || 0).toFixed(1) + '% hit rate';
        document.getElementById('overall-intercept-pct').textContent = (t.intercept_rate || 0).toFixed(1) + '%';

        // Render weapon breakdown table
        renderWeaponBreakdown(data.by_type || {});
        // Render weapon type chart
        renderWeaponChart(data.by_type || {});

        return data;
    } catch (e) {
        document.getElementById('total-launched').textContent = 'N/A';
        return null;
    }
}

// --------------- Weapon Breakdown Table ---------------

function renderWeaponBreakdown(byType) {
    const tbody = document.getElementById('weapon-breakdown-body');
    const entries = Object.entries(byType).sort((a, b) => b[1].launched - a[1].launched);

    tbody.innerHTML = entries.map(([wt, d]) => `
        <tr>
            <td>${escapeHtml(formatWeaponType(wt))}</td>
            <td>${d.launched.toLocaleString()}</td>
            <td>${d.intercepted.toLocaleString()}</td>
            <td class="cost-value">${d.hit.toLocaleString()}</td>
            <td class="cost-value">${d.hit_rate.toFixed(1)}%</td>
            <td style="color:var(--accent-green)">${d.intercept_rate.toFixed(1)}%</td>
        </tr>
    `).join('');
}

// --------------- Charts ---------------

let timelineChart = null;
let weaponChart = null;

async function loadStrikesTimeline() {
    try {
        const resp = await fetch('/api/strikes?limit=500');
        if (!resp.ok) return [];
        const strikes = await resp.json();

        if (strikes.length > 0) {
            renderTimelineChart(strikes);
        }

        renderStrikeLog(strikes);
        renderRecentStrikes(strikes);

        return strikes;
    } catch (e) {
        return [];
    }
}

function renderTimelineChart(strikes) {
    const ctx = document.getElementById('strikes-timeline-chart').getContext('2d');

    // Aggregate by date
    const byDate = {};
    strikes.forEach(s => {
        const date = s.date ? s.date.split('T')[0] : '';
        if (!byDate[date]) byDate[date] = { launched: 0, intercepted: 0, hit: 0 };
        byDate[date].launched += s.launched || 0;
        byDate[date].intercepted += s.intercepted || 0;
        byDate[date].hit += s.hit || 0;
    });

    const dates = Object.keys(byDate).sort();
    const launched = dates.map(d => byDate[d].launched);
    const intercepted = dates.map(d => byDate[d].intercepted);
    const hit = dates.map(d => byDate[d].hit);

    if (timelineChart) {
        timelineChart.data.labels = dates.map(d => new Date(d));
        timelineChart.data.datasets[0].data = launched;
        timelineChart.data.datasets[1].data = intercepted;
        timelineChart.data.datasets[2].data = hit;
        timelineChart.update();
        return;
    }

    timelineChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dates.map(d => new Date(d)),
            datasets: [
                {
                    label: 'Launched',
                    data: launched,
                    backgroundColor: 'rgba(239, 83, 80, 0.7)',
                    borderColor: '#ef5350',
                    borderWidth: 1,
                },
                {
                    label: 'Intercepted',
                    data: intercepted,
                    backgroundColor: 'rgba(102, 187, 106, 0.7)',
                    borderColor: '#66bb6a',
                    borderWidth: 1,
                },
                {
                    label: 'Hit',
                    data: hit,
                    backgroundColor: 'rgba(255, 167, 38, 0.7)',
                    borderColor: '#ffa726',
                    borderWidth: 1,
                },
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#8899aa' }
                },
                tooltip: {
                    backgroundColor: '#1a2737',
                    borderColor: '#4fc3f7',
                    borderWidth: 1,
                    titleColor: '#e0e6ed',
                    bodyColor: '#e0e6ed',
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'day',
                        displayFormats: { day: 'MMM d, yyyy' }
                    },
                    grid: { color: 'rgba(42,58,74,0.5)' },
                    ticks: { color: '#8899aa' }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(42,58,74,0.5)' },
                    ticks: { color: '#8899aa' },
                    title: {
                        display: true,
                        text: 'Count',
                        color: '#8899aa'
                    }
                }
            }
        }
    });
}

function renderWeaponChart(byType) {
    const ctx = document.getElementById('weapon-type-chart').getContext('2d');

    const entries = Object.entries(byType).sort((a, b) => b[1].launched - a[1].launched);
    const labels = entries.map(([wt]) => formatWeaponType(wt));
    const hitRates = entries.map(([, d]) => d.hit_rate);
    const interceptRates = entries.map(([, d]) => d.intercept_rate);

    if (weaponChart) {
        weaponChart.data.labels = labels;
        weaponChart.data.datasets[0].data = hitRates;
        weaponChart.data.datasets[1].data = interceptRates;
        weaponChart.update();
        return;
    }

    weaponChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Hit Rate %',
                    data: hitRates,
                    backgroundColor: 'rgba(255, 167, 38, 0.7)',
                    borderColor: '#ffa726',
                    borderWidth: 1,
                },
                {
                    label: 'Intercept Rate %',
                    data: interceptRates,
                    backgroundColor: 'rgba(102, 187, 106, 0.7)',
                    borderColor: '#66bb6a',
                    borderWidth: 1,
                },
            ]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#8899aa' }
                },
                tooltip: {
                    backgroundColor: '#1a2737',
                    borderColor: '#4fc3f7',
                    borderWidth: 1,
                    titleColor: '#e0e6ed',
                    bodyColor: '#e0e6ed',
                    callbacks: {
                        label: function(ctx) {
                            return ctx.dataset.label + ': ' + ctx.parsed.x.toFixed(1) + '%';
                        }
                    }
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100,
                    grid: { color: 'rgba(42,58,74,0.5)' },
                    ticks: {
                        color: '#8899aa',
                        callback: function(val) { return val + '%'; }
                    },
                    title: {
                        display: true,
                        text: 'Percentage',
                        color: '#8899aa'
                    }
                },
                y: {
                    grid: { color: 'rgba(42,58,74,0.5)' },
                    ticks: { color: '#8899aa' }
                }
            }
        }
    });
}

// --------------- Recent Strikes Feed ---------------

function renderRecentStrikes(strikes) {
    const feed = document.getElementById('recent-strikes-feed');
    const recent = strikes.slice().sort((a, b) => (b.date || '').localeCompare(a.date || '')).slice(0, 15);

    if (recent.length === 0) {
        feed.innerHTML = '<div style="color:var(--text-secondary);font-size:0.85rem;">No strike data yet.</div>';
        return;
    }

    feed.innerHTML = recent.map(s => {
        const hitRate = s.launched > 0 ? (s.hit / s.launched * 100).toFixed(1) : '0.0';
        return `
            <div class="news-item">
                <div class="news-title">
                    ${escapeHtml(formatWeaponType(s.weapon_type))} — ${escapeHtml(s.target || 'Unknown target')}
                </div>
                <div class="news-meta">
                    <span>${formatDate(s.date)}</span>
                    <span>${s.launched} launched</span>
                    <span class="impact-badge negative">${s.hit} hit (${hitRate}%)</span>
                </div>
                <div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px;">
                    ${escapeHtml(s.notes || '')}
                </div>
            </div>
        `;
    }).join('');
}

// --------------- Full Strike Log ---------------

function renderStrikeLog(strikes) {
    const tbody = document.getElementById('strike-log-body');
    const sorted = strikes.slice().sort((a, b) => (b.date || '').localeCompare(a.date || ''));

    tbody.innerHTML = sorted.map(s => {
        const hitRate = s.launched > 0 ? (s.hit / s.launched * 100).toFixed(1) : '0.0';
        return `
            <tr>
                <td>${formatDate(s.date)}</td>
                <td>${escapeHtml(s.operation || '-')}</td>
                <td>${escapeHtml(formatWeaponType(s.weapon_type))}</td>
                <td>${escapeHtml(s.target || '-')}</td>
                <td>${s.launched}</td>
                <td style="color:var(--accent-green)">${s.intercepted}</td>
                <td class="cost-value">${s.hit}</td>
                <td class="cost-value">${hitRate}%</td>
                <td style="font-size:0.75rem;">${escapeHtml(s.source || '-')}</td>
            </tr>
        `;
    }).join('');
}

// --------------- Init ---------------

async function refreshAll() {
    await Promise.all([
        loadSummary(),
        loadStrikesTimeline(),
    ]);

    document.getElementById('last-updated').textContent =
        'Last refreshed: ' + new Date().toLocaleTimeString();
}

refreshAll();
setInterval(refreshAll, REFRESH_INTERVAL_MS);
