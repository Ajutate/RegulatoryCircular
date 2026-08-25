/* ===================================================
   app.js — Shared state, utilities & navigation
   =================================================== */

// ── State keys (localStorage) ──────────────────────
const STATE_KEYS = {
  DOC_META:    'rca_doc_meta',
  PARAGRAPHS:  'rca_paragraphs',
  RESULTS:     'rca_results',
  SESSION_ID:  'rca_session_id',
};

const State = {
  get(key)       { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } },
  set(key, val)  { localStorage.setItem(key, JSON.stringify(val)); },
  clear(key)     { localStorage.removeItem(key); },
  clearAll()     { Object.values(STATE_KEYS).forEach(k => localStorage.removeItem(k)); },
};

// ── User / Auth helpers ──────────────────────────
function getUser() {
  try { return JSON.parse(localStorage.getItem('rca_user')); } catch { return null; }
}

function requireAuth() {
  const user = getUser();
  const page = window.location.pathname.split('/').pop() || 'index.html';
  if (page === 'login.html') return; // don't redirect on login page
  if (!user) {
    window.location.href = '/login.html';
    return null;
  }
  return user;
}

function logout() {
  localStorage.removeItem('rca_user');
  State.clearAll();
  window.location.href = '/login.html';
}

// ── Toast notifications ──────────────────────────
const toastContainer = (() => {
  const el = document.createElement('div');
  el.className = 'toast-container';
  document.body.appendChild(el);
  return el;
})();

function showToast(msg, type = 'info', duration = 4000) {
  const icons = { info: 'ℹ️', success: '✅', error: '❌', warning: '⚠️' };
  const t = document.createElement('div');
  t.className = `toast ${type}`;
  t.innerHTML = `<span>${icons[type] || 'ℹ️'}</span><span>${msg}</span>`;
  toastContainer.appendChild(t);
  setTimeout(() => {
    t.style.animation = 'none';
    t.style.opacity = '0';
    t.style.transform = 'translateX(30px)';
    t.style.transition = 'all .3s ease';
    setTimeout(() => t.remove(), 300);
  }, duration);
}

// ── Confirm Modal ────────────────────────────────
function showConfirmModal(title, message, confirmText = 'Confirm', confirmStyle = 'danger') {
  return new Promise((resolve) => {
    const existing = document.getElementById('customConfirmModal');
    if (existing) existing.remove();

    const html = `
      <div class="modal fade" id="customConfirmModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content rounded-4 shadow">
            <div class="modal-header border-0 pb-0">
              <h5 class="modal-title fw-bold text-navy">${esc(title)}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body text-secondary" style="white-space: pre-wrap;">${esc(message)}</div>
            <div class="modal-footer border-0 pt-0">
              <button type="button" class="btn btn-secondary rounded-pill" data-bs-dismiss="modal">Cancel</button>
              <button type="button" class="btn btn-${confirmStyle} rounded-pill px-4" id="btnCustomConfirm">${esc(confirmText)}</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', html);
    const modalEl = document.getElementById('customConfirmModal');
    const modalInst = new bootstrap.Modal(modalEl);
    
    let resolved = false;

    document.getElementById('btnCustomConfirm').addEventListener('click', () => {
      resolved = true;
      resolve(true);
      modalInst.hide();
    });

    modalEl.addEventListener('hidden.bs.modal', () => {
      if (!resolved) resolve(false);
      modalEl.remove();
    });

    modalInst.show();
  });
}

// ── Alert Modal ──────────────────────────────────
function showAlertModal(title, message, type = 'info') {
  return new Promise((resolve) => {
    const existing = document.getElementById('customAlertModal');
    if (existing) existing.remove();

    let icon = 'ℹ️';
    let btnStyle = 'primary';
    let titleStyle = 'text-navy';

    if (type === 'success') { icon = '✅'; btnStyle = 'success'; titleStyle = 'text-success'; }
    if (type === 'error')   { icon = '❌'; btnStyle = 'danger'; titleStyle = 'text-danger'; }
    if (type === 'warning') { icon = '⚠️'; btnStyle = 'warning'; titleStyle = 'text-warning'; }

    const html = `
      <div class="modal fade" id="customAlertModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
          <div class="modal-content rounded-4 shadow">
            <div class="modal-header border-0 pb-0">
              <h5 class="modal-title fw-bold ${titleStyle}">${icon} ${esc(title)}</h5>
              <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
            </div>
            <div class="modal-body text-secondary" style="white-space: pre-wrap;">${esc(message)}</div>
            <div class="modal-footer border-0 pt-0">
              <button type="button" class="btn btn-${btnStyle} rounded-pill px-4" data-bs-dismiss="modal">OK</button>
            </div>
          </div>
        </div>
      </div>
    `;
    document.body.insertAdjacentHTML('beforeend', html);
    const modalEl = document.getElementById('customAlertModal');
    const modalInst = new bootstrap.Modal(modalEl);

    modalEl.addEventListener('hidden.bs.modal', () => {
      resolve();
      modalEl.remove();
    });

    modalInst.show();
  });
}

// ── Sidebar — role-based navigation ──────────────
const NAV_ITEMS = {
  admin: [
    { page: 'index.html',   icon: '🏠', label: 'Home' },
    { page: 'admin.html',   icon: '🛡️', label: 'Prompt Management' },
    { page: 'history.html', icon: '📜', label: 'History' },
  ],
  maker: [
    { page: 'index.html',   icon: '🏠', label: 'Home' },
    { page: 'upload.html',  icon: '📤', label: 'Upload Document' },
    { page: 'analyze.html', icon: '🔍', label: 'Analyze' },
    { page: 'history.html', icon: '📁', label: 'My Documents' },
  ],
  checker: [
    { page: 'index.html',   icon: '🏠', label: 'Home' },
    { page: 'checker.html', icon: '✅', label: 'Review Queue' },
    { page: 'history.html', icon: '📜', label: 'History' },
  ],
};

function initSidebar() {
  const user = getUser();
  const sidebarNav = document.getElementById('sidebarNav');

  // If sidebar uses static HTML nav items (older pages), handle click navigation
  const staticItems = document.querySelectorAll('.nav-item[data-page]');

  if (sidebarNav && user) {
    // Dynamic role-based sidebar
    const role = user.role || 'maker';
    const items = NAV_ITEMS[role] || NAV_ITEMS.maker;
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';

    let html = '<div class="nav-label">Navigation</div>';
    items.forEach(item => {
      const active = item.page === currentPage ? ' active' : '';
      const badgeHtml = (role === 'checker' && item.page === 'checker.html') 
        ? `<span id="queueBadge" class="badge bg-danger rounded-pill float-end" style="display:none; font-size: 0.75em;">0</span>` 
        : '';
      html += `<div class="nav-item${active}" data-page="${item.page}">
        <span class="nav-icon">${item.icon}</span> ${item.label} ${badgeHtml}
      </div>`;
    });

    // User info + logout at the bottom
    html += `
      <div class="sidebar-status mt-auto p-3">
        <h4 class="text-uppercase text-secondary" style="font-size:0.75rem; letter-spacing:1px; margin-bottom:1rem;">Logged In</h4>
        <div class="d-flex align-items-center justify-content-between mb-3">
          <span class="text-white" style="font-size:0.9rem;">👤 ${esc(user.username)}</span>
          <span class="badge bg-primary-subtle text-primary rounded-pill">${user.role.toUpperCase()}</span>
        </div>
        <button class="btn btn-sm btn-outline-light rounded-pill w-100" onclick="logout()">🚪 Logout</button>
      </div>`;

    sidebarNav.innerHTML = html;

    // Attach click handlers
    sidebarNav.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.addEventListener('click', () => {
        window.location.href = item.dataset.page;
      });
    });

    if (role === 'checker') {
      const updateBadge = async () => {
        try {
          const res = await fetch('/api/checker/pending_count');
          if (!res.ok) return;
          const data = await res.json();
          const badge = document.getElementById('queueBadge');
          if (badge) {
            if (data.count > 0) {
              badge.textContent = data.count;
              badge.style.display = 'inline-block';
            } else {
              badge.style.display = 'none';
            }
          }
        } catch (e) {}
      };
      updateBadge();
      setInterval(updateBadge, 10000); // Poll every 10 seconds
    }
  } else if (staticItems.length) {
    // Fallback: static sidebar items (mark active + attach click)
    const path = window.location.pathname.split('/').pop() || 'index.html';
    staticItems.forEach(item => {
      if (item.dataset.page === path) item.classList.add('active');
      item.addEventListener('click', () => {
        window.location.href = item.dataset.page;
      });
    });
  }
}

// ── Sidebar status badges ────────────────────────
function updateSidebarStatus() {
  const docMeta  = State.get(STATE_KEYS.DOC_META);
  const results  = State.get(STATE_KEYS.RESULTS);

  const dotDoc  = document.getElementById('statusDoc');
  const dotAna  = document.getElementById('statusAna');
  const countEl = document.getElementById('statusCount');

  if (dotDoc)  dotDoc.classList.toggle('done', !!docMeta);
  if (dotAna)  dotAna.classList.toggle('done', !!(results && results.length));
  if (countEl && results && results.length) {
    countEl.textContent = `${results.length} paragraphs analysed`;
    countEl.style.display = '';
  } else if (countEl) {
    countEl.style.display = 'none';
  }
}

// ── Fetch helpers ────────────────────────────────
async function postJSON(url, data) {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

async function postForm(url, formData) {
  const resp = await fetch(url, { method: 'POST', body: formData });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || resp.statusText);
  }
  return resp.json();
}

// ── Format bytes ─────────────────────────────────
function fmtSize(kb) {
  if (kb < 1024) return `${kb} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

// ── Badge helper ─────────────────────────────────
function badgeClass(text) {
  const t = (text || '').toLowerCase();
  if (t.includes('action') || t.includes('directive')) return 'badge-blue';
  if (t.includes('yes') || t.includes('complian'))     return 'badge-green';
  if (t.includes('no')  || t.includes('error'))        return 'badge-red';
  if (t.includes('advisory'))                          return 'badge-amber';
  if (t.includes('information'))                       return 'badge-gray';
  return 'badge-purple';
}

// ── Escape HTML ──────────────────────────────────
function esc(str) {
  return String(str ?? '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Mini bar chart (canvas) ──────────────────────
function drawBarChart(canvasId, labels, values, color = '#2e86c1') {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width = canvas.offsetWidth;
  const H = canvas.height = 200;
  ctx.clearRect(0, 0, W, H);

  if (!labels.length) return;

  const maxVal = Math.max(...values) || 1;
  const barW   = Math.max(20, Math.floor((W - 40) / labels.length) - 6);
  const gap    = Math.floor((W - 40 - barW * labels.length) / (labels.length + 1));
  const chartH = H - 50;

  labels.forEach((lbl, i) => {
    const x = 20 + gap + i * (barW + gap);
    const h = Math.round((values[i] / maxVal) * chartH);
    const y = chartH - h + 10;

    // Bar gradient
    const grad = ctx.createLinearGradient(0, y, 0, chartH + 10);
    grad.addColorStop(0, color);
    grad.addColorStop(1, color + '55');

    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(x, y, barW, h, 4);
    ctx.fill();

    // Value label
    ctx.fillStyle = '#0d1b2a';
    ctx.font = `bold ${Math.min(11, barW * .6)}px Inter,sans-serif`;
    ctx.textAlign = 'center';
    ctx.fillText(values[i], x + barW / 2, y - 4);

    // X label (truncated)
    ctx.fillStyle = '#475569';
    ctx.font = `${Math.min(10, barW * .5)}px Inter,sans-serif`;
    const short = lbl.length > 12 ? lbl.slice(0, 10) + '…' : lbl;
    ctx.fillText(short, x + barW / 2, H - 8);
  });
}

// ── Init on every page ───────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Auth guard (skip for login page)
  const page = window.location.pathname.split('/').pop() || 'index.html';
  if (page !== 'login.html') {
    requireAuth();
  }

  initSidebar();
  updateSidebarStatus();
});
