/* FX Recovery Dashboard - Common JS utilities */

// Format currency
function formatCurrency(amount) {
    return '$' + Number(amount).toLocaleString('en-US', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    });
}

// Format percentage
function formatPct(pct) {
    return Number(pct).toFixed(2) + '%';
}

// Format date
function formatDate(dateStr) {
    if (!dateStr) return '--';
    return new Date(dateStr).toLocaleDateString('en-US', {
        year: 'numeric', month: 'short', day: 'numeric'
    });
}
