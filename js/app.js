import { api, authApi, getAuthToken, interviewApi, jobApi, normalizeApiError, paymentApi, resumeApi, userApi } from './api.js?v=integration4';
import { BrowserSpeechToTextProvider, BrowserTextToSpeechProvider, requestInterviewCamera, requestInterviewMicrophone, stopInterviewMedia } from './voice.js';

const app = document.querySelector('#app');
const toastRegion = document.querySelector('#toast-region');
const VOICE_SILENCE_TIMEOUT_MS = 30000;
const MIN_ANSWER_LENGTH = 10;

const icons = {
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 16V4m0 0L8 8m4-4 4 4M5 14v5h14v-5"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3H6v18h12V7l-4-4Z"/><path d="M14 3v4h4"/></svg>',
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="8" y="3" width="8" height="12" rx="4"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></svg>',
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/></svg>',
  speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 10v4h4l5 4V6l-5 4H4ZM17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="m19.4 15 .1.1-1.7 2.9-.2-.1a2 2 0 0 0-2.2.1l-.1.1a2 2 0 0 0-.9 1.8v.2h-3.4v-.2a2 2 0 0 0-1-1.8l-.1-.1a2 2 0 0 0-2.2-.1l-.2.1-1.7-2.9.1-.1a2 2 0 0 0 .3-2.2v-.2a2 2 0 0 0-1.8-1h-.2V8.2h.2a2 2 0 0 0 1.8-1l.1-.2a2 2 0 0 0-.3-2.2l-.1-.1 1.7-2.9.2.1a2 2 0 0 0 2.2-.1l.1-.1a2 2 0 0 0 1-1.8v-.2h3.4v.2a2 2 0 0 0 .9 1.8l.1.1a2 2 0 0 0 2.2.1l.2-.1 1.7 2.9-.1.1a2 2 0 0 0-.3 2.2v.2a2 2 0 0 0 1.8 1h.2v3.4h-.2a2 2 0 0 0-1.8 1l-.1.2a2 2 0 0 0 .3 2.2Z"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3ZM19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/></svg>'
};
const state = { view: window.location.hash === '#login' || !getAuthToken() ? 'auth' : 'dashboard', authMode: 'login', user: null, creditBalance: null, resumes: [], jobs: [], interviews: [], resume: null, resumeError: null, role: '', jobDescription: '', type: 'Mixed Interview', difficulty: 'Intermediate', duration: '30 min', timer: 1722, question: 1, recording: false, cameraStatus: 'CAMERA_OFF', microphoneStatus: 'MIC_OFF', speaker: true, interviewState: 'IDLE', mediaStream: null, microphoneStream: null, speechRecognition: null, textToSpeech: null, transcript: '', interimTranscript: '', answerStartedAt: 0, silenceTimer: null, processingAnswer: false, isSubmitting: false, silencePrompt: false, voiceInitialized: false, sttFallback: false };

function openBuyPanel() {
  console.log('openBuyPanel()');
  document.getElementById('buy-panel')?.remove();
  const panel = document.createElement('div');
  panel.id = 'buy-panel';
  panel.className = 'buy-panel';
  panel.style.cssText = `
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(15, 23, 42, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  `;
  panel.innerHTML = `
    <div style="background:#fff;padding:24px;border-radius:12px;min-width:320px;max-width:480px;width:min(90vw,480px);box-shadow:0 20px 50px rgba(0,0,0,.25);">
      <h3 style="margin:0 0 16px;font-size:18px">Choose a plan</h3>
      <button type="button" data-plan="starter" class="btn btn-primary" style="display:block;width:100%;margin-bottom:8px">
        1 interview — ₹49
      </button>
      <button type="button" data-plan="pro" class="btn btn-primary" style="display:block;width:100%;margin-bottom:16px">
        10 interviews — ₹499
      </button>
      <button type="button" data-close-buy class="btn btn-secondary" style="width:100%">Close</button>
    </div>
  `;
  document.body.appendChild(panel);

  panel.querySelector('[data-close-buy]').onclick = () => panel.remove();

  panel.querySelectorAll('[data-plan]').forEach(button => {
    button.onclick = async () => {
      const plan = button.getAttribute('data-plan');
      console.log('Plan selected:', plan);
      try {
        const response = await paymentApi.createOrder(plan);
        if (typeof window.Razorpay !== 'function') {
          throw new Error('Payment checkout is unavailable. Please refresh and try again.');
        }

        const rzp = new window.Razorpay({
          key: response.key_id,
          amount: response.amount_paise,
          currency: 'INR',
          order_id: response.order_id,
          name: 'InterviewAI',
          description: plan === 'pro' ? '10 interviews' : '1 interview',
          theme: { color: '#4F46E5' },
          handler: async (result) => {
            try {
              await paymentApi.verify({
                razorpay_order_id: result.razorpay_order_id,
                razorpay_payment_id: result.razorpay_payment_id,
                razorpay_signature: result.razorpay_signature,
              });
              await refreshCredits();
              panel.remove();
              showToast('Payment successful');
            } catch (error) {
              console.error(error);
              showToast('Payment verification failed', normalizeApiError(error));
            }
          },
        });
        rzp.open();
      } catch (error) {
        console.error(error);
        showToast('Could not create payment order', normalizeApiError(error));
      }
    };
  });
}

function showToast(title, detail = '') { const toast = document.createElement('div'); toast.className = 'toast'; toast.innerHTML = `<strong>${title}</strong><span>${detail}</span>`; toastRegion.append(toast); setTimeout(() => toast.remove(), 3400); }
function icon(name) { return icons[name] || ''; }
function formatTime(seconds) { return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; }
function userInitials() { return (state.user?.full_name || 'User').split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase(); }
function creditsMarkup() {
  const balance = Number.isFinite(state.creditBalance) ? state.creditBalance : 0;
  if (balance > 0) return `<span class="credits">Credits: ${balance} interviews</span>`;
  return '<button class="btn btn-secondary" id="buy-credits" type="button">Buy</button>';
}
function header() { return `<header class="topbar"><button class="brand" data-view="dashboard" aria-label="Go to dashboard"><span class="brand-text">InterviewAI</span></button><nav class="nav-links" aria-label="Primary"><button class="nav-link ${state.view === 'dashboard' ? 'active' : ''}" data-view="dashboard">Dashboard</button><button class="nav-link ${['resume','setup','interview'].includes(state.view) ? 'active' : ''}" data-view="resume">Practice</button><button class="nav-link ${state.view === 'history' ? 'active' : ''}" data-view="history">History</button></nav><div class="nav-actions">${creditsMarkup()}<button class="profile-chip" data-view="profile"><span class="avatar">${userInitials()}</span><span>${state.user?.full_name || 'Account'}</span><span>⌄</span></button><button class="icon-btn mobile-menu" aria-label="Open menu">☰</button></div></header>`; }
function resetUserState() { cleanupRealtimeInterview(); Object.assign(state, { view: 'auth', user: null, resumes: [], jobs: [], interviews: [], resume: null, resumeError: null, role: '', jobDescription: '', interviewId: null, currentQuestionId: null, remoteQuestion: null, transcript: '', interimTranscript: '', feedback: null, interviewState: 'IDLE' }); }
async function logout() { await authApi.logout(); resetUserState(); window.history.replaceState({}, '', '#login'); render(); }
function setupProfileMenu() { const trigger = document.querySelector('.profile-chip'); if (!trigger) return; trigger.removeAttribute('data-view'); trigger.setAttribute('aria-expanded', 'false'); const menu = document.createElement('div'); menu.className = 'profile-menu'; menu.innerHTML = '<button class="profile-menu-item" data-view="profile">Profile / Settings</button>'; trigger.parentElement.append(menu); trigger.addEventListener('click', event => { event.stopPropagation(); const open = menu.classList.toggle('open'); trigger.setAttribute('aria-expanded', String(open)); }); if (!document.body.dataset.profileMenuBound) { document.addEventListener('click', event => { const openMenu = document.querySelector('.profile-menu.open'); if (openMenu && !event.target.closest('.profile-menu') && !event.target.closest('.profile-chip')) { openMenu.classList.remove('open'); document.querySelector('.profile-chip')?.setAttribute('aria-expanded', 'false'); } }); document.body.dataset.profileMenuBound = 'true'; } }
async function refreshCredits() {
  try {
    const profileResult = await userApi.profile().catch(() => null);
    const credits = profileResult?.credits ?? (await userApi.credits().catch(() => ({ balance_interviews: 0 })));
    const balance = Number(credits.balance_interviews ?? credits.balance_minutes ?? 0);
    state.creditBalance = balance;

    document.querySelectorAll('.credits-display').forEach(element => {
      element.textContent = `Credits: ${balance} interview${balance === 1 ? '' : 's'}`;
    });
    document.querySelectorAll('[data-buy]').forEach(element => {
      element.style.display = balance === 0 ? '' : 'none';
    });
  } catch (error) {
    console.error('refreshCredits failed', error);
  }
}
async async function purchasePlan(plan) {
  try {
    const response = await paymentApi.createOrder(plan);
    document.querySelector('#credits-panel')?.remove();
    if (typeof window.Razorpay !== 'function') throw new Error('Payment checkout is unavailable. Please refresh and try again.');
    const checkout = new window.Razorpay({
      key: response.key_id,
      amount: response.amount_paise,
      currency: 'INR',
      order_id: response.order_id,
      name: 'InterviewAI',
      description: plan === 'pro' ? 'Pro - 10 interviews' : 'Starter - 1 interview',
      handler: async result => {
        try {
          await paymentApi.verify({
            razorpay_order_id: result.razorpay_order_id,
            razorpay_payment_id: result.razorpay_payment_id,
            razorpay_signature: result.razorpay_signature
          });
          await refreshCredits();
          showToast('Payment successful. Credits added.');
        } catch (error) {
          showToast('Payment verification failed', normalizeApiError(error));
        }
      },
      modal: { ondismiss: () => showToast('Payment cancelled') },
      theme: { color: '#5b21b6' }
    });
    checkout.open();
  } catch (error) {
    showToast('Could not create payment order', normalizeApiError(error));
  }
}
function shell(content, noHeader = false) { app.innerHTML = `<div class="app-shell">${noHeader ? '' : header()}${content}</div>`; setupProfileMenu(); bindEvents(); }
function pageHeading(eyebrow, title, subtitle, action = '') { return `<div class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p class="subtle">${subtitle}</p></div>${action}</div>`; }
function dashboard() { shell(`<main class="page">${pageHeading('Wednesday, September 23', 'Good afternoon, Alex', 'Ready for your next interview?', '<button class="btn btn-primary" data-view="resume">Start new interview ' + icon('arrow') + '</button>')}<section class="stat-grid"><article class="card stat-card"><div class="stat-top"><span>Interviews completed</span><span class="stat-icon">↗</span></div><strong class="stat-value">12</strong><span class="muted">+3 this month</span></article><article class="card stat-card"><div class="stat-top"><span>Practice time</span><span class="stat-icon">◷</span></div><strong class="stat-value">8.5h</strong><span class="muted">+1.2h this month</span></article><article class="card stat-card"><div class="stat-top"><span>Average score</span><span class="stat-icon">✦</span></div><strong class="stat-value">82%</strong><span class="muted">Top 18% of users</span></article><article class="card stat-card"><div class="stat-top"><span>Current streak</span><span class="stat-icon">♢</span></div><strong class="stat-value">6 days</strong><span class="muted">Personal best: 14</span></article></section><section class="dashboard-grid"><article class="card panel"><div class="panel-heading"><h3>Recent practice</h3><button class="btn btn-quiet" data-view="history">View all ${icon('arrow')}</button></div><div class="activity-list"><div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>Machine Learning Engineer</strong><span>Technical + Behavioral · 2 hours ago</span></div><span class="score-pill">82%</span></div><div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>Python Developer</strong><span>Technical · Monday</span></div><span class="score-pill">88%</span></div><div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>Data Scientist</strong><span>Mixed interview · Sep 18</span></div><span class="score-pill">79%</span></div></div></article><article class="card panel streak-panel"><p class="eyebrow" style="color:#78aaff">Your momentum</p><h3>Keep your streak alive</h3><p class="subtle">One focused session today keeps your progress moving.</p><div class="streak-number">6</div><span class="subtle">days in a row</span><div style="margin-top:25px"><div class="progress" style="background:#244268"><span style="width:60%;background:#68a7ff"></span></div><p class="subtle" style="font-size:12px;margin:8px 0 0">4 more days to beat your record</p></div></article></section></main>`); }
function getLatestResume() { return state.resume || state.resumes[0] || null; }
function canContinueToSetup() { const resume = getLatestResume(); return Boolean(resume && resume.id && !state.resumeError) || Boolean(state.resumes.length && !state.resumeError); }
function syncResumeGate() {
  const continueButton = document.querySelector('[data-view="setup"]');
  const helper = document.querySelector('#resume-gate-help');
  const enabled = canContinueToSetup();
  if (continueButton) continueButton.disabled = !enabled;
  if (helper) helper.textContent = enabled ? '' : 'Upload a resume to continue';
}
function syncJobSetupValidation() {
  const titleInput = document.querySelector('#role');
  const button = document.querySelector('#prepare-interview');
  const helper = document.querySelector('#job-title-help');
  const enabled = !!titleInput?.value?.trim();
  if (button) button.disabled = !enabled;
  if (helper) helper.textContent = enabled ? '' : 'Job title is required';
}
async function resume() {
  let items = [];
  try {
    const response = await resumeApi.list();
    items = Array.isArray(response) ? response : (response?.items ?? []);
    state.resumes = items;
  } catch (error) {
    console.warn('Could not load resumes', error);
    items = state.resumes || [];
  }
  const savedResume = items.find(item => item.id === state.resume?.id) || items[0] || null;
  if (savedResume) {
    state.resume = { ...savedResume, name: savedResume.original_filename || savedResume.name };
    if (!state.resumeSelectionMode || state.resumeSelectionMode === 'upload') state.resumeSelectionMode = 'selected';
    shell(`<main class="page">${pageHeading('Step 1 of 3', 'Build your personalized interview', 'Your saved resume is ready to use.')}<section class="card form-card"><div class="file-card"><span class="file-icon">${icon('file')}</span><div class="file-meta"><strong>Using resume: ${state.resume.name || state.resume.original_filename || 'Resume'}</strong><span>Saved for this account</span></div><button class="btn btn-secondary" type="button" data-resume-change="true">Change</button></div><div style="display:flex;justify-content:flex-end;align-items:center;flex-direction:column;gap:8px;margin-top:24px"><button class="btn btn-primary" data-view="setup" ${canContinueToSetup() ? '' : 'disabled'}>Continue ${icon('arrow')}</button><p id="resume-gate-help" class="muted" style="margin:0;min-height:20px;">${canContinueToSetup() ? '' : 'Upload a resume to continue'}</p></div></section></main>`);
    return;
  }
  state.resume = null;
  state.resumeSelectionMode = 'upload';
  shell(`<main class="page">${pageHeading('Step 1 of 3', 'Build your personalized interview', "Upload your resume and we'll tailor the interview to your experience.")}<section class="card form-card"><div class="upload-zone" id="upload-zone"><div class="upload-icon">${icon('upload')}</div><h3>Drag & drop your resume here</h3><p class="subtle" style="margin-bottom:0">or <label for="resume-input">browse files</label></p><input id="resume-input" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"><p class="upload-help">PDF or DOCX · Maximum 10MB</p></div><div id="resume-result"></div><div style="display:flex;justify-content:flex-end;align-items:center;flex-direction:column;gap:8px;margin-top:24px"><button class="btn btn-primary" data-view="setup" ${canContinueToSetup() ? '' : 'disabled'}>Continue ${icon('arrow')}</button><p id="resume-gate-help" class="muted" style="margin:0;min-height:20px;">${canContinueToSetup() ? '' : 'Upload a resume to continue'}</p></div></section></main>`);
}
function resumeResult() { const file = state.resume || (state.resumes[0] && { name: state.resumes[0].original_filename, size: `${(state.resumes[0].file_size / 1024 / 1024).toFixed(1)} MB`, id: state.resumes[0].id, parsed: state.resumes[0].parsed_profile_json || {}, extracted_text_preview: state.resumes[0].extracted_text_preview || state.resumes[0].extracted_text || '' }); if (!file) return emptyState('No resume uploaded', 'Upload a PDF or DOCX to personalize your interview.'); const parsed = file.parsed || {}; const skills = Array.isArray(parsed.skills) ? parsed.skills : []; const summary = parsed.summary || 'No summary available.'; const experienceYears = parsed.experience_years ?? (parsed.experience ? parsed.experience.length : 0); const preview = file.warning || file.extracted_text_preview || 'No extracted text preview available.'; const errorBanner = file.warning ? `<div class="error-banner" style="margin-top:12px;color:#fca5a5;background:rgba(127,29,29,0.35);border:1px solid rgba(252,165,165,0.4);padding:10px 12px;border-radius:10px;">${file.warning}</div>` : ''; return `<div class="file-card"><span class="file-icon">${icon('file')}</span><div class="file-meta"><strong>${file.name || file.original_filename || 'Resume'}</strong><span>${file.size || 'Uploaded'} · <span style="color:var(--green)">Resume analyzed</span></span></div><button class="icon-btn" id="remove-resume" aria-label="Remove resume">×</button></div>${errorBanner}<div class="extracted"><div class="panel-heading"><div><h3>Resume analysis</h3><span class="muted">We’ll use this context to personalize your questions.</span></div></div><details open><summary style="cursor:pointer;font-weight:600;margin-bottom:10px;">Extracted preview</summary><p class="subtle" style="white-space:pre-wrap;margin-top:12px;max-height:180px;overflow:auto;">${preview}</p></details><div style="margin-top:14px"><strong class="muted" style="font-size:12px;display:block;margin-bottom:8px">Parsed profile</strong><ul class="tag-list" style="margin:0 0 10px;">${skills.length ? skills.slice(0, 8).map(skill => `<li class="tag">${skill}</li>`).join('') : '<li class="tag">No skills detected</li>'}</ul><p class="subtle" style="margin:0 0 8px;"><strong>Experience:</strong> ${experienceYears} years</p><p class="subtle" style="margin:0;"><strong>Summary:</strong> ${summary}</p></div></div>`; }
function setup() { shell(`<main class="page">${pageHeading('Step 2 of 2', 'What role are you preparing for?', 'Tell us what you are aiming for so every question feels relevant.')}<section class="card form-card"><div class="field"><label for="role">Target job title</label><input id="role" value="${state.role || ''}" placeholder="e.g. Machine Learning Engineer"></div><p id="job-title-help" class="muted" style="min-height:18px;margin:0 0 8px;">${state.role?.trim() ? '' : 'Job title is required'}</p><div class="field"><label for="description">Paste the job description <span class="muted">(optional)</span></label><textarea id="description" placeholder="Paste the job description here (optional)">${state.jobDescription || ''}</textarea></div><div class="field"><label>Interview type</label><div class="option-grid">${['Technical Interview','HR Interview','Behavioral Interview','Mixed Interview'].map(x => `<button class="option ${state.type === x ? 'selected' : ''}" data-option="type" data-value="${x}"><strong>${x}</strong><span>${x === 'Mixed Interview' ? 'A balanced session' : 'Focused practice'}</span></button>`).join('')}</div></div><div class="form-row"><div class="field"><label>Difficulty</label><div class="option-grid three">${['Beginner','Intermediate','Advanced'].map(x => `<button class="option ${state.difficulty === x ? 'selected' : ''}" data-option="difficulty" data-value="${x}"><strong>${x}</strong></button>`).join('')}</div></div><div class="field"><label>Duration</label><div class="option-grid three">${['15 min','30 min','45 min','60 min'].map(x => `<button class="option ${state.duration === x ? 'selected' : ''}" data-option="duration" data-value="${x}"><strong>${x}</strong></button>`).join('')}</div></div></div><div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px"><button class="btn btn-secondary" data-view="resume">Back</button><button class="btn btn-primary" id="prepare-interview" ${state.role?.trim() ? '' : 'disabled'}>Start interview ${icon('arrow')}</button></div></section></main>`); }
function auth() { const registering = state.authMode === 'register'; shell(`<main class="page"><section class="card form-card auth-card"><p class="eyebrow">${registering ? 'Get started' : 'Welcome back'}</p><h1>${registering ? 'Create your InterviewAI account' : 'Sign in to InterviewAI'}</h1><p class="subtle">${registering ? 'Start personalized interview practice with your own account.' : 'Continue your personalized interview practice.'}</p>${registering ? '<div class="field"><label for="auth-name">Full name</label><input id="auth-name" type="text" autocomplete="name" placeholder="Your full name"></div>' : ''}<div class="field"><label for="auth-email">Email</label><input id="auth-email" type="email" autocomplete="email" placeholder="you@example.com"></div><div class="field"><label for="auth-password">Password</label><input id="auth-password" type="password" autocomplete="new-password" placeholder="Your password"></div><button class="btn btn-primary" id="auth-submit" style="width:100%">${registering ? 'Sign up' : 'Sign in'}</button><button class="btn btn-quiet" id="auth-switch" type="button" style="width:100%;margin-top:10px">${registering ? 'Sign in' : 'Sign up'}</button><p id="auth-error" class="subtle" role="alert" style="margin:14px 0 0"></p></section></main>`, true); }
// Email verification UI disabled — re-enable later. Backend support retained.
function verification() { shell(`<main class="page"><section class="card form-card auth-card"><p class="eyebrow">Almost there</p><h1>Verify your email</h1><p class="subtle">Enter the verification token from your email to activate your account.</p><div class="field"><label for="verification-token">Verification token</label><input id="verification-token" type="text" value="${state.verificationToken}" placeholder="Paste your token"></div><button class="btn btn-primary" id="verify-submit" style="width:100%">Verify email</button><p id="verification-error" class="subtle" role="alert" style="margin:14px 0 0"></p></section></main>`, true); }
function results() { shell(`<main class="page"><div class="page-heading"><div><p class="eyebrow">Session complete</p><h1>Interview complete</h1><p class="subtle">Review your final performance feedback.</p></div><button class="btn btn-primary" data-view="resume">Practice again ${icon('arrow')}</button></div><section class="results-hero"><div><p class="eyebrow" style="color:#78aaff">${state.role} · ${state.duration}</p><h2 style="color:#fff;margin-bottom:4px">Interview complete</h2><p style="color:#b4c8e3;margin:0">Loading your final feedback...</p></div><div class="results-score"><div class="score-ring"><strong>--</strong></div><div><span style="color:#b4c8e3;font-size:12px">Overall score</span><strong style="display:block">-- / 100</strong></div></div></section><section class="result-grid"><div><article class="card feedback-section positive"><h3>What you did well</h3><ul class="feedback-list"></ul></article><article class="card feedback-section improve"><h3>What to improve</h3><ul class="feedback-list"></ul></article></div><div><article class="card feedback-section recommend"><h3>${icon('spark')} Recommended practice</h3><div class="tag-list"></div></article></div></section></main>`); }
async function resultsFromApi() {
  results();
  if (!getAuthToken() || !state.interviewId) return;
  const hero = document.querySelector('.results-hero');
  if (!hero) return;
  hero.insertAdjacentHTML('afterbegin', '<p id="results-status" class="muted" style="margin:0">Loading your final feedback...</p>');
  try {
    const interview = await interviewApi.get(state.interviewId);
    const feedback = interview.final_feedback_json;
    const status = document.querySelector('#results-status');
    if (!feedback) {
      if (status) status.textContent = 'Final feedback is not available yet.';
      return;
    }
    if (status) status.remove();
    const score = Math.round(feedback.overall_score);
    const scoreRing = document.querySelector('.score-ring strong');
    const scoreLabel = document.querySelector('.results-score > div:last-child strong');
    const resultTitle = document.querySelector('.results-hero h2');
    const resultSummary = document.querySelector('.results-hero p[style*="b4c8e3"]');
    if (scoreRing) scoreRing.textContent = score;
    if (scoreLabel) scoreLabel.textContent = `${score} / 100`;
    if (resultTitle) resultTitle.textContent = 'Interview complete';
    if (resultSummary) resultSummary.textContent = feedback.summary;
    const strengths = document.querySelector('.feedback-section.positive .feedback-list');
    const weaknesses = document.querySelector('.feedback-section.improve .feedback-list');
    const recommendations = document.querySelector('.feedback-section.recommend .tag-list');
    if (strengths) strengths.innerHTML = (feedback.strengths || []).map(item => `<li>${item}</li>`).join('') || '<li>No strengths recorded.</li>';
    if (weaknesses) weaknesses.innerHTML = (feedback.weaknesses || []).map(item => `<li>${item}</li>`).join('') || '<li>No improvement items recorded.</li>';
    if (recommendations) recommendations.innerHTML = (feedback.recommended_practice || []).map(item => `<span class="tag">${item}</span>`).join('') || '<span class="muted">No recommendations recorded.</span>';
  } catch (error) {
    const status = document.querySelector('#results-status');
    if (status) status.textContent = `Could not load final feedback: ${error.message}`;
  }
}
function updateRealtimeStatus(statusText) {
  const status = document.querySelector('#voice-status');
  const presence = document.querySelector('#ai-presence');
  const aiStatus = document.querySelector('#ai-status');
  const stageStatus = document.querySelector('#stage-status');
  if (status) status.textContent = statusText;
  if (aiStatus) aiStatus.textContent = statusText;
  if (stageStatus) stageStatus.textContent = statusText;
  if (presence) presence.dataset.state = state.interviewState;
  updateRealtimeMediaUi();
}

function setRealtimeState(nextState, statusText) {
  state.interviewState = nextState;
  updateRealtimeStatus(statusText || nextState.replaceAll('_', ' '));
}

function updateRealtimeTranscript() {
  const transcript = document.querySelector('#live-transcript-text');
  if (transcript) transcript.textContent = `${state.transcript} ${state.interimTranscript}`.trim() || (state.interviewState === 'PROCESSING_ANSWER' ? 'Processing your answer...' : 'Listening...');
}

function clearSilenceTimer() { if (state.silenceTimer) { clearTimeout(state.silenceTimer); state.silenceTimer = null; } }

function normalizeSpeechText(value) { return value.toLowerCase().replace(/[^a-z0-9\s]/g, ' ').replace(/\s+/g, ' ').trim(); }
function speechSimilarity(left, right) {
  const leftWords = new Set(normalizeSpeechText(left).split(' ').filter(Boolean));
  const rightWords = new Set(normalizeSpeechText(right).split(' ').filter(Boolean));
  if (!leftWords.size || !rightWords.size) return 0;
  const overlap = [...leftWords].filter(word => rightWords.has(word)).length;
  return (2 * overlap) / (leftWords.size + rightWords.size);
}
function isQuestionEcho(transcript) { return speechSimilarity(transcript, state.remoteQuestion || '') > 0.7; }

function showSilencePrompt() {
  state.silencePrompt = true;
  updateRealtimeTranscript();
  render();
}

function scheduleAnswerSubmission() {
  clearSilenceTimer();
  state.silenceTimer = setTimeout(() => {
    if (!['LISTENING', 'USER_SPEAKING'].includes(state.interviewState)) return;
    if (state.transcript.trim()) submitVoiceAnswer();
    else showSilencePrompt();
  }, VOICE_SILENCE_TIMEOUT_MS);
}

function beginListening() {
  if (state.processingAnswer || state.interviewState === 'INTERVIEW_COMPLETE') return;
  if (!state.speechRecognition?.available) {
    state.sttFallback = true;
    setRealtimeState('LISTENING', 'Type your answer below.');
    showToast('Speech input unavailable', 'Text input fallback is active.');
    updateRealtimeTranscript();
    return;
  }
  state.sttFallback = false;
  state.transcript = '';
  state.interimTranscript = '';
  state.silencePrompt = false;
  state.answerStartedAt = Date.now();
  updateRealtimeTranscript();
  setRealtimeState('LISTENING', 'Listening...');
  scheduleAnswerSubmission();
  const started = state.speechRecognition.start({
    onStart: () => { state.microphoneStatus = 'LISTENING'; updateRealtimeStatus('Listening...'); },
    onInterim: transcript => { state.interimTranscript = transcript; state.microphoneStatus = 'USER_SPEAKING'; setRealtimeState('USER_SPEAKING', 'Listening...'); updateRealtimeTranscript(); clearSilenceTimer(); },
    onFinal: transcript => {
      if (isQuestionEcho(transcript)) {
        console.log('[echo-filter] discarded STT result matching question');
        return;
      }
      state.transcript = `${state.transcript} ${transcript}`.trim();
      state.interimTranscript = '';
      state.microphoneStatus = 'USER_SPEAKING';
      setRealtimeState('USER_SPEAKING', 'Listening...');
      updateRealtimeTranscript();
      scheduleAnswerSubmission();
    },
    onEnd: () => { if (['LISTENING', 'USER_SPEAKING'].includes(state.interviewState) && state.transcript.trim()) scheduleAnswerSubmission(); },
    onError: error => { state.microphoneStatus = 'MIC_ERROR'; if (['LISTENING', 'USER_SPEAKING'].includes(state.interviewState)) { setRealtimeState('ERROR', error.message); showToast(error.message.includes('required') ? 'Microphone unavailable' : 'Microphone listening issue', error.message.includes('required') ? '' : 'Check browser permissions and retry.'); } updateRealtimeMediaUi(); }
  });
  if (!started && state.speechRecognition.available) showToast('Microphone unavailable', 'Check browser permissions and retry.');
}

function speakCurrentQuestion() {
  if (!state.remoteQuestion) return;
  if (!state.speaker || !state.textToSpeech?.available) {
    if (!state.speaker) showToast('Speaker muted', 'Question audio is off.');
    setRealtimeState('LISTENING', 'Type or speak your answer.');
    state.sttFallback = !state.speechRecognition?.available;
    if (!state.speechRecognition?.available) showToast('Speech input unavailable', 'Text fallback is enabled.');
    if (!state.speaker && state.speechRecognition?.available) beginListening();
    return;
  }
  setRealtimeState('AI_THINKING', 'Thinking...');
  state.textToSpeech.speak(state.remoteQuestion, {
    onStart: () => setRealtimeState('AI_SPEAKING', 'AI is speaking...'),
    onEnd: () => beginListening(),
    onError: error => { setRealtimeState('LISTENING', 'Listening...'); showToast('AI voice unavailable', error.message); beginListening(); }
  });
}

async function ensureInterviewStarted() {
  if (state.currentQuestionId) return;
  if (!state.startPromise) {
    state.startPromise = (async () => {
      await interviewApi.start(state.interviewId);
      const question = await interviewApi.currentQuestion(state.interviewId);
      state.currentQuestionId = question.id;
      state.remoteQuestion = question.question_text;
      state.question = question.question_number;
    })().finally(() => { state.startPromise = null; });
  }
  await state.startPromise;
}

async function submitVoiceAnswer() {
  const manualInput = document.querySelector('#manual-answer-input');
  const answerText = (state.transcript || manualInput?.value || '').trim();
  if (state.processingAnswer || state.isSubmitting || !state.currentQuestionId || !answerText) return;
  if (answerText.length < MIN_ANSWER_LENGTH || isQuestionEcho(answerText)) {
    if (isQuestionEcho(answerText)) console.log('[echo-filter] discarded STT result matching question');
    showToast('Answer too short', `Please answer with at least ${MIN_ANSWER_LENGTH} characters.`);
    beginListening();
    return;
  }
  state.processingAnswer = true;
  state.isSubmitting = true;
  clearSilenceTimer();
  state.speechRecognition?.stop();
  state.microphoneStatus = 'PROCESSING';
  state.transcript = answerText;
  if (manualInput) manualInput.value = '';
  setRealtimeState('PROCESSING_ANSWER', 'Analyzing your answer...');
  try {
    state.feedback = await interviewApi.answer(state.interviewId, { question_id: state.currentQuestionId, answer_text: answerText, response_duration_seconds: Math.round((Date.now() - state.answerStartedAt) / 1000) });
    if (state.feedback.is_complete) {
      state.processingAnswer = false;
      state.isSubmitting = false;
      state.interviewState = 'INTERVIEW_COMPLETE';
      const showResults = () => { cleanupRealtimeInterview(); state.view = 'results'; render(); };
      if (state.feedback.closing_text && state.speaker && state.textToSpeech?.available) {
        state.textToSpeech.speak(state.feedback.closing_text, { onEnd: showResults, onError: showResults });
      } else showResults();
      return;
    }
    const next = state.feedback.next_question || await interviewApi.currentQuestion(state.interviewId);
    state.currentQuestionId = next.id;
    state.remoteQuestion = next.question_text;
    state.question = next.question_number;
    state.processingAnswer = false;
    state.isSubmitting = false;
    render();
    speakCurrentQuestion();
  } catch (error) {
    state.processingAnswer = false;
    state.isSubmitting = false;
    if (error.status === 422) {
      state.transcript = '';
      state.interimTranscript = '';
      beginListening();
      return;
    }
    setRealtimeState('LISTENING', 'AI interviewer is temporarily unavailable. Please try again.');
    showToast('AI interviewer unavailable', error.status === 409 ? error.message : 'Your answer was not submitted. Please try again.');
  }
}

async function initializeRealtimeInterview() {
  if (state.voiceInitialized) return;
  state.voiceInitialized = true;
  state.speechRecognition = new BrowserSpeechToTextProvider();
  state.textToSpeech = new BrowserTextToSpeechProvider();
  if (!state.interviewId || !getAuthToken()) { setRealtimeState('IDLE', 'Sign in to start the real interview.'); return; }
  try {
    await ensureInterviewStarted();
    if (state.view === 'interview' && !document.querySelector('#user-video')) render();
  } catch (error) {
    state.voiceInitialized = false;
    setRealtimeState('IDLE', 'AI interviewer is temporarily unavailable.');
    showToast('Interview could not start', error.message);
    return;
  }
  const cameraRequest = requestInterviewCamera();
  const microphoneRequest = requestInterviewMicrophone();
  try {
    state.cameraStatus = 'CAMERA_STARTING';
    updateRealtimeMediaUi();
    state.mediaStream = await cameraRequest;
    const video = document.querySelector('#user-video');
    if (!video) throw new Error('Camera preview is unavailable.');
    video.srcObject = state.mediaStream;
    video.muted = true;
    await video.play();
    const track = state.mediaStream.getVideoTracks()[0];
    state.cameraStatus = track?.readyState === 'live' && track.enabled && video?.readyState >= 2 && video.videoWidth > 0 ? 'CAMERA_ON' : 'CAMERA_ERROR';
  } catch (error) { state.cameraStatus = error.name === 'NotAllowedError' ? 'CAMERA_PERMISSION_DENIED' : 'CAMERA_UNAVAILABLE'; showToast('Camera unavailable'); }
  try {
    state.microphoneStream = await microphoneRequest;
    state.microphoneStatus = 'MIC_ON';
  } catch (error) { state.microphoneStatus = 'MIC_ERROR'; showToast('Microphone unavailable'); }
  updateRealtimeMediaUi();
  speakCurrentQuestion();
}

function cleanupRealtimeInterview() {
  clearSilenceTimer();
  state.speechRecognition?.stop();
  state.textToSpeech?.stop();
  stopInterviewMedia(state.mediaStream);
  stopInterviewMedia(state.microphoneStream);
  state.mediaStream = null;
  state.microphoneStream = null;
  state.cameraStatus = 'CAMERA_OFF';
  state.microphoneStatus = 'MIC_OFF';
  state.voiceInitialized = false;
  state.processingAnswer = false;
  state.timerStarted = false;
  clearInterval(timerId);
}

async function toggleCamera() {
  if (state.cameraStatus === 'CAMERA_ON') {
    stopInterviewMedia(state.mediaStream);
    state.mediaStream = null;
    state.cameraStatus = 'CAMERA_OFF';
    updateRealtimeMediaUi();
    return;
  }
  state.cameraStatus = 'CAMERA_STARTING';
  updateRealtimeMediaUi();
  try {
    state.mediaStream = await requestInterviewCamera();
    const video = document.querySelector('#user-video');
    if (!video) throw new Error('Camera preview is unavailable.');
    video.srcObject = state.mediaStream;
    video.muted = true;
    await video.play();
    const track = state.mediaStream.getVideoTracks()[0];
    state.cameraStatus = track?.readyState === 'live' && track.enabled && video.readyState >= 2 && video.videoWidth > 0 ? 'CAMERA_ON' : 'CAMERA_ERROR';
  } catch (error) {
    stopInterviewMedia(state.mediaStream);
    state.mediaStream = null;
    state.cameraStatus = error.name === 'NotAllowedError' ? 'CAMERA_PERMISSION_DENIED' : 'CAMERA_ERROR';
    showToast('Camera unavailable');
  }
  updateRealtimeMediaUi();
}

function updateRealtimeMediaUi() {
  const camera = document.querySelector('#camera-status');
  if (camera) camera.textContent = state.cameraStatus === 'CAMERA_ON' ? 'Camera on' : state.cameraStatus === 'CAMERA_PERMISSION_DENIED' ? 'Camera permission required' : 'Camera off';
  const video = document.querySelector('#user-video');
  if (video) video.hidden = state.cameraStatus !== 'CAMERA_ON';
  const cameraControl = document.querySelector('#camera-control-label');
  if (cameraControl) cameraControl.textContent = camera?.textContent || 'Camera';
  const mic = document.querySelector('#microphone-status');
  if (mic) mic.textContent = ['MIC_ON', 'LISTENING', 'USER_SPEAKING'].includes(state.microphoneStatus) ? 'Microphone on' : 'Microphone off';
  const speaker = document.querySelector('#speaker-toggle');
  if (speaker) speaker.classList.toggle('is-off', !state.speaker);
}

function realtimeStateLabel() {
  return { IDLE: 'Preparing interview', AI_THINKING: 'AI is thinking', AI_SPEAKING: 'AI is speaking', LISTENING: 'Listening to you', USER_SPEAKING: 'Listening to you', PROCESSING_ANSWER: 'Processing your answer', INTERVIEW_COMPLETE: 'Interview complete', ERROR: 'Interview needs attention' }[state.interviewState] || 'Preparing interview';
}

function realtimeLiveInterview() {
  window.onbeforeunload = () => 'Your interview is in progress. If you leave now, your progress will be lost.';
  const status = realtimeStateLabel();
  const transcript = `${state.transcript} ${state.interimTranscript}`.trim();
  const candidateSpeaking = ['LISTENING', 'USER_SPEAKING'].includes(state.interviewState);
  const showManualAnswer = state.sttFallback || !state.speechRecognition?.available || state.microphoneStatus === 'MIC_ERROR';
  if (!state.timerStarted) { state.timer = Number.parseInt(state.duration, 10) * 60; state.timerStarted = true; }
  shell(`<main class="live-interview" aria-label="Live AI interview">
    <header class="live-topbar"><div><span class="live-kicker">InterviewAI</span><strong>Live interview</strong></div><div class="live-session">${creditsMarkup()} <span class="live-divider"></span>Question ${state.question} of 10 <span class="live-divider"></span><span id="timer">${formatTime(state.timer)}</span></div></header>
    <div class="live-status" aria-live="polite"><strong id="stage-status">${status}</strong></div>
    <section class="live-stage"><div class="candidate-tile participant user-participant"><video id="user-video" autoplay playsinline muted></video><span class="participant-label">You</span><span class="participant-state" id="camera-status">Camera off</span></div><div class="ai-tile participant ai-participant" id="ai-presence"><div class="video-avatar">AI</div><strong>AI Interviewer</strong><span class="participant-state" id="voice-status">${status}</span></div><div class="stage-timer"><span>Time remaining</span><strong>${formatTime(state.timer)}</strong></div></section>
    <section class="live-workspace"><article class="interviewer-card"><div class="card-eyebrow"><span>AI INTERVIEWER</span><span class="question-count">Question ${state.question} of 10</span></div><h1>${state.remoteQuestion || 'Waiting for interviewer...'}</h1><span class="question-topic">${state.type.replace(' Interview', '')}</span></article><article class="transcript-card"><div class="transcript-heading"><strong>${candidateSpeaking ? 'Listening...' : 'Your response'}</strong></div><p id="live-transcript-text">${state.silencePrompt ? 'Did you say something?' : (transcript || 'Listening...')}</p>${state.silencePrompt ? '<button class="btn btn-secondary" id="repeat-question" type="button">Repeat question</button>' : ''}${showManualAnswer ? '<div class="manual-answer"><textarea id="manual-answer-input" rows="3" placeholder="Type your answer here..." aria-label="Type your answer"></textarea><button class="btn btn-primary" id="manual-answer-submit" type="button">Submit answer</button></div>' : ''}</article></section>
    <div class="live-controls"><div class="control-group"><button class="live-control" id="camera-toggle" aria-label="Toggle camera">${icon('video')}<span id="camera-control-label">Camera</span></button><button class="live-control" id="retry-mic" aria-label="Toggle microphone">${icon('mic')}<span id="microphone-status">Microphone</span></button><button class="live-control" id="speaker-toggle" aria-label="Toggle speaker">${icon('speaker')}<span>Speaker</span></button></div><button class="btn btn-danger end" id="end-interview">End interview</button></div>
  </main>`);
  updateRealtimeMediaUi();
  startTimer();
  initializeRealtimeInterview();
  document.querySelector('#manual-answer-submit')?.addEventListener('click', () => { const value = document.querySelector('#manual-answer-input')?.value?.trim(); if (value) { state.transcript = value; submitVoiceAnswer(); } });
}

function emptyState(title, detail, action = '') { return `<section class="card empty-state"><div class="empty-icon">${icon('spark')}</div><h3>${title}</h3><p class="subtle">${detail}</p>${action}</section>`; }
function accountDashboard() {
  const completed = state.interviews.filter(item => item.status === 'COMPLETED');
  const scores = completed.map(item => item.overall_score).filter(score => score !== null && score !== undefined);
  const average = scores.length ? `${Math.round(scores.reduce((total, score) => total + score, 0) / scores.length)}%` : '-';
  shell(`<main class="page">${pageHeading('Your workspace', `Good to see you, ${state.user?.full_name || 'there'}`, 'Your practice data belongs to this account.', '<button class="btn btn-primary" data-view="resume">Start new interview ' + icon('arrow') + '</button>')}<section class="stat-grid"><article class="card stat-card"><div class="stat-top"><span>Interviews completed</span><span class="stat-icon">↗</span></div><strong class="stat-value">${completed.length}</strong><span class="muted">Saved to your account</span></article><article class="card stat-card"><div class="stat-top"><span>Resumes</span><span class="stat-icon">${icon('file')}</span></div><strong class="stat-value">${state.resumes.length}</strong><span class="muted">Uploaded resumes</span></article><article class="card stat-card"><div class="stat-top"><span>Average score</span><span class="stat-icon">✦</span></div><strong class="stat-value">${average}</strong><span class="muted">Completed interviews only</span></article><article class="card stat-card"><div class="stat-top"><span>Jobs prepared</span><span class="stat-icon">◷</span></div><strong class="stat-value">${state.jobs.length}</strong><span class="muted">Personalized job contexts</span></article></section>${state.interviews.length ? `<section class="card panel"><div class="panel-heading"><h3>Recent practice</h3><button class="btn btn-quiet" data-view="history">View all ${icon('arrow')}</button></div><div class="activity-list">${state.interviews.slice(0, 5).map(item => `<div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>${item.interview_type}</strong><span>${new Date(item.created_at).toLocaleString()} · ${item.status}</span></div><span class="score-pill">${item.overall_score == null ? '-' : `${Math.round(item.overall_score)}%`}</span></div>`).join('')}</div></section>` : emptyState('Your dashboard is ready', 'Complete your first interview to see progress here.', '<button class="btn btn-secondary" data-view="resume">Set up an interview</button>')}</main>`);
}
function accountHistory() {
  shell(`<main class="page">${pageHeading('Your progress', 'Interview history', 'Only interviews from your authenticated account appear here.', '<button class="btn btn-primary" data-view="resume">Start new interview ' + icon('arrow') + '</button>')}${state.interviews.length ? `<section class="card table-wrap"><table class="history-table"><thead><tr><th>Date</th><th>Interview type</th><th>Score</th><th>Duration</th></tr></thead><tbody>${state.interviews.map(item => {
    const score = item.score ?? item.overall_score;
    const duration = item.duration_seconds ?? item.actual_duration_seconds;
    return `<tr><td class="muted">${item.created_at ? new Date(item.created_at).toLocaleString() : '—'}</td><td class="role">${item.interview_type || 'Interview'}</td><td class="table-score">${score == null ? '-' : `${Math.round(Number(score))}%`}</td><td class="muted">${duration == null ? '-' : `${Math.round(Number(duration) / 60)} min`}</td></tr>`;
  }).join('')}</tbody></table></section>` : emptyState('No interviews yet', 'Your completed and in-progress interviews will appear here.')}</main>`);
}
function accountProfile() {
  const user = state.user || {};
  const currentResume = state.resumes[0] || null;
  const creditsText = Number.isFinite(state.creditBalance) ? `${state.creditBalance} interviews` : '0 interviews';
  const buyButton = state.creditBalance === 0 ? '<button class="btn btn-secondary" type="button" data-buy>Buy</button>' : '';
  shell(`<main class="page">${pageHeading('Account', 'Profile & settings', 'This profile is loaded from the current authenticated session.')}<section class="profile-grid"><article class="card profile-card"><div class="profile-head"><div class="profile-avatar">${userInitials()}</div><div><h3 style="margin-bottom:2px">${user.full_name || 'Account'}</h3><span class="muted">${user.email || ''}</span></div></div><div class="profile-details"><div class="profile-detail"><span>Account status</span><strong>${user.is_active ? 'Active' : 'Inactive'}</strong></div><div class="profile-detail"><span>Resume</span><strong>${currentResume ? currentResume.original_filename : 'No resume uploaded'}</strong>${currentResume ? '<button class="btn btn-secondary" type="button" data-resume-remove="' + currentResume.id + '">Remove</button>' : ''}</div><div class="profile-detail"><span>Credits</span><strong>${creditsText}</strong>${buyButton}</div><div class="profile-detail"><span>Interviews</span><strong>${state.interviews.length}</strong></div></div></article></section><section class="danger-zone"><h3>Danger zone</h3><p class="subtle">This removes your uploaded resumes, saved jobs, interview history, and related usage logs from this account.</p><button class="btn btn-secondary" id="profile-remove-data" type="button">Remove data</button><button class="btn btn-danger" id="profile-logout" type="button">Log out</button></section></main>`);
}
async function loadUserData() {
  if (!getAuthToken()) return;
  try {
    const [user, credits, resumes, jobs, interviews] = await Promise.all([userApi.profile(), userApi.credits(), resumeApi.list(), jobApi.list(), interviewApi.history()]);
    const balance = Number(credits.balance_interviews ?? credits.balance_minutes ?? 0);
    Object.assign(state, { user, creditBalance: balance, resumes, jobs, interviews });
    if (state.view !== 'auth') render();
  } catch (error) {
    if (error.status === 401) { resetUserState(); window.history.replaceState({}, '', '#login'); render(); }
    else showToast('Could not load your account', normalizeApiError(error));
  }
}
function render() { ({ dashboard: accountDashboard, resume, setup, interview: realtimeLiveInterview, results: resultsFromApi, history: accountHistory, profile: accountProfile, auth }[state.view] || accountDashboard)(); }
function showLeaveWarning(onConfirm) {
  const existing = document.querySelector('#leave-warning-modal');
  if (existing) existing.remove();
  const backdrop = document.createElement('div');
  backdrop.id = 'leave-warning-modal';
  backdrop.className = 'modal-backdrop';
  backdrop.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="leave-warning-title"><p class="eyebrow">Leave interview</p><h2 id="leave-warning-title">Leave interview?</h2><p class="subtle">Progress is saved up to the last answered question.</p><div class="modal-actions"><button class="btn btn-secondary" id="stay-in-interview" type="button">Stay</button><button class="btn btn-danger" id="leave-interview" type="button">Leave</button></div></div>`;
  document.body.append(backdrop);
  backdrop.querySelector('#stay-in-interview').addEventListener('click', () => backdrop.remove());
  backdrop.querySelector('#leave-interview').addEventListener('click', async () => { backdrop.remove(); await onConfirm?.(); });
}

let timerId;
function startTimer() { clearInterval(timerId); timerId = setInterval(() => { if (state.view !== 'interview') return clearInterval(timerId); state.timer = Math.max(0, state.timer - 1); const timer = document.querySelector('#timer'); if (timer) timer.textContent = formatTime(state.timer); if (state.timer === 0) { clearInterval(timerId); showEndModal(); } }, 1000); }
async function removeUserData() {
  const confirmed = window.confirm('This permanently removes your resumes, job contexts, interview history, and analytics from this account. Continue?');
  if (!confirmed) return;
  try {
    await userApi.removeData();
    resetUserState();
    window.history.replaceState({}, '', '#login');
    render();
    showToast('Account data removed');
  } catch (error) {
    showToast('Could not remove your data', normalizeApiError(error));
  }
}

function bindEvents() {
  document.querySelector('#buy-credits')?.addEventListener('click', () => {
    console.log('Buy clicked');
    openBuyPanel();
  });
  document.querySelectorAll('[data-buy]').forEach(button => {
    console.log('binding data-buy', button);
    button.addEventListener('click', (event) => {
      event.preventDefault();
      console.log('Buy clicked');
      openBuyPanel();
    });
  });
  document.querySelector('#profile-logout')?.addEventListener('click', logout);
  document.querySelector('#profile-remove-data')?.addEventListener('click', removeUserData);
  document.querySelector('[data-resume-change="true"]')?.addEventListener('click', () => { state.resumeSelectionMode = 'upload'; render(); });
  document.querySelectorAll('[data-resume-remove]').forEach(button => button.addEventListener('click', async () => {
    const id = button.dataset.resumeRemove;
    if (!id) return;
    try {
      await resumeApi.remove(id);
    } catch (error) {
      if (error.status !== 404) throw error;
    }
    state.resumes = state.resumes.filter(item => item.id !== id);
    if (state.resume?.id === id) state.resume = null;
    render();
  }));
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', async () => {
    const nextView = button.dataset.view;
    if (state.view === 'interview' && ['dashboard', 'history', 'profile'].includes(nextView)) {
      showLeaveWarning(async () => {
        try {
          if (state.interviewId) await interviewApi.end(state.interviewId);
        } catch (error) {
          console.warn('Could not save interview before leaving', error);
        }
        window.onbeforeunload = null;
        state.view = nextView;
        render();
      });
      return;
    }
    state.view = nextView;
    if (state.view !== 'interview') window.onbeforeunload = null;
    render();
  }));
  document.querySelectorAll('[data-option]').forEach(button => button.addEventListener('click', () => { state[button.dataset.option] = button.dataset.value; render(); }));
  document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('.filter').forEach(item => item.classList.remove('active')); button.classList.add('active'); showToast('Filter updated', `Showing ${button.textContent.toLowerCase()} sessions.`); }));
  document.querySelectorAll('.review-toggle').forEach(button => button.addEventListener('click', () => button.closest('.review-item').classList.toggle('open')));
  document.querySelectorAll('.switch').forEach(button => button.addEventListener('click', () => button.classList.toggle('on')));
  const input = document.querySelector('#resume-input'); const zone = document.querySelector('#upload-zone');
  if (input && zone) { input.addEventListener('change', event => handleFile(event.target.files[0])); ['dragenter','dragover'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.add('dragover'); })); ['dragleave','drop'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.remove('dragover'); })); zone.addEventListener('drop', event => handleFile(event.dataTransfer.files[0])); if (state.resume) document.querySelector('#resume-result').innerHTML = resumeResult(); }
    if (input && zone) { input.addEventListener('change', event => handleFile(event.target.files[0])); ['dragenter','dragover'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.add('dragover'); })); ['dragleave','drop'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.remove('dragover'); })); zone.addEventListener('drop', event => handleFile(event.dataTransfer.files[0])); if (state.resume || state.resumes.length) document.querySelector('#resume-result').innerHTML = resumeResult(); }
  document.querySelector('#remove-resume')?.addEventListener('click', () => { state.resume = null; state.resumeError = null; render(); });
  document.querySelector('#auth-switch')?.addEventListener('click', () => { state.authMode = state.authMode === 'login' ? 'register' : 'login'; render(); });
  document.querySelector('#auth-submit')?.addEventListener('click', async () => { const error = document.querySelector('#auth-error'); try { const payload = { email: document.querySelector('#auth-email').value, password: document.querySelector('#auth-password').value }; if (state.authMode === 'register') { await authApi.register({ ...payload, full_name: document.querySelector('#auth-name').value }); state.view = 'dashboard'; window.history.replaceState({}, '', window.location.pathname); render(); await loadUserData(); return; } await authApi.login(payload); state.view = 'dashboard'; window.history.replaceState({}, '', window.location.pathname); render(); await loadUserData(); } catch (authError) { if (error) error.textContent = normalizeApiError(authError); } });
  function render() { ({ dashboard: accountDashboard, resume, setup, interview: realtimeLiveInterview, results: resultsFromApi, history: accountHistory, profile: accountProfile, auth }[state.view] || accountDashboard)(); }
  document.querySelector('#role')?.addEventListener('input', event => { state.role = event.target.value; state.jobDescription = document.querySelector('#description')?.value || ''; syncJobSetupValidation(); });
  document.querySelector('#description')?.addEventListener('input', event => { state.jobDescription = event.target.value; });
  const setupButton = document.querySelector('#prepare-interview');
  if (setupButton) { setupButton.disabled = !String(state.role || '').trim(); }
  document.querySelector('#prepare-interview')?.addEventListener('click', async () => { state.role = (document.querySelector('#role')?.value || '').trim(); state.jobDescription = document.querySelector('#description')?.value || ''; if (!state.role) { syncJobSetupValidation(); showToast('Job title is required'); return; } showToast('Preparing your interview', 'Generating personalized questions...'); if (getAuthToken()) { try { const job = await api('/api/jobs', { method: 'POST', body: JSON.stringify({ title: state.role, job_description: state.jobDescription }) }); const interview = await interviewApi.create({ job_id: job.id, resume_id: state.resume?.id || null, interview_type: state.type, difficulty: state.difficulty, duration_target_minutes: Number.parseInt(state.duration, 10) }); state.interviewId = interview.id; await interviewApi.start(state.interviewId); const question = await interviewApi.currentQuestion(state.interviewId); state.currentQuestionId = question.id; state.remoteQuestion = question.question_text; state.question = question.question_number; state.view = 'interview'; render(); return; } catch (error) { showToast('Interview setup failed', error.message); return; } } state.view = 'interview'; render(); });
  document.querySelector('[data-view="interview"]')?.addEventListener('click', async () => { if (getAuthToken() && state.interviewId) { try { await ensureInterviewStarted(); render(); } catch (error) { showToast('Interview could not start', error.message); } } });
  document.querySelector('#camera-toggle')?.addEventListener('click', toggleCamera);
  document.querySelector('#speaker-toggle')?.addEventListener('click', event => { state.speaker = !state.speaker; if (!state.speaker) { state.textToSpeech?.stop(); if (state.interviewState === 'AI_SPEAKING') beginListening(); } updateRealtimeMediaUi(); showToast(state.speaker ? 'Speaker on' : 'Speaker off'); });
  document.querySelector('#retry-mic')?.addEventListener('click', () => { if (state.interviewState === 'LISTENING') beginListening(); else initializeRealtimeInterview(); });
  document.querySelector('#end-interview')?.addEventListener('click', showEndModal);
  document.querySelector('#repeat-question')?.addEventListener('click', () => { state.silencePrompt = false; render(); speakCurrentQuestion(); });
  document.querySelector('#manual-answer-submit')?.addEventListener('click', () => { const value = document.querySelector('#manual-answer-input')?.value?.trim(); if (value) { state.transcript = value; submitVoiceAnswer(); } });
}
async function handleFile(file) { if (!file) return; const valid = ['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document']; if (!valid.includes(file.type) && !/\.(pdf|docx)$/i.test(file.name)) { state.resume = null; state.resumeError = 'Please upload a PDF or DOCX under 10MB.'; if (document.querySelector('#resume-result')) document.querySelector('#resume-result').innerHTML = `<div class="error-banner" style="color:#fca5a5;background:rgba(127,29,29,0.35);border:1px solid rgba(252,165,165,0.4);padding:10px 12px;border-radius:10px;">Please upload a PDF or DOCX under 10MB.</div>`; syncResumeGate(); showToast('Resume upload failed', 'Please upload a PDF or DOCX under 10MB.'); return; } if (file.size > 10 * 1024 * 1024) { state.resume = null; state.resumeError = 'Please choose a file under 10MB.'; if (document.querySelector('#resume-result')) document.querySelector('#resume-result').innerHTML = `<div class="error-banner" style="color:#fca5a5;background:rgba(127,29,29,0.35);border:1px solid rgba(252,165,165,0.4);padding:10px 12px;border-radius:10px;">Please choose a file under 10MB.</div>`; syncResumeGate(); showToast('Resume upload failed', 'Please choose a file under 10MB.'); return; }
  state.resume = { name: file.name, size: `${(file.size / 1024 / 1024).toFixed(1)} MB`, parsed: {}, extracted_text_preview: '', warning: null }; state.resumeError = null; const result = document.querySelector('#resume-result'); if (result) result.innerHTML = `<div class="thinking" style="margin-top:18px">${icon('spark')} Analyzing resume... <i></i><i></i><i></i></div>`;
  if (getAuthToken()) { try { const uploaded = await resumeApi.upload(file); state.resume = { ...state.resume, id: uploaded.id, name: uploaded.original_filename || file.name, size: `${(uploaded.file_size / 1024 / 1024).toFixed(1)} MB`, extracted_text_preview: uploaded.extracted_text_preview || '', parsed: uploaded.parsed || {}, warning: uploaded.warning || null }; state.resumeError = null; } catch (error) { state.resumeError = error.message; state.resume = { name: file.name, size: `${(file.size / 1024 / 1024).toFixed(1)} MB`, warning: error.message, parsed: {}, extracted_text_preview: '', error: true }; showToast('Resume upload failed', error.message); } }
  const finalResult = document.querySelector('#resume-result'); if (finalResult) { finalResult.innerHTML = resumeResult(); bindEvents(); syncResumeGate(); if (!state.resumeError) showToast('Resume analyzed', 'Your interview context is ready.'); }
}
function showEndModal() { const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop'; backdrop.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="end-title"><p class="eyebrow">Finish session</p><h2 id="end-title">End this interview?</h2><p class="subtle">Your progress will be saved and you will receive a performance summary.</p><div class="modal-actions"><button class="btn btn-secondary" id="cancel-end">Cancel</button><button class="btn btn-danger" id="confirm-end">End interview</button></div></div>`; document.body.append(backdrop); backdrop.querySelector('#cancel-end').addEventListener('click', () => backdrop.remove()); backdrop.querySelector('#confirm-end').addEventListener('click', async () => { cleanupRealtimeInterview(); if (getAuthToken() && state.interviewId) { try { await interviewApi.end(state.interviewId); state.creditBalance = (await userApi.credits()).balance_minutes; } catch (error) { showToast('Could not save interview', error.message); return; } } backdrop.remove(); state.interviewState = 'INTERVIEW_COMPLETE'; state.view = 'results'; render(); }); }
window.onbeforeunload = null;
try {
  render();
  loadUserData();
} catch (error) {
  console.error('Render failed:', error);
  document.body.innerHTML = `<pre style="padding:20px">Render error: ${error.message}</pre>`;
}
