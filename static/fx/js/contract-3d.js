var graphInstance = null;
var fullGraphData = null;
var filterState = {
    contract: true,
    clause: true,
    currency: true,
    obligation: true,
    alert: true,
    exposure: true
};
var highlightedNodes = new Set();
var defaultCameraZ = 400;

var NODE_TYPE_META = {
    contract:   { label: 'Contract',      color: '#0f3460' },
    clause:     { label: 'Clause',        color: '#e67e22' },
    currency:   { label: 'Currency Pair', color: '#f39c12' },
    obligation: { label: 'Obligation',    color: '#2ecc71' },
    alert:      { label: 'Alert',         color: '#e74c3c' },
    exposure:   { label: 'Exposure',      color: '#e94560' }
};

function initGraph(containerId, contractId) {
    var container = document.getElementById(containerId);
    if (!container) return;

    defaultCameraZ = contractId ? 250 : 400;

    var apiUrl = '/fx/api/contracts/graph';
    if (contractId) apiUrl += '?contract_id=' + contractId;

    fetch(apiUrl)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.error) {
                container.innerHTML = '<p style="color:#fff;text-align:center;padding:3rem">' +
                    esc(data.error) + '</p>';
                return;
            }
            fullGraphData = data;
            buildGraph(container, data);
            buildLegend();
            setTimeout(function() {
                var hint = document.getElementById('graph-hint');
                if (hint) hint.classList.add('fade');
            }, 100);
        })
        .catch(function(err) {
            console.error('Graph load error:', err);
            container.innerHTML = '<p style="color:#fff;text-align:center;padding:3rem">Failed to load graph data.</p>';
        });
}

function buildGraph(container, data) {
    graphInstance = ForceGraph3D()(container)
        .graphData(data)
        .nodeVal(function(n) { return n.val || 5; })
        .nodeColor(function(n) {
            if (highlightedNodes.size > 0 && !highlightedNodes.has(n.id)) {
                return '#333344';
            }
            return n.color || '#888';
        })
        .nodeOpacity(function(n) {
            if (highlightedNodes.size > 0 && !highlightedNodes.has(n.id)) {
                return 0.15;
            }
            return 0.9;
        })
        .nodeLabel(function(n) { return buildTooltip(n); })
        .linkWidth(function(l) {
            return l.type === 'contains' ? 2.5 : 1.2;
        })
        .linkColor(function(l) {
            if (highlightedNodes.size > 0) {
                var src = typeof l.source === 'object' ? l.source.id : l.source;
                var tgt = typeof l.target === 'object' ? l.target.id : l.target;
                if (!highlightedNodes.has(src) || !highlightedNodes.has(tgt)) {
                    return 'rgba(50,50,80,0.08)';
                }
            }
            return getLinkColor(l);
        })
        .linkOpacity(0.6)
        .linkDirectionalParticles(function(l) {
            return l.type === 'triggered' ? 3 : 0;
        })
        .linkDirectionalParticleWidth(2)
        .linkDirectionalParticleColor(function() { return '#e74c3c'; })
        .onNodeClick(function(node) { onNodeClick(node); })
        .onBackgroundClick(function() {
            clearHighlight();
            hideDetailPanel();
        })
        .backgroundColor('#0a0a1a')
        .d3AlphaDecay(0.025)
        .d3VelocityDecay(0.35)
        .warmupTicks(80)
        .cooldownTicks(150);

    graphInstance.cameraPosition({ x: 0, y: 0, z: defaultCameraZ });

    setTimeout(function() {
        if (graphInstance) graphInstance.zoomToFit(1000, 60);
    }, 2000);
}

function buildTooltip(node) {
    var meta = NODE_TYPE_META[node.type] || {};
    return '<div style="background:rgba(20,20,40,0.92);color:#eee;padding:6px 10px;' +
        'border-radius:6px;font-size:12px;max-width:220px;line-height:1.4">' +
        '<div style="color:' + (meta.color || '#aaa') + ';font-weight:700;font-size:11px;' +
        'text-transform:uppercase;letter-spacing:0.5px;margin-bottom:2px">' +
        esc(meta.label || node.type) + '</div>' +
        '<div>' + esc(node.label) + '</div></div>';
}

function getLinkColor(link) {
    switch (link.type) {
        case 'contains': return 'rgba(15,52,96,0.7)';
        case 'monitors': return 'rgba(243,156,18,0.7)';
        case 'requires': return 'rgba(46,204,113,0.5)';
        case 'triggered': return 'rgba(231,76,60,0.8)';
        case 'exposes': return 'rgba(233,69,96,0.6)';
        default: return 'rgba(150,150,150,0.4)';
    }
}

function onNodeClick(node) {
    highlightConnected(node);
    showDetailPanel(node);
    graphInstance.cameraPosition(
        { x: node.x + 80, y: node.y + 40, z: node.z + 80 },
        { x: node.x, y: node.y, z: node.z },
        1000
    );
}

function highlightConnected(node) {
    highlightedNodes.clear();
    highlightedNodes.add(node.id);
    var data = graphInstance.graphData();
    data.links.forEach(function(l) {
        var src = typeof l.source === 'object' ? l.source.id : l.source;
        var tgt = typeof l.target === 'object' ? l.target.id : l.target;
        if (src === node.id) highlightedNodes.add(tgt);
        if (tgt === node.id) highlightedNodes.add(src);
    });
    graphInstance.nodeColor(graphInstance.nodeColor());
    graphInstance.linkColor(graphInstance.linkColor());
}

function clearHighlight() {
    highlightedNodes.clear();
    if (graphInstance) {
        graphInstance.nodeColor(graphInstance.nodeColor());
        graphInstance.linkColor(graphInstance.linkColor());
    }
}

function showDetailPanel(node) {
    var panel = document.getElementById('detail-panel');
    var title = document.getElementById('panel-title');
    var content = document.getElementById('panel-content');
    var meta = NODE_TYPE_META[node.type] || {};
    var d = node.details || {};
    var html = '';

    title.textContent = meta.label || node.type;

    if (node.type === 'contract') {
        html = field('Customer', d.customer_name, true) +
            field('Reference', d.contract_reference) +
            badge('Status', d.status) +
            field('FX Clauses', d.clause_count) +
            '<a class="panel-link" href="/fx/contracts/' + parseInt(d.id) + '">View contract details</a>';
    } else if (node.type === 'clause') {
        html = field('Currency Pair', d.currency_pair, true) +
            field('Base Rate', d.base_rate ? d.base_rate.toFixed(4) : '-') +
            field('Threshold', d.threshold_pct + '%') +
            field('Review Frequency', d.review_frequency) +
            field('Adjustment Method', d.adjustment_method) +
            field('Notice Period', d.notification_period_days + ' days') +
            field('Confidence', d.confidence_score ? (d.confidence_score * 100).toFixed(0) + '%' : '-');
        if (d.clause_text) {
            html += '<div class="panel-clause-text">' + esc(d.clause_text) + '</div>';
        }
    } else if (node.type === 'alert') {
        html = field('Currency Pair', d.currency_pair, true) +
            badge('Status', d.status) +
            field('Deviation', d.deviation_pct ? d.deviation_pct.toFixed(2) + '%' : '-') +
            field('Base Rate', d.base_rate ? d.base_rate.toFixed(4) : '-') +
            field('Current Rate', d.current_rate ? d.current_rate.toFixed(4) : '-') +
            field('Exposure', d.exposure_amount ? '$' + formatNum(d.exposure_amount) : '-') +
            '<a class="panel-link" href="/fx/alerts/' + parseInt(d.id) + '">View alert details</a>';
    } else if (node.type === 'currency') {
        html = field('Currency Pair', d.currency_pair, true) +
            '<p style="color:var(--text-light);font-size:0.82rem;margin-top:0.5rem">' +
            'This node connects all clauses that monitor this currency pair.</p>';
    } else if (node.type === 'obligation') {
        html = field('Type', d.obligation, true) +
            field('Value', d.value);
    } else if (node.type === 'exposure') {
        html = field('Exposure Amount', '$' + formatNum(d.amount), true) +
            field('Currency Pair', d.currency_pair);
    }

    content.innerHTML = html;
    panel.classList.add('open');
}

function hideDetailPanel() {
    document.getElementById('detail-panel').classList.remove('open');
}

function field(label, value, large) {
    return '<div class="panel-field">' +
        '<div class="panel-field-label">' + esc(label) + '</div>' +
        '<div class="panel-field-value' + (large ? ' large' : '') + '">' +
        esc(String(value != null ? value : '-')) + '</div></div>';
}

function badge(label, value) {
    var colors = {
        triggered: '#ffeaa7;color:#856404',
        pending_approval: '#74b9ff;color:#0c5460',
        approved: '#55efc4;color:#155724',
        active: '#55efc4;color:#155724',
        sent: '#a29bfe;color:#2d1b69',
        dismissed: '#dfe6e9;color:#636e72'
    };
    var bg = colors[value] || '#dfe6e9;color:#636e72';
    return '<div class="panel-field">' +
        '<div class="panel-field-label">' + esc(label) + '</div>' +
        '<span class="panel-badge" style="background:' + bg + '">' +
        esc(String(value || '-')) + '</span></div>';
}

function formatNum(n) {
    if (n == null) return '-';
    return Number(n).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function buildLegend() {
    var container = document.getElementById('legend-items');
    if (!container) return;
    var html = '';
    var types = ['contract', 'clause', 'currency', 'obligation', 'alert', 'exposure'];
    types.forEach(function(type) {
        var meta = NODE_TYPE_META[type];
        var checked = filterState[type] ? 'checked' : '';
        html += '<label class="legend-item' + (filterState[type] ? '' : ' disabled') + '" data-type="' + type + '">' +
            '<input type="checkbox" ' + checked + ' onchange="toggleNodeType(\'' + type + '\', this.checked)">' +
            '<span class="legend-swatch" style="background:' + meta.color + '"></span>' +
            '<span>' + meta.label + '</span></label>';
    });
    container.innerHTML = html;
}

function toggleNodeType(type, visible) {
    filterState[type] = visible;
    applyFilters();

    var items = document.querySelectorAll('.legend-item[data-type="' + type + '"]');
    items.forEach(function(el) {
        if (visible) el.classList.remove('disabled');
        else el.classList.add('disabled');
    });
}

function applyFilters() {
    if (!fullGraphData || !graphInstance) return;
    var filteredNodes = fullGraphData.nodes.filter(function(n) {
        return filterState[n.type];
    });
    var nodeIds = new Set(filteredNodes.map(function(n) { return n.id; }));
    var filteredLinks = fullGraphData.links.filter(function(l) {
        return nodeIds.has(l.source.id || l.source) && nodeIds.has(l.target.id || l.target);
    });
    graphInstance.graphData({ nodes: filteredNodes, links: filteredLinks });
}

function explodeGraph() {
    if (!graphInstance) return;
    graphInstance.d3Force('charge').strength(-500);
    graphInstance.d3ReheatSimulation();
    setTimeout(function() {
        if (graphInstance) {
            graphInstance.d3Force('charge').strength(-120);
        }
    }, 3000);
}

function resetView() {
    if (!graphInstance) return;
    clearHighlight();
    hideDetailPanel();

    Object.keys(filterState).forEach(function(k) { filterState[k] = true; });
    buildLegend();

    if (fullGraphData) {
        graphInstance.graphData(fullGraphData);
    }
    graphInstance.d3Force('charge').strength(-120);
    graphInstance.cameraPosition(
        { x: 0, y: 0, z: defaultCameraZ },
        { x: 0, y: 0, z: 0 },
        1000
    );
}

function fitToView() {
    if (!graphInstance) return;
    graphInstance.zoomToFit(1000, 40);
}
