import { API_BASE_URL } from './js/api.js';

const TOKEN_KEY = 'interviewai_access_token';
const REFRESH_INTERVAL_MS = 15000;
let refreshTimer;
let activeRequest;
let requestSequence = 0;

function apiUrl(path) {
  const normalizedPath = path.startsWith('/api/') ? path.slice(4) : path;
  return `${API_BASE_URL}${normalizedPath}`;
}

function token() { return localStorage.getItem(TOKEN_KEY); }
function setToken(value) { localStorage.setItem(TOKEN_KEY, value); }
function clearToken() { localStorage.removeItem(TOKEN_KEY); }

async function login(email, password) {
  const response = await fetch(apiUrl('/api/auth/login'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Login failed');
  if (body.user?.role !== 'ADMIN') { clearToken(); throw new Error('Admin access required.'); }
  setToken(body.access_token);
}

async function get(path, signal) {
  const response = await fetch(apiUrl(path), { headers: { Authorization: `Bearer ${token()}` }, signal });
  if (response.status === 401 || response.status === 403) { clearToken(); showAuth('Admin access required.'); throw new Error('Admin access required.'); }
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

function showAuth(message = '') {
  document.querySelector('#auth-panel').hidden = false;
  document.querySelector('#dashboard-panel').hidden = true;
  document.querySelector('#auth-error').textContent = message;
}

function showDashboard() {
  document.querySelector('#auth-panel').hidden = true;
  document.querySelector('#dashboard-panel').hidden = false;
}

async function load() {
  if (activeRequest) return activeRequest;
  const requestId = ++requestSequence;
  const controller = new AbortController();
  const error = document.querySelector('#error');
  error.textContent = '';
  activeRequest = (async () => {
    try {
      const dashboard = await get('/api/admin/dashboard', controller.signal);
      if (requestId !== requestSequence) return;
      renderDashboard(dashboard);
      document.querySelector('#last-updated').textContent = `Last updated ${new Date().toLocaleTimeString()}`;
    } catch (loadError) {
      if (loadError.name !== 'AbortError' && requestId === requestSequence) error.textContent = 'Dashboard data is temporarily unavailable. Please try again.';
    } finally {
      if (requestId === requestSequence) activeRequest = null;
    }
  })();
  return activeRequest;
}

function escapeHtml(value) { return String(value ?? '').replace(/[&<>'"]/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]); }
function formatDate(value) { return value ? new Date(value).toLocaleString() : '—'; }
function emptyRow(columns, message) { return `<tr><td colspan="${columns}" class="muted">${message}</td></tr>`; }
function renderDashboard(dashboard) {
  const metrics = [['Total users', dashboard.total_users], ['Active users', dashboard.active_users], ['Total resumes', dashboard.total_resumes], ['Total jobs', dashboard.total_jobs], ['Total interviews', dashboard.total_interviews], ['Completed interviews', dashboard.completed_interviews], ['AI requests', dashboard.ai_requests], ['AI failures', dashboard.ai_failures], ['Avg latency', `${dashboard.average_llm_latency_ms} ms`], ['Estimated AI cost', `$${Number(dashboard.estimated_ai_cost).toFixed(2)}`]];
  document.querySelector('#metrics').innerHTML = metrics.map(([label, value]) => `<article class="card stat-card"><div class="stat-top"><span>${label}</span></div><strong class="stat-value">${escapeHtml(value)}</strong></article>`).join('');
  const users = dashboard.recent_users || [];
  document.querySelector('#user-count').textContent = `${dashboard.total_users} total`;
  document.querySelector('#users').innerHTML = users.length ? users.map(user => `<tr><td class="role">${escapeHtml(user.full_name)}</td><td class="muted">${escapeHtml(user.email)}</td><td class="muted">${formatDate(user.created_at)}</td><td>${escapeHtml(user.role)}</td><td><span class="status">${user.is_active ? 'Active' : 'Inactive'}</span></td></tr>`).join('') : emptyRow(5, 'No users yet.');
  const interviews = dashboard.recent_interviews || [];
  document.querySelector('#interview-count').textContent = `${dashboard.total_interviews} total`;
  document.querySelector('#interviews').innerHTML = interviews.length ? interviews.map(interview => `<tr><td class="role">${escapeHtml(interview.id)}</td><td class="muted">${escapeHtml(interview.user_id)}</td><td class="muted">${formatDate(interview.created_at)}</td><td><span class="status">${escapeHtml(interview.status)}</span></td><td>${interview.score == null ? '—' : escapeHtml(interview.score)}</td></tr>`).join('') : emptyRow(5, 'No interviews yet.');
}

function startRefresh() { clearInterval(refreshTimer); refreshTimer = setInterval(load, REFRESH_INTERVAL_MS); }
function stopRefresh() { clearInterval(refreshTimer); refreshTimer = undefined; requestSequence += 1; }

document.querySelector('#admin-login').addEventListener('click', async () => {
  const error = document.querySelector('#auth-error');
  error.textContent = '';
  try { await login(document.querySelector('#admin-email').value, document.querySelector('#admin-password').value); showDashboard(); await load(); }
  catch (loginError) { error.textContent = loginError.message; }
});
document.querySelector('#refresh').addEventListener('click', load);
document.querySelector('#admin-logout').addEventListener('click', () => { stopRefresh(); clearToken(); showAuth(''); });

if (token()) { showDashboard(); load(); startRefresh(); } else showAuth('');
