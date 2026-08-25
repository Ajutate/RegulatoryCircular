/* =============================================
   checker.js — Checker review queue
   ============================================= */

let rejectDocId = '';

document.addEventListener('DOMContentLoaded', async () => {
  const user = JSON.parse(localStorage.getItem('rca_user') || 'null');
  if (!user || user.role !== 'checker') {
    window.location.href = '/login.html';
    return;
  }

  await loadQueue();

  // Reject modal confirm
  document.getElementById('confirmRejectBtn').addEventListener('click', async () => {
    const comment = document.getElementById('rejectComment').value.trim();
    if (!comment) {
      alert('Please provide a rejection reason.');
      return;
    }
    try {
      await fetch(`/api/checker/reject/${rejectDocId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: user.id, comment }),
      });
      bootstrap.Modal.getInstance(document.getElementById('rejectModal')).hide();
      showToast('Document rejected.', 'warning');
      await loadQueue();
    } catch (err) {
      showToast('Reject failed: ' + err.message, 'error');
    }
  });
});

async function loadQueue() {
  const unassignedBody = document.getElementById('unassignedBody');
  const myQueueBody = document.getElementById('myQueueBody');
  const user = JSON.parse(localStorage.getItem('rca_user'));

  try {
    const resp = await fetch('/api/checker/queue?user_id=' + user.id);
    const data = await resp.json();

    // Render Unassigned
    if (data.unassigned.length === 0) {
      unassignedBody.innerHTML = `
        <tr><td colspan="5" class="text-center py-5 text-secondary">
          No unassigned documents pending review.
        </td></tr>`;
    } else {
      unassignedBody.innerHTML = '';
      data.unassigned.forEach(doc => {
        const date = new Date(doc.upload_time).toLocaleString();
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="text-secondary small ps-4">${date}</td>
          <td class="fw-medium text-navy">${esc(doc.file_name)}</td>
          <td>${esc(doc.submitter_name || '—')}</td>
          <td><span class="badge bg-secondary-subtle text-secondary">${doc.paragraph_count}</span></td>
          <td class="text-end pe-4">
            <div class="d-flex justify-content-end gap-1 flex-wrap">
              <button class="btn btn-sm btn-primary rounded-pill btn-claim" data-id="${doc.id}">✋ Claim</button>
            </div>
          </td>
        `;
        unassignedBody.appendChild(tr);
      });
    }

    // Render My Queue
    if (data.my_queue.length === 0) {
      myQueueBody.innerHTML = `
        <tr><td colspan="5" class="text-center py-5 text-secondary">
          You have no claimed documents pending review.
        </td></tr>`;
    } else {
      myQueueBody.innerHTML = '';
      data.my_queue.forEach(doc => {
        const date = new Date(doc.upload_time).toLocaleString();
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td class="text-secondary small ps-4">${date}</td>
          <td class="fw-medium text-navy">${esc(doc.file_name)}</td>
          <td>${esc(doc.submitter_name || '—')}</td>
          <td><span class="badge bg-secondary-subtle text-secondary">${doc.paragraph_count}</span></td>
          <td class="text-end pe-4">
            <div class="d-flex justify-content-end gap-1 flex-wrap">
              <button class="btn btn-sm btn-outline-primary rounded-pill btn-review-detail" data-id="${doc.id}" data-name="${esc(doc.file_name)}">📋 Review</button>
            </div>
          </td>
        `;
        myQueueBody.appendChild(tr);
      });
    }

    // Claim buttons
    unassignedBody.querySelectorAll('.btn-claim').forEach(btn => {
      btn.addEventListener('click', async () => {
        try {
          btn.disabled = true;
          btn.textContent = 'Claiming...';
          const res = await fetch(`/api/checker/claim/${btn.dataset.id}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: user.id }),
          });
          if (!res.ok) throw new Error('Claim failed');
          showToast('Document claimed! ✅', 'success');
          await loadQueue();
        } catch (err) {
          showToast(err.message, 'error');
          btn.disabled = false;
          btn.textContent = '✋ Claim';
        }
      });
    });

    // Review Detail buttons
    myQueueBody.querySelectorAll('.btn-review-detail').forEach(btn => {
      btn.addEventListener('click', () => {
        openReviewDetail(btn.dataset.id, btn.dataset.name);
      });
    });

  } catch (err) {
    unassignedBody.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-4">Error loading queue</td></tr>`;
    myQueueBody.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-4">Error loading queue</td></tr>`;
  }
}

// ── Detailed Review Logic ──

async function openReviewDetail(docId, docName) {
  document.getElementById('queueSection').style.display = 'none';
  document.getElementById('reviewDetailSection').style.display = 'block';
  document.getElementById('reviewDocTitle').textContent = docName;
  window.currentDocId = docId;

  // Fetch results
  try {
    const res = await fetch(`/api/document/${docId}/results`);
    if (!res.ok) throw new Error('Failed to load document results');
    
    const data = await res.json();
    window.docData = data;
    
    renderCheckerReviewTable(data.results, data.paragraphs);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function renderCheckerReviewTable(results, paragraphs) {
  const tbody = document.getElementById('checkerReviewBody');
  tbody.innerHTML = '';
  
  results.forEach((r, idx) => {
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
          <button class="btn btn-sm btn-outline-dark rounded-pill btn-delete-row" data-idx="${idx}" title="Delete this paragraph">🗑️</button>
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
  document.querySelectorAll('.btn-delete-row').forEach(btn => {
    btn.addEventListener('click', () => deleteRow(btn.dataset.idx));
  });
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
    
    window.docData.results[idx].status = status;
    renderCheckerReviewTable(window.docData.results, window.docData.paragraphs);
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

document.getElementById('saveEditBtn')?.addEventListener('click', async () => {
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
    
    Object.assign(window.docData.results[idx], updatedData);
    renderCheckerReviewTable(window.docData.results, window.docData.paragraphs);
    
    bootstrap.Modal.getInstance(document.getElementById('editModal')).hide();
    await showAlertModal('Paragraph Updated', 'The paragraph was successfully updated.', 'success');
  } catch (e) {
    await showAlertModal('Error Updating Paragraph', e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Save Changes';
  }
});

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
    window.docData.results[idx].status = 'Pending';
    renderCheckerReviewTable(window.docData.results, window.docData.paragraphs);
    
    showToast('Paragraph regenerated', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = originalText;
  }
}

async function deleteRow(idx) {
  const paraText = window.docData.results[idx]?.paragraph_text || '';
  const preview = paraText.substring(0, 100) + (paraText.length > 100 ? '...' : '');
  
  const confirmed = await showConfirmModal('🗑️ Delete Paragraph', `Delete paragraph ${parseInt(idx) + 1}?\n\n"${preview}"\n\nThis paragraph will be removed and won't appear in the Excel export.`, 'Delete', 'danger');
  if (!confirmed) return;

  try {
    const res = await fetch(`/api/document/${window.currentDocId}/paragraph/${idx}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Delete failed');
    }

    const data = await res.json();
    window.docData = data;
    renderCheckerReviewTable(data.results, data.paragraphs);
    showToast('Paragraph deleted ✅', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
}

// Back to queue
document.getElementById('backToQueueBtn')?.addEventListener('click', () => {
  document.getElementById('reviewDetailSection').style.display = 'none';
  document.getElementById('queueSection').style.display = 'block';
});

// Final Approve & Excel Generation
document.getElementById('btnDetailApprove')?.addEventListener('click', async () => {
  const user = JSON.parse(localStorage.getItem('rca_user'));
  const docId = window.currentDocId;
  const btn = document.getElementById('btnDetailApprove');
  
  const confirmed = await showConfirmModal('✅ Final Approval', 'This will generate the Excel file and approve the document. Proceed?', 'Approve', 'success');
  if (!confirmed) return;
  
  btn.disabled = true;
  btn.textContent = 'Approving...';
  
  try {
    const res = await fetch(`/api/checker/approve/${docId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: user.id })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Approval failed');
    }
    
    await showAlertModal('Success', 'Document approved and Excel generated!', 'success');
    document.getElementById('backToQueueBtn').click();
    await loadQueue();
  } catch (e) {
    await showAlertModal('Approval Failed', e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '✅ Final Approval';
  }
});

// Detail Reject
document.getElementById('btnDetailReject')?.addEventListener('click', () => {
  rejectDocId = window.currentDocId;
  document.getElementById('rejectComment').value = '';
  new bootstrap.Modal(document.getElementById('rejectModal')).show();
  // when rejected, it automatically reloads queue. We can just switch view back
  bootstrap.Modal.getInstance(document.getElementById('rejectModal'))._element.addEventListener('hidden.bs.modal', () => {
     document.getElementById('backToQueueBtn').click();
  }, {once: true});
});

