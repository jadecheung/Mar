// Hormuz Premium Tracker - Dashboard JavaScript

const REFRESH_INTERVAL_MS = 60000; // refresh every 60 seconds

function formatCurrency(value) {
    if (value >= 1_000_000) return '$' + (value / 1_000_000).toFixed(1) + 'M';
    if (value >= 1_000) return '$' + (value / 1_000).toFixed(0) + 'K';
    return '$' + value.toFixed(0);
}

function formatDate(isoStr) {
    const d = new Date(isoStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// --------------- KPI Cards ---------------

async function loadCurrentRate() {
    try {
        const resp = await fetch('/api/rates/latest');
        if (!resp.ok) throw new Error('No rates');
        const data = await resp.json();

        document.getElementById('current-rate').textContent = data.rate_percent.toFixed(3) + '%';
        document.getElementById('rate-source').textContent =
            'Source: ' + (data.source || 'Market data') + ' | ' + formatDate(data.date);

        // Calculate VLCC cost
        const vlccValue = 120_000_000;
        const cost = vlccValue * (data.rate_percent / 100);
        document.getElementById('vlcc-cost').textContent = formatCurrency(cost);

        return data;
    } catch (e) {
        document.getElementById('current-rate').textContent = 'N/A';
        return null;
    }
}

async function loadRateHistory() {
    try {
        const resp = await fetch('/api/rates?vessel_type=standard');
        if (!resp.ok) return [];
        const rates = await resp.json();

        // Data point count
        document.getElementById('data-count').textContent = rates.length;
        if (rates.length > 1) {
            document.getElementById('date-range').textContent =
                formatDate(rates[0].date) + ' \u2014 ' + formatDate(rates[rates.length - 1].date);
        }

        // Change indicator
        if (rates.length >= 2) {
            const latest = rates[rates.length - 1].rate_percent;
            const prev = rates[rates.length - 2].rate_percent;
            const change = latest - prev;
            const el = document.getElementById('rate-change');
            if (change > 0) {
                el.className = 'change-indicator up';
                el.textContent = '\u25B2 +' + change.toFixed(3) + '% from previous';
            } else if (change < 0) {
                el.className = 'change-indicator down';
                el.textContent = '\u25BC ' + change.toFixed(3) + '% from previous';
            } else {
                el.className = 'change-indicator neutral';
                el.textContent = '\u2014 No change from previous';
            }
        }

        return rates;
    } catch (e) {
        return [];
    }
}

async function loadRiskLevel() {
    try {
        const resp = await fetch('/api/risk');
        const data = await resp.json();

        const el = document.getElementById('risk-level');
        el.textContent = (data.level || 'HIGH').toUpperCase();
        el.className = 'big-number risk-' + (data.level || 'high').toLowerCase();

        const factorsEl = document.getElementById('risk-factors');
        factorsEl.innerHTML = '';
        (data.factors || []).forEach(f => {
            const li = document.createElement('li');
            li.textContent = f;
            factorsEl.appendChild(li);
        });
    } catch (e) {
        document.getElementById('risk-level').textContent = 'N/A';
    }
}

// --------------- Chart ---------------

let rateChart = null;

function renderChart(rates) {
    const ctx = document.getElementById('rate-chart').getContext('2d');

    const labels = rates.map(r => new Date(r.date));
    const values = rates.map(r => r.rate_percent);

    if (rateChart) {
        rateChart.data.labels = labels;
        rateChart.data.datasets[0].data = values;
        rateChart.update();
        return;
    }

    rateChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'War Risk Premium (%)',
                data: values,
                borderColor: '#ffa726',
                backgroundColor: 'rgba(255, 167, 38, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointRadius: 4,
                pointBackgroundColor: '#ffa726',
                pointBorderColor: '#0f1923',
                pointBorderWidth: 2,
                pointHoverRadius: 7,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#1a2737',
                    borderColor: '#4fc3f7',
                    borderWidth: 1,
                    titleColor: '#e0e6ed',
                    bodyColor: '#e0e6ed',
                    callbacks: {
                        label: function(ctx) {
                            return 'Premium: ' + ctx.parsed.y.toFixed(3) + '%';
                        },
                        afterLabel: function(ctx) {
                            const rate = rates[ctx.dataIndex];
                            const vlccCost = 120_000_000 * (rate.rate_percent / 100);
                            return 'VLCC cost: ' + formatCurrency(vlccCost) +
                                (rate.source ? '\nSource: ' + rate.source : '');
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'month',
                        displayFormats: { month: 'MMM yyyy' }
                    },
                    grid: { color: 'rgba(42,58,74,0.5)' },
                    ticks: { color: '#8899aa' }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(42,58,74,0.5)' },
                    ticks: {
                        color: '#8899aa',
                        callback: function(val) { return val.toFixed(2) + '%'; }
                    },
                    title: {
                        display: true,
                        text: '% of Hull Value',
                        color: '#8899aa'
                    }
                }
            }
        }
    });
}

// --------------- News feed ---------------

async function loadNews() {
    try {
        const resp = await fetch('/api/news?limit=20');
        const news = await resp.json();

        const feed = document.getElementById('news-feed');
        if (news.length === 0) {
            feed.innerHTML = '<div style="color:var(--text-secondary);font-size:0.85rem;">No news yet. Use the admin panel to add news or trigger a scrape.</div>';
            return;
        }

        feed.innerHTML = news.map(n => `
            <div class="news-item">
                <div class="news-title">
                    ${n.url ? '<a href="' + n.url + '" target="_blank">' + escapeHtml(n.title) + '</a>' : escapeHtml(n.title)}
                </div>
                <div class="news-meta">
                    <span>${formatDate(n.date)}</span>
                    <span>${escapeHtml(n.source)}</span>
                    <span class="impact-badge ${n.impact}">${n.impact}</span>
                </div>
            </div>
        `).join('');
    } catch (e) {
        document.getElementById('news-feed').innerHTML =
            '<div style="color:var(--text-secondary);">Failed to load news.</div>';
    }
}

// --------------- Cost table ---------------

async function loadCosts() {
    try {
        const resp = await fetch('/api/costs');
        const costs = await resp.json();

        const tbody = document.getElementById('cost-table-body');
        tbody.innerHTML = costs.map(c => `
            <tr>
                <td>${escapeHtml(c.vessel_type)}</td>
                <td>${formatCurrency(c.hull_value_usd)}</td>
                <td>${c.premium_rate_pct.toFixed(3)}%</td>
                <td class="cost-value">${formatCurrency(c.premium_usd)}</td>
            </tr>
        `).join('');
    } catch (e) {
        // Silently fail
    }
}

// --------------- Helpers ---------------

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str || '';
    return div.innerHTML;
}

// --------------- Init ---------------

async function refreshAll() {
    await Promise.all([
        loadCurrentRate(),
        loadRiskLevel(),
        loadNews(),
        loadCosts(),
    ]);

    const rates = await loadRateHistory();
    if (rates.length > 0) {
        renderChart(rates);
    }

    document.getElementById('last-updated').textContent =
        'Last refreshed: ' + new Date().toLocaleTimeString();
}

// Initial load
refreshAll();

// Auto-refresh
setInterval(refreshAll, REFRESH_INTERVAL_MS);
