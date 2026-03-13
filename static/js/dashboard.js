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

// --------------- Ship Transits ---------------

async function loadShipTransits() {
    try {
        const [summaryResp, transitsResp] = await Promise.all([
            fetch('/api/ship-transits/summary'),
            fetch('/api/ship-transits?limit=365'),
        ]);
        const summary = await summaryResp.json();
        const transits = await transitsResp.json();

        // KPI cards
        if (summary.latest) {
            document.getElementById('ships-today').textContent = summary.latest.total_ships;
            document.getElementById('ships-date').textContent = formatDate(summary.latest.date);
            document.getElementById('tankers-today').textContent = summary.latest.tankers || '--';
            document.getElementById('lng-today').textContent = summary.latest.lng_carriers || '--';
        }

        document.getElementById('ships-avg-7d').textContent = summary.avg_7d || '--';

        // Change indicator
        if (transits.length >= 2) {
            const latest = transits[transits.length - 1].total_ships;
            const prev = transits[transits.length - 2].total_ships;
            const change = latest - prev;
            const el = document.getElementById('ships-change');
            if (change > 0) {
                el.className = 'change-indicator up-good';
                el.textContent = '\u25B2 +' + change + ' from previous';
            } else if (change < 0) {
                el.className = 'change-indicator down-bad';
                el.textContent = '\u25BC ' + change + ' from previous';
            } else {
                el.className = 'change-indicator neutral';
                el.textContent = '\u2014 No change';
            }
        }

        // Render charts
        if (transits.length > 0) {
            renderShipTransitChart(transits);
            renderVesselBreakdownChart(transits[transits.length - 1]);
        }
    } catch (e) {
        document.getElementById('ships-today').textContent = 'N/A';
    }
}

let shipTransitChart = null;

function renderShipTransitChart(transits) {
    const ctx = document.getElementById('ship-transit-chart').getContext('2d');

    const labels = transits.map(t => new Date(t.date));
    const totals = transits.map(t => t.total_ships);
    const tankers = transits.map(t => t.tankers || 0);
    const lngData = transits.map(t => t.lng_carriers || 0);

    if (shipTransitChart) {
        shipTransitChart.data.labels = labels;
        shipTransitChart.data.datasets[0].data = totals;
        shipTransitChart.data.datasets[1].data = tankers;
        shipTransitChart.data.datasets[2].data = lngData;
        shipTransitChart.update();
        return;
    }

    shipTransitChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Total Ships',
                    data: totals,
                    borderColor: '#4fc3f7',
                    backgroundColor: 'rgba(79, 195, 247, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3,
                    pointRadius: 3,
                    pointBackgroundColor: '#4fc3f7',
                },
                {
                    label: 'Tankers',
                    data: tankers,
                    borderColor: '#ffa726',
                    backgroundColor: 'rgba(255, 167, 38, 0.05)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 2,
                    pointBackgroundColor: '#ffa726',
                },
                {
                    label: 'LNG Carriers',
                    data: lngData,
                    borderColor: '#66bb6a',
                    backgroundColor: 'rgba(102, 187, 106, 0.05)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.3,
                    pointRadius: 2,
                    pointBackgroundColor: '#66bb6a',
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
                        unit: 'month',
                        displayFormats: { month: 'MMM yyyy' }
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
                        text: 'Ships per Day',
                        color: '#8899aa'
                    }
                }
            }
        }
    });
}

let vesselBreakdownChart = null;

function renderVesselBreakdownChart(latest) {
    const ctx = document.getElementById('vessel-breakdown-chart').getContext('2d');

    const data = [
        latest.tankers || 0,
        latest.lng_carriers || 0,
        latest.container_ships || 0,
        latest.bulk_carriers || 0,
        latest.other || 0,
    ];
    const labels = ['Tankers', 'LNG Carriers', 'Container Ships', 'Bulk Carriers', 'Other'];
    const colors = ['#ffa726', '#66bb6a', '#4fc3f7', '#ab47bc', '#8899aa'];

    if (vesselBreakdownChart) {
        vesselBreakdownChart.data.datasets[0].data = data;
        vesselBreakdownChart.update();
        return;
    }

    vesselBreakdownChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: colors,
                borderColor: '#0f1923',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#8899aa', padding: 12 }
                },
                tooltip: {
                    backgroundColor: '#1a2737',
                    borderColor: '#4fc3f7',
                    borderWidth: 1,
                    titleColor: '#e0e6ed',
                    bodyColor: '#e0e6ed',
                    callbacks: {
                        label: function(ctx) {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = total > 0 ? ((ctx.parsed / total) * 100).toFixed(1) : 0;
                            return ctx.label + ': ' + ctx.parsed + ' (' + pct + '%)';
                        }
                    }
                }
            }
        }
    });
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
        loadShipTransits(),
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
