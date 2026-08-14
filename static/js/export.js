/* =============================================
   export.js — Export page logic
   ============================================= */

let allResults   = [];
let filteredRows = [];
let sortCol      = null;
let sortDir      = 1;  // 1 = asc, -1 = desc
window.lastDocId = null; // ID of the most recently exported document

/* ── On load ── */
document.addEventListener('DOMContentLoaded', () => {
  const results = State.get(STATE_KEYS.RESULTS);
  const meta    = State.get(STATE_KEYS.DOC_META);

  if (!results || !results.length) {
    document.getElementById('noResultsAlert').style.display = '';
    return;
  }

  allResults = results;
  document.getElementById('exportContent').style.display = '';

  buildSummaryMetrics(results, meta);
  buildFilters(results);
  applyFilters();
  drawCharts(results);

  // Download info and default values
  const docName = meta?.file_name || 'Regulatory_Analysis';
  document.getElementById('downloadInfo').innerHTML =
    `<strong>${docName.replace(/\.\w+$/, '')}_Analysis.xlsx</strong> &nbsp;·&nbsp;
     ${results.length} rows &nbsp;·&nbsp; 12 columns`;

  // Auto-populate the Circular Name with the first heading extracted from the document
  const circularInput = document.getElementById('exportCircularName');
  if (circularInput) {
    circularInput.value = meta?.metadata?.first_heading || meta?.file_name || '';
  }

  // Auto-populate the global Effective Date if the LLM found one during analysis
  const effDateInput = document.getElementById('exportEffDate');
  if (effDateInput && !effDateInput.value) {
    const firstDatePara = results.find(r => r.has_effective_date === 'Yes' && r.effective_date);
    if (firstDatePara) {
      effDateInput.value = firstDatePara.effective_date;
    }
  }

  // Show submit button if auto-saved
  const submitBtn = document.getElementById('submitForReviewBtn');
  const user = getUser();
  if (submitBtn && user?.role === 'maker' && window.lastDocId) {
    submitBtn.style.display = '';
  }
});

/* ── Summary metrics ── */
function buildSummaryMetrics(results, meta) {
  const buSet    = new Set(results.map(r => r.business_unit));
  const themeSet = new Set(results.map(r => r.theme));
  const withDate = results.filter(r => r.has_effective_date === 'Yes').length;

  const grid = document.getElementById('summaryMetrics');
  grid.innerHTML = `
    <div class="metric-card">
      <div class="label">Document</div>
      <div class="value" style="font-size:.9rem;word-break:break-all;">${esc(meta?.file_name ?? '—')}</div>
    </div>
    <div class="metric-card">
      <div class="label">Total Paragraphs</div>
      <div class="value">${results.length}</div>
    </div>
    <div class="metric-card">
      <div class="label">Business Units</div>
      <div class="value">${buSet.size}</div>
    </div>
    <div class="metric-card">
      <div class="label">Themes</div>
      <div class="value">${themeSet.size}</div>
    </div>
    <div class="metric-card">
      <div class="label">With Effective Dates</div>
      <div class="value">${withDate}</div>
      <div class="sub">${Math.round(withDate/results.length*100)}% of total</div>
    </div>
  `;
}

/* ── Charts ── */
function drawCharts(results) {
  // Business unit chart
  const buCount = {};
  results.forEach(r => { buCount[r.business_unit] = (buCount[r.business_unit] || 0) + 1; });
  const buSorted = Object.entries(buCount).sort((a,b) => b[1]-a[1]).slice(0, 10);
  drawBarChart('buChart', buSorted.map(x=>x[0]), buSorted.map(x=>x[1]), '#2e86c1');

  // Theme chart
  const thCount = {};
  results.forEach(r => { thCount[r.theme] = (thCount[r.theme] || 0) + 1; });
  const thSorted = Object.entries(thCount).sort((a,b) => b[1]-a[1]).slice(0, 10);
  drawBarChart('themeChart', thSorted.map(x=>x[0]), thSorted.map(x=>x[1]), '#27ae60');
}

/* ── Build filter options ── */
function buildFilters(results) {
  populateSelect('filterBU',    [...new Set(results.map(r => r.business_unit))].sort());
  populateSelect('filterTheme', [...new Set(results.map(r => r.theme))].sort());
  populateSelect('filterType',  [...new Set(results.map(r => r.para_type))].sort());

  ['filterBU','filterTheme','filterType','filterDate'].forEach(id =>
    document.getElementById(id).addEventListener('change', applyFilters)
  );
  document.getElementById('filterSearch').addEventListener('input', applyFilters);
  document.getElementById('clearFiltersBtn').addEventListener('click', clearFilters);

  // Column sorting
  document.querySelectorAll('thead th[data-col]').forEach(th => {
    th.addEventListener('click', () => {
      const col = th.dataset.col;
      if (sortCol === col) sortDir *= -1;
      else { sortCol = col; sortDir = 1; }
      applyFilters();
    });
  });
}

function populateSelect(id, options) {
  const sel = document.getElementById(id);
  options.forEach(o => {
    const opt = document.createElement('option');
    opt.value = opt.textContent = o;
    sel.appendChild(opt);
  });
}

function clearFilters() {
  ['filterBU','filterTheme','filterType','filterDate'].forEach(id =>
    document.getElementById(id).value = ''
  );
  document.getElementById('filterSearch').value = '';
  applyFilters();
}

/* ── Apply filters + sort + render ── */
function applyFilters() {
  const bu     = document.getElementById('filterBU').value;
  const theme  = document.getElementById('filterTheme').value;
  const type   = document.getElementById('filterType').value;
  const date   = document.getElementById('filterDate').value;
  const search = document.getElementById('filterSearch').value.toLowerCase();

  filteredRows = allResults.filter(r => {
    if (bu    && r.business_unit     !== bu)   return false;
    if (theme && r.theme             !== theme) return false;
    if (type  && r.para_type         !== type)  return false;
    if (date  && r.has_effective_date !== date) return false;
    if (search && !r.paragraph_text.toLowerCase().includes(search) &&
        !r.business_unit.toLowerCase().includes(search) &&
        !r.theme.toLowerCase().includes(search)) return false;
    return true;
  });

  // Sort
  if (sortCol) {
    filteredRows.sort((a, b) => {
      const va = String(a[sortCol] ?? '');
      const vb = String(b[sortCol] ?? '');
      return va.localeCompare(vb) * sortDir;
    });
  }

  document.getElementById('filteredCount').textContent =
    `Showing ${filteredRows.length} of ${allResults.length} paragraphs`;

  renderTable();
}

/* ── Render table ── */
function renderTable() {
  const tbody = document.getElementById('resultsBody');
  tbody.innerHTML = '';

  filteredRows.forEach((r, i) => {
    const tr = document.createElement('tr');
    tr.style.cursor = 'pointer';
    tr.title = 'Click to view full paragraph';
    tr.innerHTML = `
      <td style="font-weight:600;color:#1b2e45;">${i + 1}</td>
      <td><span class="badge ${badgeClass(r.para_type)}">${esc(r.para_type)}</span></td>
      <td><span class="badge ${r.has_effective_date==='Yes'?'badge-green':'badge-gray'}">${esc(r.has_effective_date)}</span></td>
      <td>${esc(r.effective_date || '—')}</td>
      <td>${esc(r.business_unit)}</td>
      <td>${esc(r.theme)}</td>
      <td>${esc(r.control_object_name)}</td>
      <td style="max-width:200px;white-space:normal;font-size:.78rem;">${esc(r.actionable.slice(0,100))}${r.actionable.length>100?'…':''}</td>
      <td>${esc(r.level_1)}</td>
      <td>${esc(r.level_2)}</td>
      <td>${esc(r.level_3)}</td>
      <td class="para-cell" style="font-size:.75rem;opacity:.85;">${esc(r.paragraph_text.slice(0,120))}…</td>
    `;
    tr.addEventListener('click', () => showParaViewer(r));
    tbody.appendChild(tr);
  });
}

/* ── Paragraph viewer ── */
function showParaViewer(r) {
  const card = document.getElementById('paraViewerCard');
  card.style.display = '';
  document.getElementById('viewerMeta').innerHTML =
    `<strong>Business Unit:</strong> ${esc(r.business_unit)} &nbsp;|&nbsp;
     <strong>Theme:</strong> ${esc(r.theme)} &nbsp;|&nbsp;
     <strong>Para Type:</strong> ${esc(r.para_type)}`;
  document.getElementById('viewerText').textContent = r.paragraph_text;
  card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ── Excel download ── */
document.getElementById('downloadBtn').addEventListener('click', async () => {
  const meta    = State.get(STATE_KEYS.DOC_META);
  const results = State.get(STATE_KEYS.RESULTS);
  const paras   = State.get(STATE_KEYS.PARAGRAPHS);
  const user    = getUser();
  if (!results || !results.length) {
    showToast('No results to export.', 'error');
    return;
  }

  const btn     = document.getElementById('downloadBtn');
  const btnText = document.getElementById('downloadBtnText');
  const spinner = document.getElementById('downloadSpinner');

  btn.disabled = true;
  btnText.textContent = 'Generating…';
  spinner.style.display = '';

  try {
    const authId = document.getElementById('exportAuthId')?.value || '';
    const effDate = document.getElementById('exportEffDate')?.value || '';
    
    const nameInput = document.getElementById('exportCircularName')?.value;
    const finalName = nameInput || meta?.metadata?.first_heading || meta?.file_name || 'Regulatory_Analysis';

    const resp = await fetch('/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        results,
        document_name: finalName,
        authority_id: authId,
        effective_date: effDate,
        user_id: user?.id || '',
        paragraphs: paras || [],
        doc_id: window.lastDocId || '',
      }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || resp.statusText);
    }

    // Capture the document ID from the response header
    window.lastDocId = resp.headers.get('X-Document-Id') || window.lastDocId;

    const blob = await resp.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    const cd   = resp.headers.get('content-disposition') || '';
    const fnMatch = cd.match(/filename="([^"]+)"/);
    a.download = fnMatch ? fnMatch[1] : 'Regulatory_Analysis.xlsx';
    a.href = url;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);

    showToast('Excel report downloaded successfully!', 'success');

    // Show the Submit for Review button for Makers
    const submitBtn = document.getElementById('submitForReviewBtn');
    if (submitBtn && user?.role === 'maker' && window.lastDocId) {
      submitBtn.style.display = '';
    }
  } catch (err) {
    showToast('Download failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btnText.textContent = '📥 Download Excel';
    spinner.style.display = 'none';
  }
});

/* ── Submit for Review (Maker) ── */
const submitBtn = document.getElementById('submitForReviewBtn');
if (submitBtn) {
  submitBtn.addEventListener('click', async () => {
    const user = getUser();
    if (!window.lastDocId || !user) return;

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting…';

    try {
      const resp = await fetch(`/api/maker/submit/${window.lastDocId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Submit failed' }));
        throw new Error(err.detail);
      }
      showToast('Document submitted for Checker review! ✅', 'success');
      submitBtn.textContent = '✅ Submitted';
      submitBtn.classList.replace('btn-warning', 'btn-success');
    } catch (err) {
      showToast('Submit failed: ' + err.message, 'error');
      submitBtn.disabled = false;
      submitBtn.textContent = '📨 Submit for Review';
    }
  });
}
