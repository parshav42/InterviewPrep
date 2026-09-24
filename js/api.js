export const API_BASE_URL = (() => {
  const host = window.location.hostname;
  const isLocal = host === '127.0.0.1' || host === 'localhost';
  return isLocal ? 'http://127.0.0.1:8002/api' : '/api';
})();

function apiUrl(path) {
  const normalizedPath = path.startsWith('/api/') ? path.slice(4) : path;
  return `${API_BASE_URL}${normalizedPath}`;
}

export function setAuthToken(token) { localStorage.setItem('interviewai_access_token', token); }
export function clearAuthToken() { localStorage.removeItem('interviewai_access_token'); }
export function getAuthToken() { return localStorage.getItem('interviewai_access_token'); }

function validationMessage(item) {
  if (typeof item === 'string') return item;
  if (item && typeof item === 'object') {
    const location = Array.isArray(item.loc) ? item.loc.filter(Boolean).join('.') : '';
    return location ? `${location}: ${item.msg || 'Invalid value'}` : (item.msg || item.detail || JSON.stringify(item));
  }
  return String(item);
}

export function normalizeApiError(error, fallback = 'Something went wrong. Please try again.') {
  if (error instanceof TypeError) return 'Unable to reach the server. Check your connection and try again.';
  if (typeof error === 'string') return error;
  if (error?.detail) return Array.isArray(error.detail) ? error.detail.map(validationMessage).join('; ') : validationMessage(error.detail);
  if (Array.isArray(error)) return error.map(validationMessage).join('; ');
  if (error?.message && error.message !== '[object Object]') return error.message;
  return fallback;
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (!(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const token = getAuthToken();
  if (token) headers.set('Authorization', `Bearer ${token}`);
  const response = await fetch(apiUrl(path), { ...options, headers, credentials: 'include' });
  if (!response.ok) {
    const detail = await response.json().catch(() => null);
    if (response.status === 401) clearAuthToken();
    const message = response.status === 409 && detail?.detail?.toLowerCase().includes('email')
      ? 'This email is already registered. Please sign in.'
      : normalizeApiError(detail, `Request failed with status ${response.status}`);
    const error = new Error(message);
    error.status = response.status;
    error.detail = detail?.detail;
    throw error;
  }
  return response.status === 204 ? null : response.json();
}

export const authApi = {
  register: async payload => { const result = await api('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) }); setAuthToken(result.access_token); return result; },
  login: async payload => { const result = await api('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) }); setAuthToken(result.access_token); return result; },
  me: () => api('/api/user/profile'),
  logout: async () => { try { await api('/api/auth/logout', { method: 'POST' }); } finally { clearAuthToken(); } }
};

export const userApi = {
  profile: () => api('/api/user/profile'),
  credits: () => api('/api/user/credits')
};

export const paymentApi = {
  createOrder: plan => api('/api/payments/create-order', { method: 'POST', body: JSON.stringify({ plan }) }),
  verify: payload => api('/api/payments/verify', { method: 'POST', body: JSON.stringify(payload) })
};

export const resumeApi = {
  upload: file => { const form = new FormData(); form.append('file', file); return api('/api/resumes/upload', { method: 'POST', body: form }); },
  list: () => api('/api/resumes'),
  remove: id => api(`/api/resumes/${id}`, { method: 'DELETE' })
};

export const jobApi = {
  list: () => api('/api/jobs')
};

export const interviewApi = {
  create: payload => api('/api/interviews', { method: 'POST', body: JSON.stringify(payload) }),
  start: id => api(`/api/interviews/${id}/start`, { method: 'POST' }),
  currentQuestion: id => api(`/api/interviews/${id}/questions/current`),
  answer: (id, payload) => api(`/api/interviews/${id}/answer`, { method: 'POST', body: JSON.stringify(payload) }),
  end: id => api(`/api/interviews/${id}/end`, { method: 'POST' }),
  get: id => api(`/api/interviews/${id}`),
  history: () => api('/api/interviews'),
  feedback: id => api(`/api/interviews/${id}/feedback`)
};
