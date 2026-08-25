/* =============================================
   admin.js — Admin prompt management
   ============================================= */

document.addEventListener('DOMContentLoaded', async () => {
  const user = JSON.parse(localStorage.getItem('rca_user') || 'null');
  if (!user || user.role !== 'admin') {
    window.location.href = '/login.html';
    return;
  }

  await loadPrompts();

  document.getElementById('saveBtn').addEventListener('click', savePrompts);
  document.getElementById('resetBtn').addEventListener('click', resetPrompts);
});

async function loadPrompts() {
  try {
    const resp = await fetch('/api/admin/prompts');
    const data = await resp.json();

    document.getElementById('systemPrompt').value = data.system.content;
    document.getElementById('userPrompt').value = data.user.content;

    setBadge('systemBadge', data.system.is_custom);
    setBadge('userBadge', data.user.is_custom);
  } catch (err) {
    showToast('Failed to load prompts: ' + err.message, 'error');
  }
}

function setBadge(id, isCustom) {
  const el = document.getElementById(id);
  if (isCustom) {
    el.textContent = '✏️ Custom';
    el.className = 'badge rounded-pill bg-warning text-dark';
  } else {
    el.textContent = '📌 Default';
    el.className = 'badge rounded-pill bg-success';
  }
}

async function savePrompts() {
  const user = JSON.parse(localStorage.getItem('rca_user'));
  const btn = document.getElementById('saveBtn');
  btn.disabled = true;
  btn.textContent = 'Saving…';

  try {
    // Save system prompt
    await fetch('/api/admin/prompts', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt_type: 'system',
        content: document.getElementById('systemPrompt').value,
        user_id: user.id,
      }),
    });

    // Save user prompt
    await fetch('/api/admin/prompts', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt_type: 'user',
        content: document.getElementById('userPrompt').value,
        user_id: user.id,
      }),
    });

    showToast('Prompts saved successfully!', 'success');
    setBadge('systemBadge', true);
    setBadge('userBadge', true);
  } catch (err) {
    showToast('Save failed: ' + err.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '💾 Save Prompts';
  }
}

async function resetPrompts() {
  const confirmed = await showConfirmModal('Reset Prompts', 'Reset both prompts to their code defaults? Any custom edits will be lost.', 'Reset', 'danger');
  if (!confirmed) return;

  try {
    await fetch('/api/admin/prompts/system', { method: 'DELETE' });
    await fetch('/api/admin/prompts/user', { method: 'DELETE' });
    showToast('Prompts reset to defaults.', 'success');
    await loadPrompts();
  } catch (err) {
    showToast('Reset failed: ' + err.message, 'error');
  }
}
