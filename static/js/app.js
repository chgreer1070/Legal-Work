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

    // Download button
    html += `
      <div class="job-actions">
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
