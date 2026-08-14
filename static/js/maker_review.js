/* =============================================
   maker_review.js — Maker Review & Submit
   ============================================= */

document.addEventListener('DOMContentLoaded', async () => {
  const user = getUser();
  if (!user || user.role !== 'maker') {
    window.location.href = '/login.html';
    return;
  }

  // Get doc_id from URL params or localStorage
  const urlParams = new URLSearchParams(window.location.search);
  const docId = urlParams.get('doc_id') || localStorage.getItem('rca_last_doc_id');
  if (!docId) {
    document.getElementById('loadingIndicator').innerHTML = `
      <div class="alert alert-info d-inline-block text-start shadow-sm mt-4">
        <h5 class="alert-heading fw-bold mb-2">No Document Selected</h5>
        <p class="mb-0">Please upload and analyze a document first, or select a draft from your <a href="/history.html" class="fw-bold">History</a>.</p>
      </div>
    `;
    return;
  }

  // Save back to localStorage in case they refresh
  localStorage.setItem('rca_last_doc_id', docId);
  
  window.currentDocId = docId;
  await loadDocumentResults(docId);
  
  // Submit document
  document.getElementById('submitBtn').addEventListener('click', submitDocument);
  
  // Save Edit
  document.getElementById('saveEditBtn').addEventListener('click', saveEdit);
});

async function loadDocumentResults(docId) {
  try {
    const res = await fetch(`/api/document/${docId}/results`);
    if (!res.ok) throw new Error('Failed to load document results');
    
    const data = await res.json();
    window.docData = data;
    
    document.getElementById('docTitle').textContent = data.file_name;
    document.getElementById('docParaCount').textContent = data.paragraphs.length;
    document.getElementById('docStatus').textContent = data.status.toUpperCase();
    
    renderReviewTable(data.results, data.paragraphs);
    
    document.getElementById('loadingIndicator').style.display = 'none';
    document.getElementById('contentSection').style.display = 'block';
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function renderReviewTable(results, paragraphs) {
  const tbody = document.getElementById('reviewBody');
  tbody.innerHTML = '';
  
  results.forEach((r, idx) => {
    // Merge paragraph_text if not present
    if (!r.paragraph_text) r.paragraph_text = paragraphs[idx];
    
    const status = r.status || 'Pending';
    const tr = document.createElement('tr');
    if (status === 'Approved') tr.classList.add('row-approved');
    if (status === 'Rejected') tr.classList.add('row-rejected');
    
    let statusBadge = '<span class="badge bg-secondary">Pending</span>';
    if (status === 'Approved') statusBadge = '<span class="badge bg-success">Approved</span>';
    if (status === 'Rejected') statusBadge = '<span class="badge bg-danger">Rejected</span>';
    
    tr.innerHTML = `
      <td class="fw-bold">${idx + 1}</td>
      <td style="font-size: 0.8rem; opacity: 0.8; max-width: 250px;" class="text-truncate" title="${esc(r.paragraph_text)}">
        ${esc(r.paragraph_text)}
      </td>
      <td><span class="badge ${badgeClass(r.para_type)}">${esc(r.para_type)}</span></td>
      <td>${esc(r.business_unit)}</td>
      <td>${esc(r.theme)}</td>
      <td id="statusCell_${idx}">${statusBadge}</td>
      <td class="text-end pe-4">
        <div class="d-flex justify-content-end gap-1 flex-wrap">
          <button class="btn btn-sm btn-outline-success rounded-pill btn-approve-row" data-idx="${idx}">✅</button>
          <button class="btn btn-sm btn-outline-danger rounded-pill btn-reject-row" data-idx="${idx}">❌</button>
          <button class="btn btn-sm btn-outline-primary rounded-pill btn-edit" data-idx="${idx}">✏️ Edit</button>
          <button class="btn btn-sm btn-outline-warning rounded-pill btn-regenerate" data-idx="${idx}">🔄 Regen</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
  
  // Attach events
  document.querySelectorAll('.btn-approve-row').forEach(btn => {
    btn.addEventListener('click', () => updateRowStatus(btn.dataset.idx, 'Approved'));
  });
  document.querySelectorAll('.btn-reject-row').forEach(btn => {
    btn.addEventListener('click', () => updateRowStatus(btn.dataset.idx, 'Rejected'));
  });
  document.querySelectorAll('.btn-edit').forEach(btn => {
    btn.addEventListener('click', () => openEditModal(btn.dataset.idx));
  });
  document.querySelectorAll('.btn-regenerate').forEach(btn => {
    btn.addEventListener('click', () => regenerateRow(btn.dataset.idx, btn));
  });
  
  checkSubmitState();
}

function checkSubmitState() {
  const btn = document.getElementById('submitBtn');
  if (!window.docData || !window.docData.results) return;
  
  const notApproved = window.docData.results.filter(r => r.status !== 'Approved').length;
  if (notApproved > 0) {
    btn.disabled = true;
    btn.title = 'All paragraphs must be approved before submitting.';
  } else {
    btn.disabled = false;
    btn.title = '';
  }
}

async function updateRowStatus(idx, status) {
  try {
    const docId = window.currentDocId;
    const res = await fetch(`/api/document/${docId}/paragraph/${idx}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: status })
    });
    if (!res.ok) throw new Error('Update failed');
    
    // Update local state and UI
    window.docData.results[idx].status = status;
    renderReviewTable(window.docData.results, window.docData.paragraphs);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function openEditModal(idx) {
  const result = window.docData.results[idx];
  document.getElementById('editIdx').value = idx;
  document.getElementById('editParaText').textContent = result.paragraph_text;
  
  document.getElementById('editParaType').value = result.para_type || 'Action Para';
  document.getElementById('editBU').value = result.business_unit || '';
  document.getElementById('editTheme').value = result.theme || '';
  document.getElementById('editHasDate').value = result.has_effective_date || 'No';
  document.getElementById('editDate').value = result.effective_date || '';
  document.getElementById('editControl').value = result.control_object_name || '';
  document.getElementById('editActionable').value = result.actionable || '';
  document.getElementById('editL1').value = result.level_1 || '';
  document.getElementById('editL2').value = result.level_2 || '';
  document.getElementById('editL3').value = result.level_3 || '';
  
  new bootstrap.Modal(document.getElementById('editModal')).show();
}

async function saveEdit() {
  const idx = document.getElementById('editIdx').value;
  const docId = window.currentDocId;
  const btn = document.getElementById('saveEditBtn');
  
  const updatedData = {
    para_type: document.getElementById('editParaType').value,
    business_unit: document.getElementById('editBU').value,
    theme: document.getElementById('editTheme').value,
    has_effective_date: document.getElementById('editHasDate').value,
    effective_date: document.getElementById('editDate').value,
    control_object_name: document.getElementById('editControl').value,
    actionable: document.getElementById('editActionable').value,
    level_1: document.getElementById('editL1').value,
    level_2: document.getElementById('editL2').value,
    level_3: document.getElementById('editL3').value,
    status: 'Approved' // auto-approve on save
  };
  
  btn.disabled = true;
  btn.textContent = 'Saving...';
  
  try {
    const res = await fetch(`/api/document/${docId}/paragraph/${idx}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updatedData)
    });
    if (!res.ok) throw new Error('Save failed');
    
    // Merge updates locally
    Object.assign(window.docData.results[idx], updatedData);
    renderReviewTable(window.docData.results, window.docData.paragraphs);
    
    bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
    showToast('Paragraph updated successfully', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Changes';
  }
}

async function regenerateRow(idx, btn) {
  const docId = window.currentDocId;
  
  btn.disabled = true;
  const originalText = btn.innerHTML;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
  
  try {
    const res = await fetch(`/api/document/${docId}/paragraph/${idx}/regenerate`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Regenerate failed');
    
    const data = await res.json();
    Object.assign(window.docData.results[idx], data.result);
    // Unset status so they review it again
    window.docData.results[idx].status = 'Pending';
    renderReviewTable(window.docData.results, window.docData.paragraphs);
    
    showToast('Paragraph regenerated', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

async function submitDocument() {
  const user = getUser();
  const docId = window.currentDocId;
  
  const notApproved = window.docData.results.filter(r => r.status !== 'Approved').length;
  if (notApproved > 0) {
    showToast('All paragraphs must be approved before submitting to Checker.', 'warning');
    return;
  }
  
  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = 'Submitting...';
  
  try {
    const res = await fetch(`/api/maker/submit/${docId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: user.id })
    });
    if (!res.ok) throw new Error('Submit failed');
    
    showToast('Document submitted for Checker review! ✅', 'success');
    document.getElementById('docStatus').textContent = 'PENDING_REVIEW';
    
    // Redirect back to upload or history
    setTimeout(() => {
      window.location.href = '/history.html';
    }, 1500);
  } catch (e) {
    showToast(e.message, 'error');
    btn.disabled = false;
    btn.textContent = '📨 Submit to Checker';
  }
}
