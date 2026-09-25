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
      const [dashboard, usersPage] = await Promise.all([
        get('/api/admin/dashboard', controller.signal),
        get('/api/admin/users?page=1&page_size=100', controller.signal)
      ]);
      if (requestId !== requestSequence) return;
      renderDashboard(dashboard, usersPage.items || []);
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
function downloadBlobFile(response, filename) {
  return response.blob().then(blob => {
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = objectUrl;
    link.download = filename || 'download';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
  });
}
function downloadResumeFile(path, filename) {
  const authToken = token();
  if (!authToken) {
    showAuth('Admin access required.');
    return;
  }
  fetch(apiUrl(path), { headers: { Authorization: `Bearer ${authToken}` } })
    .then(async response => {
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || 'Resume download failed');
      }
      return downloadBlobFile(response, filename);
    })
    .catch(error => {
      const errorNode = document.querySelector('#error');
      if (errorNode) errorNode.textContent = error.message || 'Resume download failed.';
    });
}
function downloadMediaFile(path, filename) {
  const authToken = token();
  if (!authToken) {
    showAuth('Admin access required.');
    return;
  }
  fetch(apiUrl(path), { headers: { Authorization: `Bearer ${authToken}` } })
    .then(async response => {
      if (!response.ok) {
        const detail = await response.json().catch(() => ({}));
        throw new Error(detail.detail || 'Media download failed');
      }
      return downloadBlobFile(response, filename);
    })
    .catch(error => {
      const errorNode = document.querySelector('#error');
      if (errorNode) errorNode.textContent = error.message || 'Media download failed.';
    });
}
function renderUserDetail(user) {
  const panel = document.getElementById('user-detail-panel') || (() => {
    const block = document.createElement('section');
    block.id = 'user-detail-panel';
    block.style = 'margin-top:20px;';
    const container = document.querySelector('#dashboard-panel');
    if (container) container.appendChild(block);
    return block;
  })();
  const resumeButton = user.resume ? `<button type="button" class="btn btn-primary" data-resume-download="${escapeHtml(user.resume.download_url)}" data-resume-name="${escapeHtml(user.resume.filename || 'resume.pdf')}">Download resume PDF</button>` : '<span class="muted">No resume uploaded</span>';
  const mediaMarkup = (user.media || []).length ? user.media.map(media => `
    <div class="card" style="padding:12px 14px; margin-top:10px;">
      <strong>${escapeHtml(media.type || 'Media')}</strong>
      <div class="muted">${escapeHtml(media.filename || 'Capture')}</div>
      <div class="muted">${media.captured_at ? formatDate(media.captured_at) : '—'}</div>
      <div class="muted">${escapeHtml(JSON.stringify(media.metadata || {}))}</div>
      <button type="button" class="btn btn-quiet" data-media-download="${escapeHtml(media.download_url)}" data-media-name="${escapeHtml(media.filename || 'capture')}">Download</button>
    </div>
  `).join('') : '<div class="muted">No captured media metadata yet.</div>';
  const interviewsMarkup = (user.interviews || []).length ? user.interviews.map(interview => `
    <div class="card" style="padding:12px 14px; margin-top:10px;">
      <strong>${escapeHtml(interview.status)}</strong>
      <div class="muted">Score: ${interview.score == null ? '—' : escapeHtml(interview.score)}</div>
      <div class="muted">Started: ${formatDate(interview.created_at)}</div>
      <div class="muted">Duration: ${interview.duration_seconds == null ? '—' : `${interview.duration_seconds} sec`}</div>
      <div class="muted">ID: ${escapeHtml(interview.id)}</div>
    </div>
  `).join('') : '<div class="muted">No interviews yet.</div>';
  panel.innerHTML = `
    <div class="card panel" style="padding:18px;">
      <div class="panel-heading" style="margin-bottom:12px;">
        <h3>${escapeHtml(user.full_name || user.email)}</h3>
        <button type="button" class="btn btn-quiet" id="close-user-detail">Close</button>
      </div>
      <div style="display:flex; gap:12px; align-items:center; margin-bottom:18px;">
        <span style="display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,#e0e7ff,#c7d2fe);color:#1f2937;font-weight:700;">${escapeHtml(user.avatar_initials || 'U')}</span>
        <div>
          <div class="role">${escapeHtml(user.email)}</div>
          <div class="muted">Role: ${escapeHtml(user.role)} • Joined: ${formatDate(user.created_at)}</div>
        </div>
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:18px;">${resumeButton}</div>
      <div style="margin-bottom:18px;">
        <h4>Interview history</h4>
        ${interviewsMarkup}
      </div>
      <div>
        <h4>Captured photo/video metadata</h4>
        ${mediaMarkup}
      </div>
    </div>
  `;
  panel.hidden = false;
  document.getElementById('close-user-detail').addEventListener('click', () => { panel.hidden = true; panel.innerHTML = ''; });
  document.querySelectorAll('[data-resume-download]').forEach(button => {
    button.addEventListener('click', () => {
      const path = button.getAttribute('data-resume-download');
      const filename = button.getAttribute('data-resume-name') || 'resume.pdf';
      downloadResumeFile(path, filename);
    });
  });
  document.querySelectorAll('[data-media-download]').forEach(button => {
    button.addEventListener('click', () => {
      const path = button.getAttribute('data-media-download');
      const filename = button.getAttribute('data-media-name') || 'media';
      downloadMediaFile(path, filename);
    });
  });
}
async function loadUserDetail(userId) {
  try {
    const user = await get(`/api/admin/users/${userId}`);
    renderUserDetail(user);
  } catch (error) {
    const errorNode = document.querySelector('#error');
    if (errorNode) errorNode.textContent = error.message || 'Could not load user profile.';
  }
}
function renderDashboard(dashboard, users = dashboard.recent_users || []) {
  const metrics = [['Total users', dashboard.total_users], ['Active users', dashboard.active_users], ['Total resumes', dashboard.total_resumes], ['Total jobs', dashboard.total_jobs], ['Total interviews', dashboard.total_interviews], ['Completed interviews', dashboard.completed_interviews], ['AI requests', dashboard.ai_requests], ['AI failures', dashboard.ai_failures], ['Avg latency', `${dashboard.average_llm_latency_ms} ms`], ['Estimated AI cost', `$${Number(dashboard.estimated_ai_cost).toFixed(2)}`]];
  document.querySelector('#metrics').innerHTML = metrics.map(([label, value]) => `<article class="card stat-card"><div class="stat-top"><span>${label}</span></div><strong class="stat-value">${escapeHtml(value)}</strong></article>`).join('');
  document.querySelector('#user-count').textContent = `${users.length} total`;
  document.querySelector('#users').innerHTML = users.length ? users.map(user => {
    const initials = escapeHtml(user.avatar_initials || (user.full_name || user.email || 'U').slice(0, 2).toUpperCase());
    const resumeName = user.resume_filename ? escapeHtml(user.resume_filename) : 'No resume';
    const resumeLink = user.resume_url ? `<button type="button" class="btn btn-quiet" data-resume-download="${escapeHtml(user.resume_url)}" data-resume-name="${escapeHtml(user.resume_filename || 'resume.pdf')}" style="display:inline-block;margin-top:6px;">${resumeName}</button>` : '<span class="muted" style="display:inline-block;margin-top:6px;">No resume</span>';
    const detailButton = `<button type="button" class="btn btn-secondary" data-user-detail="${escapeHtml(user.id)}" style="margin-left:8px;">View profile</button>`;
    return `<tr><td><div style="display:flex;align-items:center;gap:10px;min-width:220px"><span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#e0e7ff,#c7d2fe);color:#1f2937;font-weight:700;font-size:12px;">${initials}</span><div><div class="role">${escapeHtml(user.full_name || 'Unknown user')}</div>${resumeLink}</div></div></td><td class="muted">${escapeHtml(user.email)}</td><td class="muted">${formatDate(user.created_at)}</td><td>${escapeHtml(user.role)}</td><td><span class="status">${user.is_active ? 'Active' : 'Inactive'}</span></td><td>${detailButton}</td></tr>`;
  }).join('') : emptyRow(6, 'No users yet.');
  document.querySelectorAll('[data-resume-download]').forEach(button => {
    button.addEventListener('click', () => {
      const path = button.getAttribute('data-resume-download');
      const filename = button.getAttribute('data-resume-name') || 'resume.pdf';
      downloadResumeFile(path, filename);
    });
  });
  document.querySelectorAll('[data-user-detail]').forEach(button => {
    button.addEventListener('click', () => {
      const userId = button.getAttribute('data-user-detail');
      if (userId) loadUserDetail(userId);
    });
  });
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
