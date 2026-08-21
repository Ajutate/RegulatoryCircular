/* =============================================
   maker_review.js — Maker Review & Submit
   With: Merge, Split, Drag-and-Drop Reorder
   ============================================= */

document.addEventListener('DOMContentLoaded', async () => {
  const user = getUser();
  if (!user || user.role !== 'maker') {
    window.location.href = '/login.html';
    return;
  }

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

  localStorage.setItem('rca_last_doc_id', docId);
  window.currentDocId = docId;
  await loadDocumentResults(docId);

  // Submit
  document.getElementById('submitBtn').addEventListener('click', submitDocument);
  // Save Edit
  document.getElementById('saveEditBtn').addEventListener('click', saveEdit);
  // Merge
  document.getElementById('mergeBtn').addEventListener('click', mergeSelected);
  // Select All
  document.getElementById('selectAllCheck').addEventListener('change', toggleSelectAll);
  // Confirm Split
  document.getElementById('confirmSplitBtn').addEventListener('click', confirmSplit);
});


// ================================================================== //
//  Load & Render                                                      //
// ================================================================== //

async function loadDocumentResults(docId) {
  try {
    const res = await fetch(`/api/document/${docId}/results`);
    if (!res.ok) throw new Error('Failed to load document results');

    const data = await res.json();
    window.docData = data;

    document.getElementById('docTitle').textContent = data.file_name;
    document.getElementById('docParaCount').textContent = data.results.length;
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
    if (!r.paragraph_text) r.paragraph_text = paragraphs[idx];

    const status = r.status || 'Pending';
    const tr = document.createElement('tr');
    tr.dataset.idx = idx;
    tr.setAttribute('draggable', 'true');

    if (status === 'Approved') tr.classList.add('row-approved');
    if (status === 'Rejected') tr.classList.add('row-rejected');

    let statusBadge = '<span class="badge bg-secondary">Pending</span>';
    if (status === 'Approved') statusBadge = '<span class="badge bg-success">Approved</span>';
    if (status === 'Rejected') statusBadge = '<span class="badge bg-danger">Rejected</span>';

    tr.innerHTML = `
      <td>
        <input type="checkbox" class="form-check-input merge-check row-check" data-idx="${idx}" />
      </td>
      <td>
        <span class="drag-handle" title="Drag to reorder">⠿</span>
      </td>
      <td class="fw-bold ps-2">${idx + 1}</td>
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
          <button class="btn btn-sm btn-outline-info rounded-pill btn-split" data-idx="${idx}">✂️ Split</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach row-level events
  document.querySelectorAll('.btn-approve-row').forEach(btn =>
    btn.addEventListener('click', () => updateRowStatus(btn.dataset.idx, 'Approved'))
  );
  document.querySelectorAll('.btn-reject-row').forEach(btn =>
    btn.addEventListener('click', () => updateRowStatus(btn.dataset.idx, 'Rejected'))
  );
  document.querySelectorAll('.btn-edit').forEach(btn =>
    btn.addEventListener('click', () => openEditModal(btn.dataset.idx))
  );
  document.querySelectorAll('.btn-regenerate').forEach(btn =>
    btn.addEventListener('click', () => regenerateRow(btn.dataset.idx, btn))
  );
  document.querySelectorAll('.btn-split').forEach(btn =>
    btn.addEventListener('click', () => openSplitModal(btn.dataset.idx))
  );

  // Checkbox events
  document.querySelectorAll('.row-check').forEach(cb =>
    cb.addEventListener('change', updateMergeButton)
  );

  // Drag-and-drop events
  initDragAndDrop();

  checkSubmitState();
  updateMergeButton();
}


// ================================================================== //
//  Merge Logic                                                        //
// ================================================================== //

function toggleSelectAll(e) {
  const checked = e.target.checked;
  document.querySelectorAll('.row-check').forEach(cb => { cb.checked = checked; });
  updateMergeButton();
}

function updateMergeButton() {
  const checked = document.querySelectorAll('.row-check:checked');
  const btn = document.getElementById('mergeBtn');
  const count = document.getElementById('mergeCount');
  count.textContent = checked.length;
  btn.disabled = checked.length < 2;
}

async function mergeSelected() {
  const checked = document.querySelectorAll('.row-check:checked');
  const indices = Array.from(checked).map(cb => parseInt(cb.dataset.idx));

  if (indices.length < 2) {
    showToast('Select at least 2 paragraphs to merge.', 'warning');
    return;
  }

  if (!confirm(`Merge ${indices.length} paragraphs into one? The merged paragraph will be re-analyzed by the AI.`)) return;

  const btn = document.getElementById('mergeBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Merging...';

  try {
    const res = await fetch(`/api/document/${window.currentDocId}/paragraphs/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ indices })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Merge failed');
    }

    const data = await res.json();
    window.docData = data;
    document.getElementById('docParaCount').textContent = data.results.length;
    renderReviewTable(data.results, data.paragraphs);
    showToast('Paragraphs merged and re-analyzed! ✅', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.innerHTML = '🔗 Merge Selected (<span id="mergeCount">0</span>)';
    btn.disabled = true;
  }
}


// ================================================================== //
//  Split Logic                                                        //
// ================================================================== //

function openSplitModal(idx) {
  const result = window.docData.results[idx];
  const text = result.paragraph_text;

  document.getElementById('splitIdx').value = idx;
  document.getElementById('splitPos').value = '';
  document.getElementById('confirmSplitBtn').disabled = true;

  // Render the text as a clickable div
  const preview = document.getElementById('splitPreview');
  preview.textContent = text;
  preview.dataset.fullText = text;

  // Remove old split info
  document.getElementById('splitInfo').style.display = 'none';

  // Click handler: compute split position from click
  preview.onclick = function (e) {
    const range = document.caretRangeFromPoint
      ? document.caretRangeFromPoint(e.clientX, e.clientY)
      : null;

    let pos = 0;
    if (range) {
      // Walk through text nodes to compute absolute offset
      const walker = document.createTreeWalker(preview, NodeFilter.SHOW_TEXT);
      let node;
      while ((node = walker.nextNode())) {
        if (node === range.startContainer) {
          pos += range.startOffset;
          break;
        }
        pos += node.textContent.length;
      }
    }

    if (pos <= 0 || pos >= text.length) return;

    document.getElementById('splitPos').value = pos;

    // Show visual preview
    const partA = text.substring(0, pos);
    const partB = text.substring(pos);
    preview.innerHTML =
      `<span class="split-part-a">${esc(partA)}</span>` +
      `<span class="split-marker"></span>` +
      `<span class="split-part-b">${esc(partB)}</span>`;

    // Update info
    document.getElementById('splitInfo').style.display = 'flex';
    document.getElementById('splitInfo').style.cssText = '';
    document.getElementById('splitPartALen').textContent = `${partA.trim().length} chars`;
    document.getElementById('splitPartBLen').textContent = `${partB.trim().length} chars`;

    document.getElementById('confirmSplitBtn').disabled = false;
  };

  new bootstrap.Modal(document.getElementById('splitModal')).show();
}

async function confirmSplit() {
  const idx = parseInt(document.getElementById('splitIdx').value);
  const splitPos = parseInt(document.getElementById('splitPos').value);
  const btn = document.getElementById('confirmSplitBtn');

  if (!splitPos || splitPos <= 0) {
    showToast('Click on the text to select a split point first.', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Splitting & Analyzing...';

  try {
    const res = await fetch(`/api/document/${window.currentDocId}/paragraphs/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index: idx, split_position: splitPos })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Split failed');
    }

    const data = await res.json();
    window.docData = data;
    document.getElementById('docParaCount').textContent = data.results.length;
    renderReviewTable(data.results, data.paragraphs);

    bootstrap.Modal.getInstance(document.getElementById('splitModal')).hide();
    showToast('Paragraph split and both parts re-analyzed! ✅', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✂️ Split & Re-analyze';
  }
}


// ================================================================== //
//  Drag-and-Drop Reorder                                              //
// ================================================================== //

function initDragAndDrop() {
  const tbody = document.getElementById('reviewBody');
  let dragRow = null;

  tbody.addEventListener('dragstart', (e) => {
    const tr = e.target.closest('tr');
    if (!tr) return;
    dragRow = tr;
    tr.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', tr.dataset.idx);
  });

  tbody.addEventListener('dragend', (e) => {
    const tr = e.target.closest('tr');
    if (tr) tr.classList.remove('dragging');
    tbody.querySelectorAll('tr').forEach(r => r.classList.remove('drag-over'));
    dragRow = null;
  });

  tbody.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const tr = e.target.closest('tr');
    if (!tr || tr === dragRow) return;
    tbody.querySelectorAll('tr').forEach(r => r.classList.remove('drag-over'));
    tr.classList.add('drag-over');
  });

  tbody.addEventListener('drop', async (e) => {
    e.preventDefault();
    const targetTr = e.target.closest('tr');
    if (!targetTr || !dragRow || targetTr === dragRow) return;

    tbody.querySelectorAll('tr').forEach(r => r.classList.remove('drag-over'));

    // Move the row in DOM
    const allRows = Array.from(tbody.querySelectorAll('tr'));
    const fromIdx = allRows.indexOf(dragRow);
    const toIdx = allRows.indexOf(targetTr);

    if (fromIdx < toIdx) {
      targetTr.after(dragRow);
    } else {
      targetTr.before(dragRow);
    }

    // Build new_order from current DOM order
    const newRows = Array.from(tbody.querySelectorAll('tr'));
    const newOrder = newRows.map(r => parseInt(r.dataset.idx));

    // Save to backend
    try {
      const res = await fetch(`/api/document/${window.currentDocId}/paragraphs/reorder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_order: newOrder })
      });
      if (!res.ok) throw new Error('Reorder failed');

      const data = await res.json();
      window.docData = data;
      renderReviewTable(data.results, data.paragraphs);
      showToast('Paragraphs reordered! ✅', 'success');
    } catch (e) {
      showToast(e.message, 'error');
      // Reload to restore correct order
      await loadDocumentResults(window.currentDocId);
    }
  });
}


// ================================================================== //
//  Row Status, Edit, Regenerate, Submit (existing features)           //
// ================================================================== //

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
    status: 'Approved'
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

    setTimeout(() => {
      window.location.href = '/history.html';
    }, 1500);
  } catch (e) {
    showToast(e.message, 'error');
    btn.disabled = false;
    btn.textContent = '📨 Submit to Checker';
  }
}
