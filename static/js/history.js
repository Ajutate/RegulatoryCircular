/* =============================================
   history.js — Document history view (with lazy loading)
   ============================================= */

let PAGE_SIZE = 10;   // default; user can change via dropdown

let _skip = 0;
let _total = 0;
let _loading = false;
let _user = null;

document.addEventListener('DOMContentLoaded', () => {
  _user = getUser();
  if (!_user) return;

  // Page size dropdown
  const pageSizeSel = document.getElementById('historyPageSize');
  pageSizeSel.value = String(PAGE_SIZE);
  pageSizeSel.addEventListener('change', () => {
    PAGE_SIZE = parseInt(pageSizeSel.value, 10);
    resetHistory();
  });

  // Load More button (manual click)
  document.getElementById('historyLoadMoreBtn').addEventListener('click', () => {
    loadNextPage();
  });

  // Initial load
  resetHistory();
});

function resetHistory() {
  _skip  = 0;
  _total = 0;
  _loading = false;

  const tbody = document.getElementById('historyBody');
  tbody.innerHTML = `
    <tr><td colspan="6" class="text-center py-5 text-secondary">
      <div class="spinner-border spinner-border-sm me-2" role="status"></div>
      Loading...
    </td></tr>`;
  setFooterState('hidden');
  loadNextPage();
}

// Footer states:
//   'hidden'   — nothing visible
//   'loading'  — spinner + "Loading more…"
//   'more'     — "Load More" button + record counter
//   'done'     — "All N records loaded"
//   'error'    — error message + retry button
function setFooterState(state, msg) {
  const footer   = document.getElementById('historyFooter');
  const spinner  = document.getElementById('historyFooterSpinner');
  const loadBtn  = document.getElementById('historyLoadMoreBtn');
  const counter  = document.getElementById('historyCounter');
  const doneMsg  = document.getElementById('historyDoneMsg');
  const errorMsg = document.getElementById('historyErrorMsg');

  // Reset all
  footer.classList.remove('d-none');
  spinner.classList.add('d-none');
  loadBtn.classList.add('d-none');
  counter.classList.add('d-none');
  doneMsg.classList.add('d-none');
  errorMsg.classList.add('d-none');

  if (state === 'hidden') {
    footer.classList.add('d-none');
  } else if (state === 'loading') {
    spinner.classList.remove('d-none');
  } else if (state === 'more') {
    loadBtn.classList.remove('d-none');
    counter.classList.remove('d-none');
    counter.textContent = `Showing ${_skip} of ${_total} records`;
  } else if (state === 'done') {
    doneMsg.classList.remove('d-none');
    doneMsg.textContent = `✅ All ${_total} record${_total !== 1 ? 's' : ''} loaded`;
  } else if (state === 'error') {
    errorMsg.classList.remove('d-none');
    errorMsg.textContent = msg || 'Failed to load.';
  }
}

async function loadNextPage() {
  if (_loading) return;
  if (_skip > 0 && _skip >= _total) return;

  _loading = true;
  setFooterState('loading');

  const tbody = document.getElementById('historyBody');

  try {
    const resp = await fetch(
      `/api/history?user_id=${_user.id}&role=${_user.role}&skip=${_skip}&limit=${PAGE_SIZE}`
    );
    if (!resp.ok) throw new Error('Failed to fetch history');

    const data  = await resp.json();
    const items = data.items || [];
    _total = data.total || 0;

    // Clear placeholder on first page
    if (_skip === 0) {
      tbody.innerHTML = '';
      if (items.length === 0) {
        tbody.innerHTML = `
          <tr>
            <td colspan="6" class="text-center py-5 text-secondary">
              No history found. Upload and export a document to see it here.
            </td>
          </tr>`;
        setFooterState('hidden');
        _loading = false;
        return;
      }
    }

    items.forEach(doc => appendRow(tbody, doc, _user));
    _skip += items.length;

    if (_skip >= _total) {
      setFooterState('done');
    } else {
      setFooterState('more');
    }

  } catch (err) {
    setFooterState('error', `Error: ${err.message}`);
    if (_skip === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-5 text-danger">
            Failed to load history: ${err.message}
          </td>
        </tr>`;
    }
  } finally {
    _loading = false;
  }
}

function appendRow(tbody, doc, user) {
  const date = new Date(doc.upload_time).toLocaleString();
  const statusBadge = getStatusBadge(doc.status);
  const isDraftOrRejected = doc.status === 'draft' || doc.status === 'rejected';
  const isApproved = doc.status === 'approved';
  const isPendingAnalysis = doc.status === 'pending_analysis';

  const reviewBtnHtml = (isDraftOrRejected && user.role === 'maker')
    ? `<a href="/maker_review.html?doc_id=${doc.id}" class="btn btn-sm btn-outline-primary rounded-pill px-3 ms-2">📝 Review &amp; Edit</a>`
    : '';

  const analyzeBtnHtml = (isPendingAnalysis && user.role === 'maker')
    ? `<a href="/analyze.html?doc_id=${doc.id}" class="btn btn-sm btn-outline-info rounded-pill px-3 ms-2">🔍 Analyze</a>`
    : '';

  const downloadBtnHtml = isApproved
    ? `<a href="/api/history/${doc.id}/download" class="btn btn-sm btn-outline-success rounded-pill px-3">📥 Download Excel</a>`
    : '';

  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="text-secondary small ps-4">${date}</td>
    <td class="fw-medium text-navy">${esc(doc.file_name)}</td>
    <td>${esc(doc.circular_name || '—')}</td>
    <td><span class="badge bg-secondary-subtle text-secondary">${doc.paragraph_count}</span></td>
    <td>${statusBadge}</td>
    <td class="text-end pe-4" style="max-width: none; overflow: visible; white-space: nowrap;">
      ${downloadBtnHtml}
      ${analyzeBtnHtml}
      ${reviewBtnHtml}
    </td>
  `;
  tbody.appendChild(tr);
}

function getStatusBadge(status) {
  switch (status) {
    case 'pending_analysis':
      return '<span class="badge bg-info text-dark rounded-pill">📥 Extracted</span>';
    case 'pending_review':
      return '<span class="badge bg-warning text-dark rounded-pill">⏳ Pending Review</span>';
    case 'approved':
      return '<span class="badge bg-success rounded-pill">✅ Approved</span>';
    case 'rejected':
      return '<span class="badge bg-danger rounded-pill">❌ Rejected</span>';
    default:
      return '<span class="badge bg-secondary-subtle text-secondary rounded-pill">📝 Draft</span>';
  }
}

async function submitDraftFromHistory(docId, btnEl) {
  const user = getUser();
  if (!user) return;

  btnEl.disabled = true;
  btnEl.textContent = 'Submitting...';

  try {
    const resp = await fetch(`/api/maker/submit/${docId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: user.id }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Submit failed' }));
      throw new Error(err.detail);
    }
    showToast('Document submitted for Checker review! ✅', 'success');
    setTimeout(() => { window.location.reload(); }, 1500);
  } catch (err) {
    showToast('Submit failed: ' + err.message, 'error');
    btnEl.disabled = false;
    btnEl.textContent = '📨 Submit for Review';
  }
}
