function renderPreAnalysisTable() {
  const paras = State.get(STATE_KEYS.PARAGRAPHS) || [];
  const metaParasEl = document.getElementById('metaParas') || document.getElementById('docParas');
  if (metaParasEl) metaParasEl.textContent = paras.length;
  
  const tbody = document.getElementById('preAnalysisBody');
  tbody.innerHTML = '';
  
  paras.forEach((text, idx) => {
    const tr = document.createElement('tr');
    tr.dataset.idx = idx;
    tr.setAttribute('draggable', 'true');
    tr.innerHTML = `
      <td><span class="drag-handle" title="Drag onto another row to merge, or drag between rows to reorder">⠿</span></td>
      <td><input class="form-check-input row-checkbox" type="checkbox" data-idx="${idx}"></td>
      <td class="fw-bold ps-2">${idx + 1}</td>
      <td style="font-size: 0.85rem; line-height: 1.5; white-space: pre-wrap;" title="${esc(text)}">${esc(text)}</td>
      <td class="text-end pe-4">
        <div class="d-flex justify-content-end gap-1 flex-wrap">
          <button class="btn btn-sm btn-outline-info rounded-pill btn-split" data-idx="${idx}">✂️ Split</button>
          <button class="btn btn-sm btn-outline-danger rounded-pill btn-delete" data-idx="${idx}">🗑️ Delete</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });

  // Attach button events
  document.querySelectorAll('.btn-delete').forEach(btn => 
    btn.addEventListener('click', async () => {
      const confirmed = await showConfirmModal('Remove Paragraph', 'Are you sure you want to remove this paragraph? It will be excluded from AI analysis.', 'Remove', 'danger');
      if (confirmed) {
        deletePara(btn.dataset.idx);
      }
    })
  );
  document.querySelectorAll('.btn-split').forEach(btn => 
    btn.addEventListener('click', () => openSplitModal(btn.dataset.idx))
  );

  // Handle select all and merge button visibility
  const selectAll = document.getElementById('selectAllPreAnalysis');
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

  if (!tbody.dataset.dndInitialized) {
    initPreAnalysisDragAndDrop();
    tbody.dataset.dndInitialized = "true";
  }
}

function deletePara(idx) {
  let paras = State.get(STATE_KEYS.PARAGRAPHS);
  paras.splice(idx, 1);
  State.set(STATE_KEYS.PARAGRAPHS, paras);
  renderPreAnalysisTable();
  showToast('Paragraph deleted.', 'info');
}

// ================================================================== //
//  Drag-and-Drop Logic
// ================================================================== //

function initPreAnalysisDragAndDrop() {
  const tbody = document.getElementById('preAnalysisBody');
  let dragRow = null;
  let dropAction = null;

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
    clearAllDropIndicators(tbody);
    dragRow = null;
    dropAction = null;
  });

  tbody.addEventListener('dragover', (e) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    const tr = e.target.closest('tr');
    if (!tr || tr === dragRow) {
      clearAllDropIndicators(tbody);
      return;
    }

    const rect = tr.getBoundingClientRect();
    const y = e.clientY - rect.top;
    const edgeZone = rect.height * 0.25;

    clearAllDropIndicators(tbody);
    if (y < edgeZone) {
      tr.classList.add('reorder-above');
      dropAction = 'reorder-above';
    } else if (y > rect.height - edgeZone) {
      tr.classList.add('reorder-below');
      dropAction = 'reorder-below';
    } else {
      tr.classList.add('merge-drop-target');
      dropAction = 'merge';
    }
  });

  tbody.addEventListener('dragleave', (e) => {
    const tr = e.target.closest('tr');
    if (tr) tr.classList.remove('merge-drop-target', 'reorder-above', 'reorder-below');
  });

  tbody.addEventListener('drop', (e) => {
    e.preventDefault();
    const targetTr = e.target.closest('tr');
    if (!targetTr || !dragRow || targetTr === dragRow) return;

    const sourceIdx = parseInt(dragRow.dataset.idx);
    const targetIdx = parseInt(targetTr.dataset.idx);

    let paras = State.get(STATE_KEYS.PARAGRAPHS);
    const sourcePara = paras[sourceIdx];

    if (dropAction === 'merge') {
      // Merge
      if (sourceIdx < targetIdx) {
        paras[targetIdx] = sourcePara + '\n\n' + paras[targetIdx];
        paras.splice(sourceIdx, 1);
      } else {
        paras[targetIdx] = paras[targetIdx] + '\n\n' + sourcePara;
        paras.splice(sourceIdx, 1);
      }
      showToast('Paragraphs merged successfully.', 'success');
    } else {
      // Reorder
      paras.splice(sourceIdx, 1);
      const newTargetIdx = sourceIdx < targetIdx 
        ? (dropAction === 'reorder-above' ? targetIdx - 1 : targetIdx)
        : (dropAction === 'reorder-above' ? targetIdx : targetIdx + 1);
      paras.splice(newTargetIdx, 0, sourcePara);
    }
    
    State.set(STATE_KEYS.PARAGRAPHS, paras);
    renderPreAnalysisTable();
  });
}

function clearAllDropIndicators(tbody) {
  tbody.querySelectorAll('tr').forEach(r => 
    r.classList.remove('merge-drop-target', 'reorder-above', 'reorder-below')
  );
}

// ================================================================== //
//  Split Logic
// ================================================================== //

function openSplitModal(idx) {
  const paras = State.get(STATE_KEYS.PARAGRAPHS);
  const text = paras[idx];

  document.getElementById('splitIdx').value = idx;
  const editor = document.getElementById('splitPreviewTextarea');
  editor.innerHTML = '';
  editor.textContent = text; // Safely set text

  new bootstrap.Modal(document.getElementById('splitModal')).show();
}

const splitEditor = document.getElementById('splitPreviewTextarea');
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

document.getElementById('confirmSplitBtn')?.addEventListener('click', () => {
  const idx = parseInt(document.getElementById('splitIdx').value);
  const editor = document.getElementById('splitPreviewTextarea');
  
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

  let paras = State.get(STATE_KEYS.PARAGRAPHS);
  
  // Replace original with the new part(s)
  paras.splice(idx, 1, ...newParts);
  State.set(STATE_KEYS.PARAGRAPHS, paras);

  bootstrap.Modal.getInstance(document.getElementById('splitModal')).hide();
  renderPreAnalysisTable();
  
  if (newParts.length > 1) {
    showToast(`Paragraph split into ${newParts.length} parts.`, 'success');
  } else {
    showToast('Paragraph updated.', 'success');
  }
});

document.getElementById('mergeSelectedBtn')?.addEventListener('click', async () => {
  const checkedBoxes = Array.from(document.querySelectorAll('.row-checkbox:checked'));
  if (checkedBoxes.length < 2) return;
  
  const indices = checkedBoxes.map(cb => parseInt(cb.dataset.idx)).sort((a, b) => a - b);
  const confirmed = await showConfirmModal('🔗 Merge Paragraphs', `Merge ${indices.length} selected paragraphs together?`, 'Merge', 'primary');
  if (!confirmed) return;

  let paras = State.get(STATE_KEYS.PARAGRAPHS);
  const firstIdx = indices[0];
  const combinedText = indices.map(i => paras[i]).join('\n\n');
  paras[firstIdx] = combinedText;
  
  for (let i = indices.length - 1; i > 0; i--) {
    paras.splice(indices[i], 1);
  }
  
  State.set(STATE_KEYS.PARAGRAPHS, paras);
  renderPreAnalysisTable();
  
  const btn = document.getElementById('mergeSelectedBtn');
  if (btn) btn.style.display = 'none';
  showToast('Paragraphs merged successfully.', 'success');
});

