/* =============================================
   upload.js — Upload page logic
   ============================================= */

const uploadZone  = document.getElementById('uploadZone');
const fileInput   = document.getElementById('fileInput');
const procSection = document.getElementById('processingSection');
const procMsg     = document.getElementById('processingMsg');
const progressBar = document.getElementById('uploadProgress');
const resultsSection = document.getElementById('resultsSection');
const resetBtn    = document.getElementById('resetBtn');

/* ── Drag-and-drop events ── */
['dragenter','dragover'].forEach(ev =>
  uploadZone.addEventListener(ev, e => { e.preventDefault(); uploadZone.classList.add('dragover'); })
);
['dragleave','drop'].forEach(ev =>
  uploadZone.addEventListener(ev, e => { e.preventDefault(); uploadZone.classList.remove('dragover'); })
);
uploadZone.addEventListener('drop', e => {
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

/* ── Reset ── */
resetBtn?.addEventListener('click', () => {
  State.clear(STATE_KEYS.DOC_META);
  State.clear(STATE_KEYS.PARAGRAPHS);
  State.clear(STATE_KEYS.RESULTS);
  State.clear(STATE_KEYS.SESSION_ID);
  resultsSection.style.display = 'none';
  uploadZone.parentElement.style.display = '';
  procSection.style.display = 'none';
  fileInput.value = '';
  updateSidebarStatus();
  showToast('Document cleared. Upload a new file.', 'info');
});

/* ── On page load — restore if already uploaded ── */
document.addEventListener('DOMContentLoaded', () => {
  const meta  = State.get(STATE_KEYS.DOC_META);
  const paras = State.get(STATE_KEYS.PARAGRAPHS);
  if (meta && paras) {
    uploadZone.parentElement.style.display = 'none';
    renderResults(meta, paras);
  }
});

/* ── Handle file ── */
async function handleFile(file) {
  const allowed = ['application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document'];
  const extOk = /\.(pdf|docx)$/i.test(file.name);
  if (!extOk) {
    showToast('Only .pdf and .docx files are supported.', 'error');
    return;
  }
  if (file.size > 52_428_800) { // 50 MB
    showToast('File is too large. Maximum supported size is 50 MB.', 'error');
    return;
  }

  // Show progress
  uploadZone.parentElement.style.display = 'none';
  procSection.style.display = '';
  resultsSection.style.display = 'none';

  // Animate progress bar (fake 0→80% while uploading)
  let fakeProgress = 0;
  const ticker = setInterval(() => {
    fakeProgress = Math.min(fakeProgress + 3, 80);
    progressBar.style.width = fakeProgress + '%';
  }, 150);

  try {
    procMsg.textContent = `Uploading ${file.name}…`;
    const fd = new FormData();
    fd.append('file', file);
    const data = await postForm('/api/upload', fd);

    clearInterval(ticker);
    progressBar.style.width = '100%';
    procMsg.textContent = '✅ Extraction complete!';

    // Store in localStorage
    State.set(STATE_KEYS.DOC_META, {
      file_name:  data.file_name,
      file_size_kb: data.file_size_kb,
      format:     data.format,
      page_count: data.page_count,
      metadata:   data.metadata,
      text_preview: data.text_preview,
      paragraph_count: data.paragraph_count,
    });
    State.set(STATE_KEYS.PARAGRAPHS, data.paragraphs);
    // Clear old analysis when new doc uploaded
    State.clear(STATE_KEYS.RESULTS);
    State.clear(STATE_KEYS.SESSION_ID);

    await new Promise(r => setTimeout(r, 600));
    procSection.style.display = 'none';
    renderResults(data, data.paragraphs);
    updateSidebarStatus();
    showToast(`Extracted ${data.paragraph_count} paragraphs from "${data.file_name}"`, 'success');

  } catch (err) {
    clearInterval(ticker);
    procSection.style.display = 'none';
    uploadZone.parentElement.style.display = '';
    showToast('Upload failed: ' + err.message, 'error');
  }
}

/* ── Render results ── */
function renderResults(meta, paragraphs) {
  resultsSection.style.display = '';

  // Success alert
  document.getElementById('successMsg').textContent =
    `Document extracted successfully — ${meta.paragraph_count ?? paragraphs.length} paragraphs ready for analysis.`;

  // Metrics
  document.getElementById('metaName').textContent   = meta.file_name;
  document.getElementById('metaFormat').textContent = meta.format;
  document.getElementById('metaSize').textContent   = fmtSize(meta.file_size_kb);
  document.getElementById('metaParas').textContent  = meta.paragraph_count ?? paragraphs.length;

  // Text preview
  document.getElementById('textPreview').textContent =
    (meta.text_preview || '').slice(0, 2500) +
    (meta.text_preview?.length > 2500 ? '\n\n[truncated…]' : '');

  // Paragraph selector
  const sel = document.getElementById('paraSelect');
  sel.innerHTML = '';
  paragraphs.forEach((p, i) => {
    const opt = document.createElement('option');
    opt.value = i;
    opt.textContent = `Para ${i + 1} (${p.length} chars)`;
    sel.appendChild(opt);
  });
  sel.addEventListener('change', () => {
    document.getElementById('paraPreview').textContent = paragraphs[+sel.value] || '';
  });
  document.getElementById('paraPreview').textContent = paragraphs[0] || '';

  // Doc metadata
  const m = meta.metadata || {};
  const detailsEl = document.getElementById('metaDetails');
  const metaCard  = document.getElementById('metaCard');
  const items = Object.entries(m).filter(([,v]) => v);
  if (items.length) {
    detailsEl.innerHTML = items
      .map(([k, v]) => `<div><strong style="text-transform:capitalize;">${k}:</strong> ${esc(v)}</div>`)
      .join('');
    metaCard.style.display = '';
  }
}
