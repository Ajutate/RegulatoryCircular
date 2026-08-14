/* =============================================
   history.js — Document history view
   ============================================= */

document.addEventListener('DOMContentLoaded', async () => {
  const user = getUser();
  if (!user) return;

  const tbody = document.getElementById('historyBody');

  try {
    const resp = await fetch(`/api/history?user_id=${user.id}&role=${user.role}`);
    if (!resp.ok) throw new Error('Failed to fetch history');
    
    const history = await resp.json();
    
    if (history.length === 0) {
      tbody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center py-5 text-secondary">
            No history found. Upload and export a document to see it here.
          </td>
        </tr>
      `;
      return;
    }

    tbody.innerHTML = '';
    
    history.forEach(doc => {
      const date = new Date(doc.upload_time).toLocaleString();
      const statusBadge = getStatusBadge(doc.status);
      const isDraftOrRejected = doc.status === 'draft' || doc.status === 'rejected';
      const isApproved = doc.status === 'approved';
      
      const reviewBtnHtml = (isDraftOrRejected && user.role === 'maker')
        ? `<a href="/maker_review.html?doc_id=${doc.id}" class="btn btn-sm btn-outline-primary rounded-pill px-3 ms-2">📝 Review & Edit</a>`
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
          ${reviewBtnHtml}
        </td>
      `;
      tbody.appendChild(tr);
    });

  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" class="text-center py-5 text-danger">
          Failed to load history: ${err.message}
        </td>
      </tr>
    `;
  }
});

function getStatusBadge(status) {
  switch (status) {
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
    
    // Refresh history
    setTimeout(() => {
      // Re-trigger the DOMContentLoaded event listener by reloading the tab
      // The easiest way in a SPA is to click the nav link again, but since this isn't possible directly,
      // we can just reload the page or re-dispatch DOMContentLoaded
      window.location.reload(); 
    }, 1500);
  } catch (err) {
    showToast('Submit failed: ' + err.message, 'error');
    btnEl.disabled = false;
    btnEl.textContent = '📨 Submit for Review';
  }
}
