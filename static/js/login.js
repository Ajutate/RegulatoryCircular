/* =============================================
   login.js — Proper Username + Password login
   ============================================= */

document.addEventListener('DOMContentLoaded', () => {
  // If already logged in, redirect
  const user = JSON.parse(localStorage.getItem('rca_user') || 'null');
  if (user) {
    redirectByRole(user.role);
    return;
  }

  // Inputs
  const userInp = document.getElementById('loginUsername');
  const passInp = document.getElementById('loginPassword');
  
  userInp.addEventListener('input', checkReady);
  passInp.addEventListener('input', checkReady);

  // Login button
  document.getElementById('loginBtn').addEventListener('click', doLogin);

  // Enter key
  const handleEnter = (e) => {
    if (e.key === 'Enter' && !document.getElementById('loginBtn').disabled) {
      doLogin();
    }
  };
  userInp.addEventListener('keydown', handleEnter);
  passInp.addEventListener('keydown', handleEnter);
});

function checkReady() {
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value.trim();
  document.getElementById('loginBtn').disabled = !(username && password);
}

async function doLogin() {
  const username = document.getElementById('loginUsername').value.trim();
  const password = document.getElementById('loginPassword').value.trim();
  const errorEl = document.getElementById('loginError');
  const loginBtn = document.getElementById('loginBtn');
  
  errorEl.style.display = 'none';
  loginBtn.disabled = true;
  loginBtn.textContent = 'Authenticating...';

  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: 'Login failed' }));
      throw new Error(err.detail);
    }

    const data = await resp.json();
    localStorage.setItem('rca_user', JSON.stringify(data.user));
    redirectByRole(data.user.role);

  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.style.display = '';
    loginBtn.disabled = false;
    loginBtn.textContent = 'Login';
  }
}

function redirectByRole(role) {
  switch (role) {
    case 'admin':   window.location.href = '/admin.html';   break;
    case 'maker':   window.location.href = '/index.html';   break;
    case 'checker': window.location.href = '/checker.html'; break;
    default:        window.location.href = '/index.html';
  }
}
