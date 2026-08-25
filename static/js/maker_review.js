/* =============================================
   maker_review.js — Maker Review & Submit
   With: Drag-to-Merge, Split, Drag Reorder
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

  document.getElementById('submitBtn').addEventListener('click', submitDocument);
  document.getElementById('saveEditBtn').addEventListener('click', saveEdit);
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

    const needsRegen = r.needs_regeneration === true;
    const approveDisabled = needsRegen ? 'disabled title="Regenerate first"' : '';
    const regenBadge = needsRegen ? ' <span class="badge bg-warning text-dark">⚠️ Needs Regen</span>' : '';

    tr.innerHTML = `
      <td>
        <span class="drag-handle" title="Drag onto another row to merge, or drag to reorder">⠿</span>
      </td>
      <td><input class="form-check-input row-checkbox" type="checkbox" data-idx="${idx}"></td>
      <td class="fw-bold ps-2">${idx + 1}</td>
      <td style="font-size: 0.8rem; opacity: 0.8; max-width: 250px;" class="text-truncate" title="${esc(r.paragraph_text)}">
        ${esc(r.paragraph_text)}
      </td>
      <td><span class="badge ${badgeClass(r.para_type)}">${esc(r.para_type)}</span></td>
      <td>${esc(r.business_unit)}</td>
      <td>${esc(r.theme)}</td>
      <td id="statusCell_${idx}">${statusBadge}${regenBadge}</td>
      <td class="text-end pe-4">
        <div class="d-flex justify-content-end gap-1 flex-wrap">
          <button class="btn btn-sm btn-outline-success rounded-pill btn-approve-row" data-idx="${idx}" ${approveDisabled}>✅</button>
          <button class="btn btn-sm btn-outline-danger rounded-pill btn-reject-row" data-idx="${idx}" ${approveDisabled}>❌</button>
          <button class="btn btn-sm btn-outline-primary rounded-pill btn-edit" data-idx="${idx}">✏️ Edit</button>
          <button class="btn btn-sm btn-outline-warning rounded-pill btn-regenerate" data-idx="${idx}">🔄 Regen</button>
          <button class="btn btn-sm btn-outline-info rounded-pill btn-split" data-idx="${idx}">✂️ Split</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach row events
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

  // Initialize drag-and-drop (merge + reorder)
  if (!tbody.dataset.dndInitialized) {
    initDragAndDrop();
    tbody.dataset.dndInitialized = "true";
  }

  // Handle select all and merge button visibility
  const selectAll = document.getElementById('selectAllMaker');
  if (selectAll) {
    selectAll.checked = false;
    selectAll.addEventListener('change', (e) => {
      document.querySelectorAll('.row-checkbox').forEach(cb => cb.checked = e.target.checked);
      toggleMergeBtn();
    });
  }
  document.querySelectorAll('.row-checkbox').forEach(cb => cb.addEventListener('change', toggleMergeBtn));

  function toggleMergeBtn() {
    const checked = document.querySelectorAll('.row-checkbox:checked').length;
    const btn = document.getElementById('mergeSelectedBtn');
    if (btn) btn.style.display = checked > 1 ? 'inline-block' : 'none';
  }
  
  checkSubmitState();
}


// ================================================================== //
//  Drag-and-Drop: Merge + Reorder                                     //
//                                                                     //
//  Behaviour:                                                         //
//    - Drag a row and DROP ON TOP of another row → MERGE              //
//    - Drag a row and DROP BETWEEN rows (edge zone) → REORDER         //
//  Visual cues:                                                       //
//    - Merge: target row gets blue glow (merge-drop-target class)     //
//    - Reorder: green line appears between rows                       //
// ================================================================== //

function initDragAndDrop() {
  const tbody = document.getElementById('reviewBody');
  let dragRow = null;
  let dropAction = null; // 'merge' or 'reorder'

  tbody.addEventListener('dragstart', (e) => {
    const tr = e.target.closest('tr');
    if (!tr) return;
    dragRow = tr;
    tr.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', tr.dataset.idx);
  });

  tbody.addEventListener('dragend', () => {
    if (dragRow) dragRow.classList.remove('dragging');
    clearAllDropIndicators();
    dragRow = null;
    dropAction = null;
  });

  tbody.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';

    const tr = e.target.closest('tr');
    if (!tr || tr === dragRow) {
      clearAllDropIndicators();
      return;
    }

    // Determine if we're near the top/bottom edge (reorder) or centre (merge)
    const rect = tr.getBoundingClientRect();
    const y = e.clientY - rect.top;
    const edgeZone = rect.height * 0.25; // top/bottom 25% = reorder zone

    clearAllDropIndicators();

    if (y < edgeZone) {
      // Top edge → reorder above
      tr.classList.add('reorder-above');
      dropAction = 'reorder-above';
    } else if (y > rect.height - edgeZone) {
      // Bottom edge → reorder below
      tr.classList.add('reorder-below');
      dropAction = 'reorder-below';
    } else {
      // Centre → merge
      tr.classList.add('merge-drop-target');
      dropAction = 'merge';
    }
  });

  tbody.addEventListener('dragleave', (e) => {
    const tr = e.target.closest('tr');
    if (tr) {
      tr.classList.remove('merge-drop-target', 'reorder-above', 'reorder-below');
    }
  });

  tbody.addEventListener('drop', async (e) => {
    e.preventDefault();
    const targetTr = e.target.closest('tr');
    if (!targetTr || !dragRow || targetTr === dragRow) return;

    const fromIdx = parseInt(dragRow.dataset.idx);
    const toIdx = parseInt(targetTr.dataset.idx);

    clearAllDropIndicators();

    if (dropAction === 'merge') {
      await performMerge(fromIdx, toIdx);
    } else if (dropAction === 'reorder-above' || dropAction === 'reorder-below') {
      await performReorder(dragRow, targetTr, dropAction);
    }
  });

  function clearAllDropIndicators() {
    tbody.querySelectorAll('tr').forEach(r => {
      r.classList.remove('merge-drop-target', 'reorder-above', 'reorder-below');
    });
  }
}


// ================================================================== //
//  Merge (drag one row onto another)                                  //
// ================================================================== //

async function performMerge(fromIdx, toIdx) {
  const fromText = window.docData.results[fromIdx]?.paragraph_text || '';
  const toText = window.docData.results[toIdx]?.paragraph_text || '';

  const preview = `Paragraph ${fromIdx + 1}: "${fromText.substring(0, 80)}..."\n\n` +
                  `Paragraph ${toIdx + 1}: "${toText.substring(0, 80)}..."`;

  const confirmed = await showConfirmModal('🔗 Merge Paragraphs', `Merge these 2 paragraphs?\n\n${preview}`, 'Merge', 'primary');
  if (!confirmed) return;

  // Show loading state
  showToast('Merging paragraphs...', 'info');
  disableTable(true);

  try {
    const indices = [fromIdx, toIdx].sort((a, b) => a - b);
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
    showToast('Merge successful! Click Regenerate when ready.', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    disableTable(false);
  }
}


// ================================================================== //
//  Reorder (drag row to edge of another row)                          //
// ================================================================== //

async function performReorder(dragRow, targetTr, position) {
  const allRows = Array.from(document.getElementById('reviewBody').querySelectorAll('tr'));

  // Remove dragRow from its current position in the DOM
  dragRow.remove();

  // Insert at new position
  if (position === 'reorder-above') {
    targetTr.before(dragRow);
  } else {
    targetTr.after(dragRow);
  }

  // Build new_order from current DOM order
  const newRows = Array.from(document.getElementById('reviewBody').querySelectorAll('tr'));
  const newOrder = newRows.map(r => parseInt(r.dataset.idx));

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
    await loadDocumentResults(window.currentDocId);
  }
}


// ================================================================== //
//  Split Logic                                                        //
// ================================================================== //

function openSplitModal(idx) {
  const result = window.docData.results[idx];
  const text = result.paragraph_text;

  document.getElementById('splitIdx').value = idx;
  const editor = document.getElementById('splitPreview');
  editor.innerHTML = '';
  editor.textContent = text; // Safely set text

  new bootstrap.Modal(document.getElementById('splitModal')).show();
}

const splitEditor = document.getElementById('splitPreview');
splitEditor?.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    e.preventDefault();
    const selection = window.getSelection();
    if (!selection.rangeCount) return;
    const range = selection.getRangeAt(0);
    range.deleteContents();
    
    // Create HR
    const hr = document.createElement('hr');
    hr.style.cssText = 'border: none; border-top: 2px dashed red; margin: 10px 0;';
    hr.className = 'split-divider';
    
    // Insert a zero-width space after HR to allow cursor placement
    const textNode = document.createTextNode('\u200B');
    
    const fragment = document.createDocumentFragment();
    fragment.appendChild(hr);
    fragment.appendChild(textNode);
    
    range.insertNode(fragment);
    
    // Move cursor after the HR
    range.setStart(textNode, 1);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
  }
});

async function confirmSplit() {
  const idx = parseInt(document.getElementById('splitIdx').value);
  const editor = document.getElementById('splitPreview');
  const btn = document.getElementById('confirmSplitBtn');

  // Parse out the HRs by replacing them with a delimiter in a clone
  const clone = editor.cloneNode(true);
  clone.querySelectorAll('hr.split-divider').forEach(hr => {
    hr.parentNode.replaceChild(document.createTextNode('|||SPLIT|||'), hr);
  });
  
  const newText = clone.innerText || clone.textContent;

  if (!newText.trim()) {
    showToast('Paragraph cannot be empty.', 'warning');
    return;
  }

  // Split the content by our delimiter and clean up zero-width spaces
  const newParts = newText.split('|||SPLIT|||')
    .map(p => p.replace(/\u200B/g, '').trim())
    .filter(p => p);

  if (newParts.length < 2) {
    showToast('Please insert a split point by pressing Enter.', 'warning');
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Splitting...';

  try {
    const res = await fetch(`/api/document/${window.currentDocId}/paragraphs/split`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ index: idx, new_parts: newParts })
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
    showToast('Split successful! Click Regenerate when ready.', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '✂️ Split';
  }
}


// ================================================================== //
//  Helpers                                                            //
// ================================================================== //

function disableTable(disabled) {
  const table = document.getElementById('reviewTable');
  if (disabled) {
    table.style.opacity = '0.5';
    table.style.pointerEvents = 'none';
  } else {
    table.style.opacity = '1';
    table.style.pointerEvents = '';
  }
}

function checkSubmitState() {
  const btn = document.getElementById('submitBtn');
  if (!window.docData || !window.docData.results) return;

  const notApproved = window.docData.results.filter(r => r.status !== 'Approved').length;
  const needsRegen = window.docData.results.filter(r => r.needs_regeneration === true).length;
  const blocked = notApproved > 0 || needsRegen > 0;
  btn.disabled = blocked;
  if (needsRegen > 0) {
    btn.title = `${needsRegen} paragraph(s) need regeneration before submitting.`;
  } else if (notApproved > 0) {
    btn.title = 'All paragraphs must be approved before submitting.';
  } else {
    btn.title = '';
  }
}


// ================================================================== //
//  Row Status, Edit, Regenerate, Submit                               //
// ================================================================== //

async function updateRowStatus(idx, status) {
  // Client-side guard: block if paragraph needs regeneration
  if (window.docData.results[idx]?.needs_regeneration) {
    showToast('This paragraph was modified (merged/split). Please regenerate it first.', 'warning');
    return;
  }
  try {
    const res = await fetch(`/api/document/${window.currentDocId}/paragraph/${idx}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Update failed');
    }

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
    const res = await fetch(`/api/document/${window.currentDocId}/paragraph/${idx}`, {
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
  btn.disabled = true;
  const originalText = btn.innerHTML;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

  try {
    const res = await fetch(`/api/document/${window.currentDocId}/paragraph/${idx}/regenerate`, {
      method: 'POST'
    });
    if (!res.ok) throw new Error('Regenerate failed');

    const data = await res.json();
    Object.assign(window.docData.results[idx], data.result);
    window.docData.results[idx].status = 'Pending';
    window.docData.results[idx].needs_regeneration = false;
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
  const notApproved = window.docData.results.filter(r => r.status !== 'Approved').length;
  if (notApproved > 0) {
    showToast('All paragraphs must be approved before submitting to Checker.', 'warning');
    return;
  }

  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = 'Submitting...';

  try {
    const res = await fetch(`/api/maker/submit/${window.currentDocId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: user.id })
    });
    if (!res.ok) throw new Error('Submit failed');

    showToast('Document submitted for Checker review! ✅', 'success');
    document.getElementById('docStatus').textContent = 'PENDING_REVIEW';
    setTimeout(() => { window.location.href = '/history.html'; }, 1500);
  } catch (e) {
    showToast(e.message, 'error');
    btn.disabled = false;
    btn.textContent = '📨 Submit to Checker';
  }
}

document.getElementById('mergeSelectedBtn')?.addEventListener('click', async () => {
  const checkedBoxes = Array.from(document.querySelectorAll('.row-checkbox:checked'));
  if (checkedBoxes.length < 2) return;
  
  const indices = checkedBoxes.map(cb => parseInt(cb.dataset.idx)).sort((a, b) => a - b);
  const confirmed = await showConfirmModal('🔗 Merge Paragraphs', `Merge ${indices.length} selected paragraphs together?`, 'Merge', 'primary');
  if (!confirmed) return;

  showToast('Merging paragraphs...', 'info');
  disableTable(true);

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
    
    const btn = document.getElementById('mergeSelectedBtn');
    if (btn) btn.style.display = 'none';
    showToast('Merge successful! Click Regenerate when ready.', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    disableTable(false);
  }
});
