/* =============================================
   analyze.js — Analysis page logic (SSE)
   ============================================= */

let isRunning = false;
let startTime = null;
let collectedResults = [];

/* ── Elements ── */
const noDocAlert     = document.getElementById('noDocAlert');
const completeBanner = document.getElementById('completeBanner');
const configSection  = document.getElementById('configSection');
const docSummary     = document.getElementById('docSummary');
const settingsCard   = document.getElementById('settingsCard');
const startBtn       = document.getElementById('startBtn');
const progressSection = document.getElementById('progressSection');
const liveTableSection = document.getElementById('liveTableSection');
const liveBody       = document.getElementById('liveBody');
const maxSlider      = document.getElementById('maxSlider');
const maxNum         = document.getElementById('maxNum');

/* ── On load ── */
document.addEventListener('DOMContentLoaded', () => {
  loadModelConfig();

  const meta   = State.get(STATE_KEYS.DOC_META);
  const paras  = State.get(STATE_KEYS.PARAGRAPHS);
  const results = State.get(STATE_KEYS.RESULTS);

  if (!meta || !paras) {
    noDocAlert.style.display = '';
    configSection.style.display = 'none';
    return;
  }

  // Populate summary
  docSummary.style.display = '';
  document.getElementById('docName').textContent = meta.file_name;
  document.getElementById('docParas').textContent = paras.length;
  maxSlider.max = paras.length;

  // Already done?
  if (results && results.length) {
    showCompleteBanner(results);
    renderLiveTable(results);
    liveTableSection.style.display = '';
  } else if (State.get(STATE_KEYS.SESSION_ID)) {
    // Resume background analysis
    resumeAnalysis(State.get(STATE_KEYS.SESSION_ID));
  }
});

/* ── Load model config from server ── */
async function loadModelConfig() {
  try {
    const cfg = await fetch('/api/config').then(r => r.json());
    const el = (id) => document.getElementById(id);
    if (el('modelName'))  el('modelName').textContent  = cfg.current_model || '—';
    if (el('proxyUrl'))   el('proxyUrl').textContent   = cfg.litellm_base_url || '—';
    if (el('tempVal'))    el('tempVal').textContent     = cfg.temperature ?? '—';
    if (el('modelList'))  el('modelList').textContent  =
      (cfg.known_models || []).join(' · ');
  } catch {
    const el = document.getElementById('modelName');
    if (el) el.textContent = 'Could not load config';
  }
}

/* ── Slider ↔ number sync ── */
maxSlider?.addEventListener('input', () => {
  maxNum.value = maxSlider.value;
  document.getElementById('maxDisplay').textContent =
    +maxSlider.value === 0 ? 'All' : maxSlider.value;
});
maxNum?.addEventListener('input', () => {
  maxSlider.value = maxNum.value;
  document.getElementById('maxDisplay').textContent =
    +maxNum.value === 0 ? 'All' : maxNum.value;
});

/* ── Re-analyze ── */
document.getElementById('reAnalyzeBtn')?.addEventListener('click', () => {
  State.clear(STATE_KEYS.RESULTS);
  State.clear(STATE_KEYS.SESSION_ID);
  completeBanner.style.display = 'none';
  configSection.style.display  = '';
  liveBody.innerHTML = '';
  liveTableSection.style.display = 'none';
  collectedResults = [];
  updateSidebarStatus();
});

/* ── Start analysis ── */
startBtn?.addEventListener('click', startAnalysis);
document.getElementById('cancelBtn')?.addEventListener('click', cancelAnalysis);

let evtSource = null;

async function startAnalysis() {
  if (isRunning) return;
  const paras  = State.get(STATE_KEYS.PARAGRAPHS) || [];
  const maxVal = +maxNum.value;
  const toProcess = maxVal > 0 ? paras.slice(0, maxVal) : paras;

  if (!toProcess.length) {
    showToast('No paragraphs to analyse.', 'error');
    return;
  }

  isRunning = true;
  startTime = Date.now();
  collectedResults = [];
  startBtn.disabled = true;
  settingsCard.style.display = 'none';

  // Show progress
  progressSection.style.display = '';
  liveTableSection.style.display = '';
  liveBody.innerHTML = '';

  try {
    // Start session
    const { session_id, total } = await postJSON('/api/analyze/start', {
      paragraphs: toProcess,
      max_paragraphs: maxVal,
    });
    State.set(STATE_KEYS.SESSION_ID, session_id);
    document.getElementById('cancelBtn').style.display = 'inline-block';

    connectToStream(session_id);

  } catch (err) {
    handleError(err.message);
  }
}

function resumeAnalysis(session_id) {
  if (isRunning) return;
  isRunning = true;
  startTime = Date.now(); // Note: ETA might be slightly off on resume
  collectedResults = [];
  startBtn.disabled = true;
  settingsCard.style.display = 'none';

  progressSection.style.display = '';
  liveTableSection.style.display = '';
  liveBody.innerHTML = '';
  document.getElementById('cancelBtn').style.display = 'inline-block';
  
  connectToStream(session_id);
}

function connectToStream(session_id) {
  // Stream SSE
  evtSource = new EventSource(`/api/analyze/stream/${session_id}`);

  evtSource.onmessage = (e) => {
    const payload = JSON.parse(e.data);

    if (payload.type === 'progress') {
      handleProgress(payload, payload.total);
    } else if (payload.type === 'complete') {
      evtSource.close();
      handleComplete(payload.results);
    } else if (payload.type === 'cancelled') {
      evtSource.close();
      handleCancelComplete();
    } else if (payload.type === 'error') {
      evtSource.close();
      handleError(payload.message);
    }
  };
  evtSource.onerror = () => {
    evtSource.close();
    // Don't error out immediately, as it might just be a network blip.
    // However, for simplicity here, we'll log it and let it retry or fail.
    console.warn('Connection to server lost.');
  };
}

async function cancelAnalysis() {
  const session_id = State.get(STATE_KEYS.SESSION_ID);
  if (!session_id) return;
  
  document.getElementById('cancelBtn').textContent = "Cancelling...";
  document.getElementById('cancelBtn').disabled = true;
  
  try {
    await fetch(`/api/analyze/cancel/${session_id}`, { method: 'POST' });
  } catch(e) {
    console.error(e);
  }
}

function handleCancelComplete() {
  isRunning = false;
  State.clear(STATE_KEYS.SESSION_ID);
  document.getElementById('cancelBtn').textContent = "Stop / Cancel";
  document.getElementById('cancelBtn').disabled = false;
  document.getElementById('cancelBtn').style.display = 'none';
  
  progressSection.style.display = 'none';
  startBtn.disabled = false;
  settingsCard.style.display = '';
  showToast('Analysis cancelled.', 'warning');
}

function handleProgress(payload, total) {
  const { current, result } = payload;
  const pct = Math.round((current / total) * 100);
  const elapsed = (Date.now() - startTime) / 1000;
  const rate  = current / elapsed;
  const eta   = Math.round((total - current) / (rate || 1));

  // Progress bar
  document.getElementById('mainProgress').style.width = pct + '%';
  document.getElementById('progressCount').textContent = `${current} / ${total}`;
  document.getElementById('progressPct').textContent   = `${pct}%`;
  document.getElementById('etaLabel').textContent      =
    `⏱ ${elapsed.toFixed(0)}s elapsed · ETA ${eta}s`;

  if (!payload.skipped) {
    document.getElementById('progressLabel').textContent =
      `Analysing paragraph ${current} of ${total} — ${result.business_unit} · ${result.theme}`;
    
    // Last snippet
    document.getElementById('lastResultSnippet').innerHTML =
      `<strong>${result.para_type}</strong> · ${esc(result.business_unit)} · ${esc(result.theme)}<br>
       <span style="opacity:.7;">${esc(result.paragraph_text.slice(0, 120))}…</span>`;
  
    collectedResults.push(result);
    document.getElementById('liveCount').textContent =
      `${collectedResults.length} paragraphs processed`;
    appendTableRow(collectedResults.length, result);
  } else {
    document.getElementById('progressLabel').textContent =
      `Analysing paragraph ${current} of ${total} — Skipped (Structural)`;
    
    // Last snippet
    document.getElementById('lastResultSnippet').innerHTML =
      `<strong>Skipped (Structural / Non-Regulatory)</strong><br>
       <span style="opacity:.7;">${esc(result.paragraph_text.slice(0, 120))}…</span>`;
  }
}

async function handleComplete(results) {
  isRunning = false;
  State.set(STATE_KEYS.RESULTS, results);
  collectedResults = results;
  progressSection.style.display = 'none';
  showCompleteBanner(results);
  updateSidebarStatus();
  showToast(`Analysis complete! ${results.length} paragraphs classified. Saving draft...`, 'info', 3000);

  // Auto-save draft
  try {
    const meta = State.get(STATE_KEYS.DOC_META);
    const paras = State.get(STATE_KEYS.PARAGRAPHS);
    const user = getUser();
    
    const resp = await fetch('/api/document/save_draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        results: results,
        document_name: meta?.file_name,
        user_id: user?.id,
        paragraphs: paras || []
      })
    });
    
    if (resp.ok) {
      const data = await resp.json();
      window.lastDocId = data.doc_id; // Global state for export.js to pick up
      localStorage.setItem('rca_last_doc_id', data.doc_id); // Persist for maker_review
      showToast('Draft auto-saved successfully! Redirecting to your documents...', 'success');
      setTimeout(() => {
        window.location.href = `/history.html`;
      }, 1500);
    }
  } catch (err) {
    console.error('Failed to auto-save draft:', err);
    showToast('Analysis complete, but auto-saving draft failed.', 'warning');
  }
}

function handleError(msg) {
  isRunning = false;
  progressSection.style.display = 'none';
  startBtn.disabled = false;
  settingsCard.style.display = '';
  showToast('Analysis error: ' + msg, 'error', 8000);
}

/* ── Complete banner ── */
function showCompleteBanner(results) {
  completeBanner.style.display = '';
  document.getElementById('completeMsg').textContent =
    `✅ Analysis complete — ${results.length} paragraphs classified.`;
  configSection.style.display  = 'none';
  progressSection.style.display = 'none';
}

/* ── Table helpers ── */
function appendTableRow(idx, r) {
  const tr = document.createElement('tr');
  tr.className = 'row-new';
  tr.innerHTML = `
    <td style="font-weight:600;color:#1b2e45;">${idx}</td>
    <td><span class="badge ${badgeClass(r.para_type)}">${esc(r.para_type)}</span></td>
    <td><span class="badge ${r.has_effective_date==='Yes'?'badge-green':'badge-gray'}">${esc(r.has_effective_date)}</span></td>
    <td>${esc(r.business_unit)}</td>
    <td>${esc(r.theme)}</td>
    <td>${esc(r.control_object_name)}</td>
    <td>${esc(r.level_1)}</td>
    <td>${esc(r.level_2)}</td>
    <td style="max-width:240px;white-space:normal;">${esc(r.actionable.slice(0, 90))}${r.actionable.length>90?'…':''}</td>
  `;
  liveBody.prepend(tr); // newest on top
}

function renderLiveTable(results) {
  liveBody.innerHTML = '';
  results.forEach((r, i) => appendTableRow(i + 1, r));
  document.getElementById('liveCount').textContent =
    `${results.length} paragraphs processed`;
}
