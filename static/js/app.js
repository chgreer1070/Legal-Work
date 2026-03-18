/* Outlook-to-PDF Converter – front-end logic */

'use strict';

// ── State ─────────────────────────────────────────────────────────────────

let fileMap = new Map();   // filename → File object (deduplication key)
let jobTimers = {};        // job_id → interval id

// ── DOM refs ──────────────────────────────────────────────────────────────

const dropZone   = document.getElementById('dropZone');
const fileInput  = document.getElementById('fileInput');
const fileQueue  = document.getElementById('fileQueue');
const fileList   = document.getElementById('fileList');
const clearBtn   = document.getElementById('clearBtn');
const convertBtn = document.getElementById('convertBtn');
const jobsPanel  = document.getElementById('jobsPanel');

// ── Drag-and-drop ─────────────────────────────────────────────────────────

dropZone.addEventListener('dragover', e => {
  e.preventDefault();
  dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  addFiles(Array.from(e.dataTransfer.files));
});
dropZone.addEventListener('click', e => {
  if (e.target === dropZone || e.target.closest('.drop-icon, .drop-primary, .drop-hint')) {
    fileInput.click();
  }
});
fileInput.addEventListener('change', () => {
  addFiles(Array.from(fileInput.files));
  fileInput.value = '';
});

// ── File queue management ─────────────────────────────────────────────────

const ALLOWED = new Set(['.msg', '.pdf', '.doc', '.docx', '.ppt', '.pptx']);

function ext(filename) {
  return filename.slice(filename.lastIndexOf('.')).toLowerCase();
}

function addFiles(files) {
  const ignored = [];
  files.forEach(f => {
    if (!ALLOWED.has(ext(f.name))) { ignored.push(f.name); return; }
    fileMap.set(f.name, f);
  });
  if (ignored.length) {
    alert(`Unsupported file type(s) ignored:\n${ignored.join('\n')}`);
  }
  renderQueue();
}

function renderQueue() {
  fileList.innerHTML = '';
  if (fileMap.size === 0) {
    fileQueue.classList.add('hidden');
    return;
  }
  fileQueue.classList.remove('hidden');

  fileMap.forEach((file, name) => {
    const e = ext(name).slice(1);   // strip leading dot
    const li = document.createElement('li');
    li.className = 'file-item';
    li.dataset.name = name;
    li.innerHTML = `
      <div class="file-icon ext-${e}">${e}</div>
      <div class="file-info">
        <div class="file-name" title="${escHtml(name)}">${escHtml(name)}</div>
        <div class="file-size">${formatBytes(file.size)}</div>
      </div>
      <button class="file-remove" title="Remove" aria-label="Remove ${escHtml(name)}">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
          <path d="M4.5 4.5l7 7M11.5 4.5l-7 7" stroke="currentColor" stroke-width="1.5"
                stroke-linecap="round"/>
        </svg>
      </button>`;
    li.querySelector('.file-remove').addEventListener('click', () => {
      fileMap.delete(name);
      renderQueue();
    });
    fileList.appendChild(li);
  });
}

clearBtn.addEventListener('click', () => { fileMap.clear(); renderQueue(); });

// ── Conversion ────────────────────────────────────────────────────────────

convertBtn.addEventListener('click', startConversion);

async function startConversion() {
  if (fileMap.size === 0) return;

  convertBtn.disabled = true;
  convertBtn.textContent = 'Uploading…';

  const fd = new FormData();
  fileMap.forEach(f => fd.append('files', f, f.name));

  let jobId;
  try {
    const res = await fetch('/convert', { method: 'POST', body: fd });
    const data = await res.json();
    if (!res.ok) { alert('Error: ' + (data.error || res.statusText)); return; }
    jobId = data.job_id;
    fileMap.clear();
    renderQueue();
    appendJobCard(jobId, data);
  } catch (err) {
    alert('Network error: ' + err.message);
  } finally {
    convertBtn.disabled = false;
    convertBtn.textContent = 'Convert to PDF';
  }

  if (jobId) pollJob(jobId);
}

// ── Job polling ───────────────────────────────────────────────────────────

function pollJob(jobId) {
  if (jobTimers[jobId]) return;
  jobTimers[jobId] = setInterval(async () => {
    try {
      const res  = await fetch(`/status/${jobId}`);
      const data = await res.json();
      updateJobCard(jobId, data);
      if (data.status !== 'processing') {
        clearInterval(jobTimers[jobId]);
        delete jobTimers[jobId];
      }
    } catch (_) { /* ignore transient errors */ }
  }, 1500);
}

// ── Job card rendering ────────────────────────────────────────────────────

function appendJobCard(jobId, data) {
  const card = document.createElement('div');
  card.className = 'job-card';
  card.id = `job-${jobId}`;
  jobsPanel.prepend(card);
  updateJobCard(jobId, { ...data, status: 'processing' });
}

function updateJobCard(jobId, data) {
  const card = document.getElementById(`job-${jobId}`);
  if (!card) return;

  const isProcessing = data.status === 'processing';
  const isDone       = data.status === 'done' || data.status === 'done_with_errors';
  const hasErrors    = (data.errors || []).length > 0;

  const badgeClass = isProcessing
    ? 'badge-processing'
    : hasErrors ? 'badge-error' : 'badge-done';
  const badgeText  = isProcessing ? 'Processing'
    : hasErrors ? 'Done (with errors)' : 'Done';

  const fileNames = (data.files || []).map(escHtml).join(', ');
  const timeStr   = data.created_at
    ? new Date(data.created_at).toLocaleTimeString()
    : '';

  let html = `
    <div class="job-header">
      ${isProcessing ? '<div class="spinner"></div>' : ''}
      <div class="job-title">${fileNames || 'Conversion job'}</div>
      <span class="job-time">${timeStr}</span>
      <span class="badge ${badgeClass}">${badgeText}</span>
    </div>`;

  if (isProcessing) {
    html += `<div class="progress-bar-wrap"><div class="progress-bar"></div></div>`;
  } else {
    // Results
    if ((data.results || []).length > 0) {
      html += `<ul class="result-list">`;
      data.results.forEach(r => {
        if (r.type === 'email') {
          html += `
            <li class="result-item">
              <div class="result-source">
                <span class="icon">✉</span>
                <span>${escHtml(r.source)}</span>
              </div>
              <div class="result-meta">
                ${r.subject ? `<span>Subject: ${escHtml(r.subject)}</span>` : ''}
                ${r.from    ? `<span>From: ${escHtml(r.from)}</span>` : ''}
                ${r.date    ? `<span>${escHtml(r.date)}</span>` : ''}
              </div>
              <div class="result-files">
                <span class="result-file-tag">${escHtml(r.email_pdf)}</span>
                ${(r.attachments || []).map(a =>
                  `<span class="result-file-tag">${escHtml(a)}</span>`).join('')}
              </div>
            </li>`;
        } else {
          html += `
            <li class="result-item">
              <div class="result-source">
                <span class="icon">📄</span>
                <span>${escHtml(r.source)}</span>
              </div>
              <div class="result-files">
                <span class="result-file-tag">${escHtml(r.pdf)}</span>
              </div>
            </li>`;
        }
      });
      html += `</ul>`;
    }

    // Errors
    if (hasErrors) {
      html += `<div class="error-list">`;
      data.errors.forEach(e => {
        html += `<div class="error-item">⚠ ${escHtml(e.file)}: ${escHtml(e.error)}</div>`;
      });
      html += `</div>`;
    }

    // Analysis results (if present)
    const analysisDiv = card.querySelector('.analysis-results');
    const existingAnalysis = analysisDiv ? analysisDiv.outerHTML : '';
    if (existingAnalysis) {
      html += existingAnalysis;
    }

    // Action buttons
    html += `
      <div class="job-actions">
        <button class="btn-secondary" onclick="runAnalysis('${jobId}')" id="analyzeBtn-${jobId}">
          Analyze with AI
        </button>
        <a href="/download/${jobId}" class="btn-primary" download>
          Download all PDFs (.zip)
        </a>
      </div>`;
  }

  card.innerHTML = html;
}

// ── Utilities ─────────────────────────────────────────────────────────────

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatBytes(bytes) {
  if (bytes < 1024)       return bytes + ' B';
  if (bytes < 1048576)    return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / 1048576).toFixed(1) + ' MB';
}

// ── AI Analysis ──────────────────────────────────────────────────────────

async function runAnalysis(jobId) {
  const btn = document.getElementById(`analyzeBtn-${jobId}`);
  if (btn) { btn.disabled = true; btn.textContent = 'Analyzing…'; }

  const card = document.getElementById(`job-${jobId}`);
  if (!card) return;

  // Remove any previous analysis
  const prev = card.querySelector('.analysis-results');
  if (prev) prev.remove();

  try {
    const res = await fetch(`/analyze/${jobId}`);
    const data = await res.json();

    if (!res.ok) {
      alert('Analysis error: ' + (data.error || res.statusText));
      return;
    }

    const container = document.createElement('div');
    container.className = 'analysis-results';

    if (data.analyses && data.analyses.length > 0) {
      data.analyses.forEach(item => {
        container.innerHTML += renderAnalysis(item.filename, item.analysis);
      });
    }

    if (data.errors && data.errors.length > 0) {
      let errHtml = '<div class="analysis-errors">';
      data.errors.forEach(e => {
        errHtml += `<div class="error-item">AI error for ${escHtml(e.filename)}: ${escHtml(e.error)}</div>`;
      });
      errHtml += '</div>';
      container.innerHTML += errHtml;
    }

    // Insert before the job-actions div
    const actions = card.querySelector('.job-actions');
    if (actions) {
      actions.parentNode.insertBefore(container, actions);
    } else {
      card.appendChild(container);
    }
  } catch (err) {
    alert('Network error during analysis: ' + err.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = 'Analyze with AI'; }
  }
}

function renderAnalysis(filename, analysis) {
  let html = `<div class="analysis-doc">`;
  html += `<div class="analysis-doc-header">${escHtml(filename)}</div>`;

  // Classification
  const cls = analysis.classification;
  if (cls) {
    html += `<div class="analysis-section">`;
    html += `<div class="analysis-label">Classification</div>`;
    html += `<div class="analysis-tags">`;
    html += `<span class="tag tag-category">${escHtml(cls.category)}</span>`;
    html += `<span class="tag tag-sub">${escHtml(cls.subcategory)}</span>`;
    html += `<span class="tag tag-sensitivity">${escHtml(cls.sensitivity)}</span>`;
    html += `<span class="tag tag-priority">${escHtml(cls.priority)}</span>`;
    html += `</div>`;
    if (cls.brief_description) {
      html += `<p class="analysis-desc">${escHtml(cls.brief_description)}</p>`;
    }
    if (cls.tags && cls.tags.length) {
      html += `<div class="analysis-tags">`;
      cls.tags.forEach(t => { html += `<span class="tag">${escHtml(t)}</span>`; });
      html += `</div>`;
    }
    html += `</div>`;
  }

  // Summary
  const sum = analysis.summary;
  if (sum) {
    html += `<div class="analysis-section">`;
    html += `<div class="analysis-label">Summary</div>`;
    html += `<p class="analysis-text">${escHtml(sum.summary)}</p>`;
    if (sum.key_points && sum.key_points.length) {
      html += `<ul class="analysis-points">`;
      sum.key_points.forEach(p => { html += `<li>${escHtml(p)}</li>`; });
      html += `</ul>`;
    }
    html += `</div>`;
  }

  // Metadata
  const meta = analysis.metadata;
  if (meta) {
    html += `<div class="analysis-section">`;
    html += `<div class="analysis-label">Extracted Metadata</div>`;
    html += `<div class="analysis-meta-grid">`;

    if (meta.parties && meta.parties.length) {
      html += `<div class="meta-field"><strong>Parties:</strong> ${meta.parties.map(escHtml).join(', ')}</div>`;
    }
    if (meta.dates && meta.dates.length) {
      html += `<div class="meta-field"><strong>Dates:</strong> `;
      html += meta.dates.map(d => `${escHtml(d.date)} (${escHtml(d.context)})`).join('; ');
      html += `</div>`;
    }
    if (meta.references && meta.references.length) {
      html += `<div class="meta-field"><strong>References:</strong> ${meta.references.map(escHtml).join(', ')}</div>`;
    }
    if (meta.monetary_values && meta.monetary_values.length) {
      html += `<div class="meta-field"><strong>Monetary Values:</strong> `;
      html += meta.monetary_values.map(m => `${escHtml(m.amount)} (${escHtml(m.context)})`).join('; ');
      html += `</div>`;
    }
    if (meta.obligations && meta.obligations.length) {
      html += `<div class="meta-field"><strong>Obligations:</strong></div>`;
      html += `<ul class="analysis-points">`;
      meta.obligations.forEach(o => { html += `<li>${escHtml(o)}</li>`; });
      html += `</ul>`;
    }
    if (meta.jurisdictions && meta.jurisdictions.length) {
      html += `<div class="meta-field"><strong>Jurisdictions:</strong> ${meta.jurisdictions.map(escHtml).join(', ')}</div>`;
    }
    html += `</div></div>`;
  }

  html += `</div>`;
  return html;
}
