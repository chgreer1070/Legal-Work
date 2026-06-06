/* FX Recovery - Chart.js wrappers for rate and exposure charts */

const PAIR_COLORS = {
    'USD/BRL': { line: '#e74c3c', bg: 'rgba(231,76,60,0.1)' },
    'USD/MXN': { line: '#3498db', bg: 'rgba(52,152,219,0.1)' },
    'USD/CNY': { line: '#2ecc71', bg: 'rgba(46,204,113,0.1)' },
};

let rateChartInstance = null;
let exposureChartInstance = null;

async function loadRateChart() {
    const canvas = document.getElementById('rateChart');
    if (!canvas) return;

    const pairs = ['USD/BRL', 'USD/MXN', 'USD/CNY'];
    const datasets = [];

    const results = await Promise.all(pairs.map(async (pair) => {
        try {
            const resp = await fetch(`/fx/api/rates/${pair}/history?days=90`);
            return { pair, data: await resp.json() };
        } catch (e) {
            console.error(`Rate chart error for ${pair}:`, e);
            return { pair, data: [] };
        }
    }));

    for (const { pair, data } of results) {
        if (data.length === 0) continue;
        const colors = PAIR_COLORS[pair] || { line: '#95a5a6', bg: 'rgba(149,165,166,0.1)' };
        datasets.push({
            label: pair,
            data: data.map(d => ({ x: d.fetched_at, y: d.rate })),
            borderColor: colors.line,
            backgroundColor: colors.bg,
            fill: true,
            tension: 0.3,
            pointRadius: 0,
            borderWidth: 2,
        });
    }

    if (rateChartInstance) rateChartInstance.destroy();

    // Clear any prior empty-state overlay
    const wrap = canvas.parentElement;
    wrap.querySelectorAll('.chart-empty').forEach(el => el.remove());

    if (datasets.length === 0) {
        const empty = document.createElement('div');
        empty.className = 'chart-empty';
        empty.innerHTML = '<div class="empty-state-title">No rate data yet</div><div class="empty-state-hint">Click <strong>Refresh Rates</strong> to fetch the latest exchange rates.</div>';
        wrap.appendChild(empty);
        return;
    }

    rateChartInstance = new Chart(canvas, {
        type: 'line',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { intersect: false, mode: 'index' },
            scales: {
                x: {
                    type: 'time',
                    time: { unit: 'week' },
                    grid: { display: false },
                },
                y: {
                    beginAtZero: false,
                    grid: { color: '#f0f0f0' },
                },
            },
            plugins: {
                legend: { position: 'top' },
            },
        },
    });
}

async function loadExposureChart() {
    const canvas = document.getElementById('exposureChart');
    if (!canvas) return;

    try {
        const resp = await fetch('/fx/api/dashboard/exposure-by-pair');
        const data = await resp.json();

        const pairs = Object.keys(data);
        const wrap = canvas.parentElement;
        wrap.querySelectorAll('.chart-empty').forEach(el => el.remove());
        if (exposureChartInstance) { exposureChartInstance.destroy(); exposureChartInstance = null; }

        if (pairs.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'chart-empty';
            empty.innerHTML = '<div class="empty-state-title">No exposure yet</div><div class="empty-state-hint">Exposure appears once an alert is triggered for a currency pair.</div>';
            wrap.appendChild(empty);
            return;
        }

        const colors = pairs.map(p => (PAIR_COLORS[p] || { line: '#95a5a6' }).line);

        exposureChartInstance = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: pairs,
                datasets: [{
                    data: pairs.map(p => data[p]),
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff',
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' },
                },
            },
        });
    } catch (e) {
        console.error('Exposure chart error:', e);
    }
}
