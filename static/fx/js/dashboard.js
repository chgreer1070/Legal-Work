/* FX Recovery Dashboard - Common JS utilities */

// HTML escape to prevent XSS when inserting into innerHTML
function esc(str) {
    if (str === null || str === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(str);
    return div.innerHTML;
}

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

// Humanize snake_case enum values (e.g. "pending_approval" -> "Pending Approval")
function humanizeStatus(s) {
    if (!s) return '';
    return String(s).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Toast notification (auto-dismiss after 4s, aria-live for screen readers)
function showToast(message, kind) {
    let host = document.querySelector('.toast-host');
    if (!host) {
        host = document.createElement('div');
        host.className = 'toast-host';
        host.setAttribute('role', 'status');
        host.setAttribute('aria-live', 'polite');
        document.body.appendChild(host);
    }
    const t = document.createElement('div');
    t.className = 'toast' + (kind ? ' toast-' + kind : '');
    t.textContent = message;
    host.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        t.style.transition = 'opacity 200ms';
        setTimeout(() => t.remove(), 200);
    }, 4000);
}

// Run an async action while a button shows loading state.
async function withButtonLoading(btn, fn) {
    if (!btn) return fn();
    btn.classList.add('is-loading');
    btn.disabled = true;
    try { return await fn(); }
    finally {
        btn.classList.remove('is-loading');
        btn.disabled = false;
    }
}
