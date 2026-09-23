import { api, authApi, getAuthToken, interviewApi, jobApi, normalizeApiError, resumeApi, userApi } from './api.js?v=integration3';
import { BrowserSpeechToTextProvider, BrowserTextToSpeechProvider, requestInterviewCamera, requestInterviewMicrophone, stopInterviewMedia } from './voice.js';

const app = document.querySelector('#app');
const toastRegion = document.querySelector('#toast-region');
const VOICE_SILENCE_TIMEOUT_MS = 2600;

const icons = {
  logo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/></svg>',
  bell: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9ZM10 21h4"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>',
  upload: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 16V4m0 0L8 8m4-4 4 4M5 14v5h14v-5"/></svg>',
  file: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M14 3H6v18h12V7l-4-4Z"/><path d="M14 3v4h4"/></svg>',
  mic: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="8" y="3" width="8" height="12" rx="4"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6"/></svg>',
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="3" y="6" width="13" height="12" rx="2"/><path d="m16 10 5-3v10l-5-3"/></svg>',
  speaker: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 10v4h4l5 4V6l-5 4H4ZM17 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12"/></svg>',
  settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z"/><path d="m19.4 15 .1.1-1.7 2.9-.2-.1a2 2 0 0 0-2.2.1l-.1.1a2 2 0 0 0-.9 1.8v.2h-3.4v-.2a2 2 0 0 0-1-1.8l-.1-.1a2 2 0 0 0-2.2-.1l-.2.1-1.7-2.9.1-.1a2 2 0 0 0 .3-2.2v-.2a2 2 0 0 0-1.8-1h-.2V8.2h.2a2 2 0 0 0 1.8-1l.1-.2a2 2 0 0 0-.3-2.2l-.1-.1 1.7-2.9.2.1a2 2 0 0 0 2.2-.1l.1-.1a2 2 0 0 0 1-1.8v-.2h3.4v.2a2 2 0 0 0 .9 1.8l.1.1a2 2 0 0 0 2.2.1l.2-.1 1.7 2.9-.1.1a2 2 0 0 0-.3 2.2v.2a2 2 0 0 0 1.8 1h.2v3.4h-.2a2 2 0 0 0-1.8 1l-.1.2a2 2 0 0 0 .3 2.2Z"/></svg>',
  spark: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7L12 3ZM19 16l.7 2.3L22 19l-2.3.7L19 22l-.7-2.3L16 19l2.3-.7L19 16Z"/></svg>'
};
const state = { view: window.location.hash === '#login' || !getAuthToken() ? 'auth' : 'dashboard', authMode: 'login', user: null, resumes: [], jobs: [], interviews: [], resume: null, role: 'Machine Learning Engineer', type: 'Mixed Interview', difficulty: 'Intermediate', duration: '30 min', timer: 1722, question: 1, recording: false, cameraStatus: 'CAMERA_OFF', microphoneStatus: 'MIC_OFF', speaker: true, interviewState: 'IDLE', mediaStream: null, microphoneStream: null, speechRecognition: null, textToSpeech: null, transcript: '', interimTranscript: '', answerStartedAt: 0, silenceTimer: null, processingAnswer: false, voiceInitialized: false };

function showToast(title, detail = '') { const toast = document.createElement('div'); toast.className = 'toast'; toast.innerHTML = `<strong>${title}</strong><span>${detail}</span>`; toastRegion.append(toast); setTimeout(() => toast.remove(), 3400); }
function icon(name) { return icons[name] || ''; }
function formatTime(seconds) { return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; }
function userInitials() { return (state.user?.full_name || 'User').split(/\s+/).map(part => part[0]).join('').slice(0, 2).toUpperCase(); }
function header() { return `<header class="topbar"><button class="brand" data-view="dashboard" aria-label="Go to dashboard"><span class="brand-mark">${icon('logo')}</span>InterviewAI</button><nav class="nav-links" aria-label="Primary"><button class="nav-link ${state.view === 'dashboard' ? 'active' : ''}" data-view="dashboard">Dashboard</button><button class="nav-link ${['resume','setup','lobby','interview'].includes(state.view) ? 'active' : ''}" data-view="resume">Practice</button><button class="nav-link ${state.view === 'history' ? 'active' : ''}" data-view="history">History</button></nav><div class="nav-actions"><span class="credits"><i class="credit-dot"></i> Account</span><button class="icon-btn" aria-label="Notifications">${icon('bell')}</button><button class="profile-chip" data-view="profile"><span class="avatar">${userInitials()}</span><span>${state.user?.full_name || 'Account'}</span><span>⌄</span></button><button class="icon-btn mobile-menu" aria-label="Open menu">☰</button></div></header>`; }
function resetUserState() { cleanupRealtimeInterview(); Object.assign(state, { view: 'auth', user: null, resumes: [], jobs: [], interviews: [], resume: null, interviewId: null, currentQuestionId: null, remoteQuestion: null, transcript: '', interimTranscript: '', feedback: null, interviewState: 'IDLE' }); }
async function logout() { await authApi.logout(); resetUserState(); window.history.replaceState({}, '', '#login'); render(); }
function setupProfileMenu() { const trigger = document.querySelector('.profile-chip'); if (!trigger) return; trigger.removeAttribute('data-view'); trigger.setAttribute('aria-expanded', 'false'); const menu = document.createElement('div'); menu.className = 'profile-menu'; menu.innerHTML = '<button class="profile-menu-item" data-view="profile">Profile / Settings</button><button class="profile-menu-item" id="logout-button">Logout</button>'; trigger.parentElement.append(menu); trigger.addEventListener('click', event => { event.stopPropagation(); const open = menu.classList.toggle('open'); trigger.setAttribute('aria-expanded', String(open)); }); menu.querySelector('#logout-button').addEventListener('click', logout); if (!document.body.dataset.profileMenuBound) { document.addEventListener('click', event => { const openMenu = document.querySelector('.profile-menu.open'); if (openMenu && !event.target.closest('.profile-menu') && !event.target.closest('.profile-chip')) { openMenu.classList.remove('open'); document.querySelector('.profile-chip')?.setAttribute('aria-expanded', 'false'); } }); document.body.dataset.profileMenuBound = 'true'; } }
function shell(content, noHeader = false) { app.innerHTML = `<div class="app-shell">${noHeader ? '' : header()}${content}</div>`; setupProfileMenu(); bindEvents(); }
function pageHeading(eyebrow, title, subtitle, action = '') { return `<div class="page-heading"><div><p class="eyebrow">${eyebrow}</p><h1>${title}</h1><p class="subtle">${subtitle}</p></div>${action}</div>`; }
function dashboard() { shell(`<main class="page">${pageHeading('Wednesday, September 23', 'Good afternoon, Alex', 'Ready for your next interview?', '<button class="btn btn-primary" data-view="resume">Start new interview ' + icon('arrow') + '</button>')}<section class="stat-grid"><article class="card stat-card"><div class="stat-top"><span>Interviews completed</span><span class="stat-icon">↗</span></div><strong class="stat-value">12</strong><span class="muted">+3 this month</span></article><article class="card stat-card"><div class="stat-top"><span>Practice time</span><span class="stat-icon">◷</span></div><strong class="stat-value">8.5h</strong><span class="muted">+1.2h this month</span></article><article class="card stat-card"><div class="stat-top"><span>Average score</span><span class="stat-icon">✦</span></div><strong class="stat-value">82%</strong><span class="muted">Top 18% of users</span></article><article class="card stat-card"><div class="stat-top"><span>Current streak</span><span class="stat-icon">♢</span></div><strong class="stat-value">6 days</strong><span class="muted">Personal best: 14</span></article></section><section class="dashboard-grid"><article class="card panel"><div class="panel-heading"><h3>Recent practice</h3><button class="btn btn-quiet" data-view="history">View all ${icon('arrow')}</button></div><div class="activity-list"><div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>Machine Learning Engineer</strong><span>Technical + Behavioral · 2 hours ago</span></div><span class="score-pill">82%</span></div><div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>Python Developer</strong><span>Technical · Monday</span></div><span class="score-pill">88%</span></div><div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>Data Scientist</strong><span>Mixed interview · Sep 18</span></div><span class="score-pill">79%</span></div></div></article><article class="card panel streak-panel"><p class="eyebrow" style="color:#78aaff">Your momentum</p><h3>Keep your streak alive</h3><p class="subtle">One focused session today keeps your progress moving.</p><div class="streak-number">6</div><span class="subtle">days in a row</span><div style="margin-top:25px"><div class="progress" style="background:#244268"><span style="width:60%;background:#68a7ff"></span></div><p class="subtle" style="font-size:12px;margin:8px 0 0">4 more days to beat your record</p></div></article></section></main>`); }
function resume() { shell(`<main class="page">${pageHeading('Step 1 of 3', 'Build your personalized interview', "Upload your resume and we'll tailor the interview to your experience.")}<section class="card form-card"><div class="upload-zone" id="upload-zone"><div class="upload-icon">${icon('upload')}</div><h3>Drag & drop your resume here</h3><p class="subtle" style="margin-bottom:0">or <label for="resume-input">browse files</label></p><input id="resume-input" type="file" accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"><p class="upload-help">PDF or DOCX · Maximum 10MB</p></div><div id="resume-result"></div><div style="display:flex;justify-content:flex-end;margin-top:24px"><button class="btn btn-primary" data-view="setup">Continue to job setup ${icon('arrow')}</button></div></section></main>`); }
function resumeResult() { const file = state.resume || (state.resumes[0] && { name: state.resumes[0].original_filename, size: `${(state.resumes[0].file_size / 1024 / 1024).toFixed(1)} MB` }); if (!file) return emptyState('No resume uploaded', 'Upload a PDF or DOCX to personalize your interview.'); return `<div class="file-card"><span class="file-icon">${icon('file')}</span><div class="file-meta"><strong>${file.name}</strong><span>${file.size} · <span style="color:var(--green)">Resume analyzed</span></span></div><button class="icon-btn" id="remove-resume" aria-label="Remove resume">×</button></div><div class="extracted"><div class="panel-heading"><div><h3>Resume detected</h3><span class="muted">We'll use this context to personalize your questions.</span></div></div><strong class="muted" style="font-size:12px">Resume context</strong><p class="subtle">Interview questions will use the analyzed information from this account's resume.</p></div>`; }
function setup() { shell(`<main class="page">${pageHeading('Step 2 of 3', 'What role are you preparing for?', 'Tell us what you are aiming for so every question feels relevant.')}<section class="card form-card"><div class="field"><label for="role">Target job title</label><input id="role" value="${state.role}" placeholder="e.g. Machine Learning Engineer"></div><div class="field"><label for="description">Paste the job description <span class="muted">(optional)</span></label><textarea id="description" placeholder="Paste the responsibilities and requirements here...">Build and ship machine learning systems that turn complex data into useful products. Collaborate with engineering and product teams.</textarea></div><div class="field"><label>Interview type</label><div class="option-grid">${['Technical Interview','HR Interview','Behavioral Interview','Mixed Interview'].map(x => `<button class="option ${state.type === x ? 'selected' : ''}" data-option="type" data-value="${x}"><strong>${x}</strong><span>${x === 'Mixed Interview' ? 'A balanced session' : 'Focused practice'}</span></button>`).join('')}</div></div><div class="form-row"><div class="field"><label>Difficulty</label><div class="option-grid three">${['Beginner','Intermediate','Advanced'].map(x => `<button class="option ${state.difficulty === x ? 'selected' : ''}" data-option="difficulty" data-value="${x}"><strong>${x}</strong></button>`).join('')}</div></div><div class="field"><label>Duration</label><div class="option-grid three">${['15 min','30 min','45 min','60 min'].map(x => `<button class="option ${state.duration === x ? 'selected' : ''}" data-option="duration" data-value="${x}"><strong>${x}</strong></button>`).join('')}</div></div></div><div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px"><button class="btn btn-secondary" data-view="resume">Back</button><button class="btn btn-primary" id="prepare-interview">Start interview ${icon('arrow')}</button></div></section></main>`); }
function lobby() { shell(`<main class="page lobby">${pageHeading('Step 3 of 3', "You're all set.", 'Take a breath. Your session is prepared and ready when you are.')}<section class="lobby-grid"><div class="interviewer-preview"><div class="ai-face">AI</div><div class="preview-copy"><span class="status"><i class="live-dot"></i> Ready</span><strong>Alex — AI Interviewer</strong><span style="color:#afc4e3">Your personal practice partner</span></div></div><article class="card summary-card"><p class="eyebrow">Session summary</p><div class="summary-list"><div class="summary-item"><span>Role</span><strong>${state.role}</strong></div><div class="summary-item"><span>Interview</span><strong>${state.type.replace(' Interview','')} + Behavioral</strong></div><div class="summary-item"><span>Difficulty</span><strong>${state.difficulty}</strong></div><div class="summary-item"><span>Duration</span><strong>${state.duration}</strong></div><div class="summary-item"><span>Questions</span><strong>Personalized by AI</strong></div></div><p class="subtle" style="font-size:12px">Your interviewer will ask questions based on your resume and target role.</p><button class="btn btn-primary" style="width:100%;margin-top:18px" data-view="interview">Enter interview ${icon('arrow')}</button><button class="btn btn-quiet" style="width:100%;margin-top:13px" data-view="setup">Review setup</button></article></section></main>`); }
/* legacy renderer retained temporarily for history compatibility; the active renderer is below. */
function results() { shell(`<main class="page">${pageHeading('Session complete', 'Interview complete', "Here's how you performed.", '<button class="btn btn-primary" data-view="resume">Practice again ' + icon('arrow') + '</button>')}<section class="results-hero"><div><p class="eyebrow" style="color:#78aaff">Machine Learning Engineer · ${state.duration}</p><h2 style="color:#fff;margin-bottom:4px">Strong performance</h2><p style="color:#b4c8e3;margin:0">You showed strong technical range and clear communication.</p></div><div class="results-score"><div class="score-ring"><strong>82</strong></div><div><span style="color:#b4c8e3;font-size:12px">Overall score</span><strong style="display:block;font:600 20px 'Space Grotesk'">82 / 100</strong></div></div></section><section class="result-grid"><div><article class="card panel" style="margin-bottom:18px"><div class="panel-heading"><h3>Performance breakdown</h3><span class="muted">Out of 100</span></div><div class="breakdown">${[['Technical Knowledge','84%'],['Communication','79%'],['Problem Solving','86%'],['Confidence','81%'],['Resume Relevance','88%']].map(x => `<div class="card metric"><div class="metric-head"><span>${x[0]}</span><strong>${x[1]}</strong></div><div class="progress"><span style="width:${x[1]}"></span></div></div>`).join('')}</div></article><article class="card feedback-section positive"><h3>✓ What you did well</h3><ul class="feedback-list"><li>Explained your project clearly</li><li>Demonstrated strong technical knowledge</li><li>Connected answers to your experience</li></ul></article><article class="card feedback-section improve"><h3>↗ What to improve</h3><ul class="feedback-list"><li>Give more structured answers</li><li>Explain technical decisions more clearly</li><li>Avoid very short answers</li></ul></article></div><div><article class="card feedback-section recommend"><h3>${icon('spark')} Recommended practice</h3><div class="tag-list"><span class="tag">Machine learning fundamentals</span><span class="tag">System design</span><span class="tag">Behavioral questions</span></div></article><article class="card panel"><div class="panel-heading"><h3>Question review</h3><span class="muted">3 questions</span></div><div class="review-list">${[['Tell me about yourself.','84%','Clear and concise introduction.'],['Explain your EfficientNet project.','78%','Add more context around your technical choices.'],['How did you validate the model?','85%','Strong answer with useful metrics.']].map(x => `<div class="review-item"><button class="review-toggle"><strong>${x[0]}</strong><span class="review-score">${x[1]}</span><span>⌄</span></button><div class="review-body"><strong>Your answer</strong><p>${x[2]}</p></div></div>`).join('')}</div></article></div></section></main>`); }
function history() { shell(`<main class="page">${pageHeading('Your progress', 'Interview history', 'Review your sessions and see how your confidence is growing.', '<button class="btn btn-primary" data-view="resume">Start new interview ' + icon('arrow') + '</button>')}<div class="filter-row"><button class="filter active">All</button><button class="filter">Technical</button><button class="filter">HR</button><button class="filter">Behavioral</button></div><section class="card table-wrap"><table class="history-table"><thead><tr><th>Date</th><th>Role</th><th>Interview type</th><th>Score</th><th>Duration</th><th>Status</th></tr></thead><tbody>${[['Today, 2:40 PM','Machine Learning Engineer','Technical + Behavioral','82%','30 min'],['Sep 21, 2026','Cybersecurity Analyst','Technical','76%','45 min'],['Sep 18, 2026','Python Developer','Technical','88%','30 min'],['Sep 14, 2026','Data Scientist','Behavioral','79%','15 min']].map(x => `<tr><td class="muted">${x[0]}</td><td class="role">${x[1]}</td><td class="muted">${x[2]}</td><td class="table-score">${x[3]}</td><td class="muted">${x[4]}</td><td><span class="status">Completed</span></td></tr>`).join('')}</tbody></table></section></main>`); }
function profile() { shell(`<main class="page">${pageHeading('Account', 'Profile & settings', 'Keep your profile current so your practice stays relevant.')}<section class="profile-grid"><article class="card profile-card"><div class="profile-head"><div class="profile-avatar">AK</div><div><h3 style="margin-bottom:2px">Alex Kim</h3><span class="muted">alex.kim@example.com</span></div></div><div class="profile-details"><div class="profile-detail"><span>Target role</span><strong>Machine Learning Engineer</strong></div><div class="profile-detail"><span>Experience level</span><strong>Mid-level · 3 years</strong></div><div class="profile-detail"><span>Resume</span><strong style="color:var(--blue)">Parshav_Khoche_Resume.pdf</strong></div><div class="profile-detail"><span>Member since</span><strong>January 2026</strong></div></div><button class="btn btn-secondary" style="width:100%;margin-top:26px">Edit profile</button></article><article class="card profile-card"><h3>Preferences</h3><div class="setting-row"><div><strong>Interview reminders</strong><p class="muted" style="margin:3px 0 0;font-size:12px">Get a gentle nudge to keep practicing.</p></div><button class="switch on"><span></span></button></div><div class="setting-row"><div><strong>Session summaries</strong><p class="muted" style="margin:3px 0 0;font-size:12px">Receive feedback after every interview.</p></div><button class="switch on"><span></span></button></div><div class="setting-row"><div><strong>Weekly progress email</strong><p class="muted" style="margin:3px 0 0;font-size:12px">A compact look at your growth.</p></div><button class="switch"><span></span></button></div><h3 style="margin-top:30px">Your skills</h3><div class="tag-list"><span class="tag">Python</span><span class="tag">PyTorch</span><span class="tag">Computer Vision</span><span class="tag">FastAPI</span></div></article></section></main>`); }
function auth() { const registering = state.authMode === 'register'; shell(`<main class="page"><section class="card form-card auth-card"><p class="eyebrow">${registering ? 'Get started' : 'Welcome back'}</p><h1>${registering ? 'Create your InterviewAI account' : 'Sign in to InterviewAI'}</h1><p class="subtle">${registering ? 'Start personalized interview practice with your own account.' : 'Continue your personalized interview practice.'}</p>${registering ? '<div class="field"><label for="auth-name">Full name</label><input id="auth-name" type="text" autocomplete="name" placeholder="Your full name"></div>' : ''}<div class="field"><label for="auth-email">Email</label><input id="auth-email" type="email" autocomplete="email" placeholder="you@example.com"></div><div class="field"><label for="auth-password">Password</label><input id="auth-password" type="password" autocomplete="new-password" placeholder="Your password"></div><button class="btn btn-primary" id="auth-submit" style="width:100%">${registering ? 'Create account' : 'Sign in'}</button><button class="btn btn-quiet" id="auth-switch" type="button" style="width:100%;margin-top:10px">${registering ? 'Already have an account? Sign in' : 'New here? Create an account'}</button><p id="auth-error" class="subtle" role="alert" style="margin:14px 0 0"></p></section></main>`, true); }
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

function scheduleAnswerSubmission() {
  clearSilenceTimer();
  state.silenceTimer = setTimeout(() => { if (['LISTENING', 'USER_SPEAKING'].includes(state.interviewState) && state.transcript.trim()) submitVoiceAnswer(); }, VOICE_SILENCE_TIMEOUT_MS);
}

function beginListening() {
  if (state.processingAnswer || state.interviewState === 'INTERVIEW_COMPLETE') return;
  if (!state.speechRecognition?.available) {
    setRealtimeState('ERROR', 'Voice input is not supported in this browser.');
    showToast('Voice input is not supported in this browser');
    return;
  }
  state.transcript = '';
  state.interimTranscript = '';
  state.answerStartedAt = Date.now();
  updateRealtimeTranscript();
  setRealtimeState('LISTENING', 'Listening...');
  const started = state.speechRecognition.start({
    onStart: () => { state.microphoneStatus = 'LISTENING'; updateRealtimeStatus('Listening...'); },
    onInterim: transcript => { state.interimTranscript = transcript; state.microphoneStatus = 'USER_SPEAKING'; setRealtimeState('USER_SPEAKING', 'Listening...'); updateRealtimeTranscript(); clearSilenceTimer(); },
    onFinal: transcript => { state.transcript = `${state.transcript} ${transcript}`.trim(); state.interimTranscript = ''; state.microphoneStatus = 'USER_SPEAKING'; setRealtimeState('USER_SPEAKING', 'Listening...'); updateRealtimeTranscript(); scheduleAnswerSubmission(); },
    onEnd: () => { if (['LISTENING', 'USER_SPEAKING'].includes(state.interviewState) && state.transcript.trim()) scheduleAnswerSubmission(); },
    onError: error => { state.microphoneStatus = 'MIC_ERROR'; if (['LISTENING', 'USER_SPEAKING'].includes(state.interviewState)) { setRealtimeState('ERROR', error.message); showToast(error.message.includes('required') ? 'Microphone unavailable' : 'Microphone listening issue', error.message.includes('required') ? '' : 'Check browser permissions and retry.'); } updateRealtimeMediaUi(); }
  });
  if (!started && state.speechRecognition.available) showToast('Microphone unavailable', 'Check browser permissions and retry.');
}

function speakCurrentQuestion() {
  if (!state.remoteQuestion) return;
  if (!state.speaker) { beginListening(); return; }
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
  if (state.processingAnswer || !state.currentQuestionId || !state.transcript.trim()) return;
  state.processingAnswer = true;
  clearSilenceTimer();
  state.speechRecognition.stop();
  state.microphoneStatus = 'PROCESSING';
  setRealtimeState('PROCESSING_ANSWER', 'Analyzing your answer...');
  try {
    state.feedback = await interviewApi.answer(state.interviewId, { question_id: state.currentQuestionId, answer_text: state.transcript.trim(), response_duration_seconds: Math.round((Date.now() - state.answerStartedAt) / 1000) });
    const next = await interviewApi.currentQuestion(state.interviewId);
    if (next.question_number <= state.question) {
      await interviewApi.end(state.interviewId);
      state.processingAnswer = false;
      state.interviewState = 'INTERVIEW_COMPLETE';
      state.view = 'results';
      cleanupRealtimeInterview();
      render();
      return;
    }
    state.currentQuestionId = next.id;
    state.remoteQuestion = next.question_text;
    state.question = next.question_number;
    state.processingAnswer = false;
    render();
    speakCurrentQuestion();
  } catch (error) {
    state.processingAnswer = false;
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

/* legacyRealtimeLiveInterview() {
  shell(`<main class="interview-layout realtime-layout"><section><div class="video-stage realtime-stage"><div class="video-frame realtime-frame"><div class="video-label"><i class="live-dot"></i> Live interview</div><div class="timer" id="timer">${formatTime(state.timer)}</div><div class="participant user-participant"><video id="user-video" autoplay playsinline></video><span class="participant-label">You</span><span class="participant-state"><i class="live-dot"></i> Camera ${state.camera ? 'active' : 'off'}</span></div><div class="participant ai-participant" id="ai-presence" data-state="${state.interviewState}"><div class="video-avatar">AI</div><span class="participant-label">AI Interviewer</span><span class="participant-state" id="voice-status">Starting...</span></div></div></div><div class="question-card realtime-question"><div class="question-meta">QUESTION ${state.question} OF 10 · TECHNICAL KNOWLEDGE</div><h2>${state.remoteQuestion || 'Preparing your first question...'}</h2><div class="voice-transcript"><strong>Live transcript</strong><p id="live-transcript-text">Your answer will appear here...</p></div></div><div class="control-bar"><button class="icon-btn" id="camera-toggle" aria-label="Toggle camera">${icon('video')}</button><button class="icon-btn" id="speaker-toggle" aria-label="Toggle speaker">${icon('speaker')}</button><button class="icon-btn" id="retry-mic" aria-label="Retry microphone">${icon('mic')}</button><button class="btn btn-danger end" id="end-interview">End interview</button></div></section><aside class="ai-panel"><div class="ai-panel-header"><div class="ai-title"><span class="ai-small-mark">${icon('spark')}</span><div><strong>Interview Assistant</strong><span class="status" style="display:block"><i class="live-dot"></i> AI is active</span></div></div><span class="muted">•••</span></div><div class="focus-box"><div class="focus-title"><strong>Current focus</strong><span>Question ${state.question} / 10</span></div><div class="progress"><span style="width:${Math.min(state.question * 10, 100)}%"></span></div><p class="muted" style="font-size:12px;margin:8px 0 0">Technical Knowledge</p></div><div class="transcript" id="transcript"><div class="message"><span class="message-label">AI Interviewer</span><p>${state.remoteQuestion || 'Preparing your personalized question...'}</p></div><div class="message you"><span class="message-label">You</span><p id="panel-transcript">${state.transcript || 'Your live answer will appear here.'}</p></div></div><div class="insights"><h3>Live insights</h3>${[['Communication','82%','82%'],['Technical depth','76%','76%'],['Confidence','88%','88%']].map(x => `<div class="insight"><div class="insight-label"><span>${x[0]}</span><strong>${x[1]}</strong></div><div class="progress"><span style="width:${x[2]}"></span></div></div>`).join('')}<div class="tip"><strong>${icon('spark')} AI tip</strong>Answer naturally. The interviewer will wait through thoughtful pauses.</div></div></aside></main>`); startTimer(); initializeRealtimeInterview(); }
function updateRealtimeMediaUi() {
  const camera = document.querySelector('#camera-status');
  const cameraLabel = state.cameraStatus === 'CAMERA_ON' ? 'Camera on' : state.cameraStatus === 'CAMERA_PERMISSION_DENIED' ? 'Camera permission required' : state.cameraStatus === 'CAMERA_STARTING' ? 'Camera starting...' : 'Camera off';
  if (camera) camera.textContent = cameraLabel;
  const video = document.querySelector('#user-video');
  if (video) {
    const cameraOn = state.cameraStatus === 'CAMERA_ON' && Boolean(state.mediaStream?.getVideoTracks().some(track => track.readyState === 'live' && track.enabled));
    video.hidden = !cameraOn;
    video.classList.toggle('is-hidden', !cameraOn);
  }
  const cameraControl = document.querySelector('#camera-control-label');
  if (cameraControl) cameraControl.textContent = cameraLabel;
  const mic = document.querySelector('#microphone-status');
  if (mic) mic.textContent = ['MIC_ON', 'LISTENING', 'USER_SPEAKING'].includes(state.microphoneStatus) ? 'Microphone on' : state.microphoneStatus === 'MIC_ERROR' ? 'Microphone unavailable' : state.microphoneStatus === 'PROCESSING' ? 'Processing' : 'Microphone off';
  const speaker = document.querySelector('#speaker-toggle');
  if (speaker) {
    speaker.classList.toggle('is-off', !state.speaker);
    speaker.setAttribute('aria-pressed', String(state.speaker));
    speaker.dataset.state = state.interviewState;
  }
}
} */
function updateRealtimeMediaUi() {
  const camera = document.querySelector('#camera-status');
  const cameraLabel = state.cameraStatus === 'CAMERA_ON' ? 'Camera on' : state.cameraStatus === 'CAMERA_PERMISSION_DENIED' ? 'Camera permission required' : state.cameraStatus === 'CAMERA_STARTING' ? 'Camera starting...' : 'Camera off';
  if (camera) camera.textContent = cameraLabel;
  const video = document.querySelector('#user-video');
  if (video) {
    const cameraOn = state.cameraStatus === 'CAMERA_ON' && Boolean(state.mediaStream?.getVideoTracks().some(track => track.readyState === 'live' && track.enabled));
    video.hidden = !cameraOn;
    video.classList.toggle('is-hidden', !cameraOn);
  }
  const cameraControl = document.querySelector('#camera-control-label');
  if (cameraControl) cameraControl.textContent = cameraLabel;
  const mic = document.querySelector('#microphone-status');
  if (mic) mic.textContent = ['MIC_ON', 'LISTENING', 'USER_SPEAKING'].includes(state.microphoneStatus) ? 'Microphone on' : state.microphoneStatus === 'MIC_ERROR' ? 'Microphone unavailable' : state.microphoneStatus === 'PROCESSING' ? 'Processing' : 'Microphone off';
  const speaker = document.querySelector('#speaker-toggle');
  if (speaker) {
    speaker.classList.toggle('is-off', !state.speaker);
    speaker.setAttribute('aria-pressed', String(state.speaker));
    speaker.dataset.state = state.interviewState;
  }
}
function realtimeStateLabel() {
  return { IDLE: 'Preparing interview', AI_THINKING: 'AI is thinking', AI_SPEAKING: 'AI is speaking', LISTENING: 'Listening to you', USER_SPEAKING: 'Listening to you', PROCESSING_ANSWER: 'Processing your answer', INTERVIEW_COMPLETE: 'Interview complete', ERROR: 'Interview needs attention' }[state.interviewState] || 'Preparing interview';
}

function realtimeLiveInterview() {
  const status = realtimeStateLabel();
  const transcript = `${state.transcript} ${state.interimTranscript}`.trim();
  const aiSpeaking = state.interviewState === 'AI_SPEAKING';
  const candidateSpeaking = ['LISTENING', 'USER_SPEAKING'].includes(state.interviewState);
  if (!state.timerStarted) {
    state.timer = Number.parseInt(state.duration, 10) * 60;
    state.timerStarted = true;
  }
  shell(`<main class="live-interview" aria-label="Live AI interview">
    <header class="live-topbar"><div><span class="live-kicker">InterviewAI</span><strong>Live interview</strong></div><div class="live-session">Interview ${state.question} / 10 <span class="live-divider"></span><span id="timer">${formatTime(state.timer)}</span></div></header>
    <div class="live-status" aria-live="polite"><span class="status-pulse"></span><strong id="stage-status">${status}</strong><span>${state.interviewState === 'PROCESSING_ANSWER' ? 'Your answer is being evaluated' : 'Stay present and take your time'}</span></div>
    <section class="live-stage">
      <div class="candidate-tile participant user-participant"><video id="user-video" autoplay playsinline muted></video><div class="tile-gradient"></div><span class="participant-label">You</span><span class="participant-state" id="camera-status">Camera off</span></div>
      <div class="ai-tile participant ai-participant" id="ai-presence" data-state="${state.interviewState}"><div class="ai-orbit"><span></span><span></span><div class="video-avatar">AI</div></div><div class="ai-wave ${aiSpeaking ? 'active' : ''}" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div><strong>AI Interviewer</strong><span class="participant-state" id="voice-status">${status}</span></div>
      <div class="stage-timer"><span>Time remaining</span><strong>${formatTime(state.timer)}</strong></div>
    </section>
    <section class="live-workspace">
      <article class="interviewer-card"><div class="card-eyebrow"><span class="ai-small-mark">${icon('spark')}</span><span>AI INTERVIEWER</span><span class="question-count">Question ${state.question} of 10</span></div><h1>${state.remoteQuestion || 'Waiting for interviewer...'}</h1><span class="question-topic">${state.type.replace(' Interview', '')}</span></article>
      <article class="transcript-card"><div class="transcript-heading"><div><span class="card-eyebrow">LIVE TRANSCRIPT</span><strong>${candidateSpeaking ? 'Listening...' : state.interviewState === 'PROCESSING_ANSWER' ? 'Processing your answer...' : 'Your response'}</strong></div><div class="candidate-wave ${candidateSpeaking ? 'active' : ''}" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></div></div><p id="live-transcript-text">${transcript || (state.interviewState === 'PROCESSING_ANSWER' ? 'Processing your answer...' : 'Listening...')}</p></article>
      <aside class="analysis-card"><span class="card-eyebrow">INTERVIEW ANALYSIS</span><strong>${state.feedback ? 'Answer analyzed' : 'Waiting for answer'}</strong><span>${state.feedback ? 'Feedback received from the interviewer.' : 'Real feedback will appear after evaluation.'}</span></aside>
    </section>
    <div class="live-controls"><div class="control-group"><button class="live-control" id="camera-toggle" aria-label="Toggle camera">${icon('video')}<span id="camera-control-label">Camera</span></button><button class="live-control" id="retry-mic" aria-label="Toggle microphone">${icon('mic')}<span id="microphone-status">${state.microphoneStatus === 'MIC_ERROR' ? 'Microphone required' : 'Microphone'}</span></button><button class="live-control ${state.speaker ? '' : 'is-off'}" id="speaker-toggle" aria-label="Toggle speaker">${icon('speaker')}<span>Speaker</span></button></div><button class="btn btn-danger end" id="end-interview">End interview</button></div>
  </main>`);
  updateRealtimeMediaUi();
  startTimer();
  initializeRealtimeInterview();
}

function legacyRealtimeLiveInterview() {
  return;
  shell(`<main class="interview-layout realtime-layout"><section><div class="video-stage realtime-stage"><div class="video-frame realtime-frame"><div class="video-label"><i class="live-dot"></i> Live interview</div><div class="timer" id="timer">${formatTime(state.timer)}</div><div class="participant user-participant"><video id="user-video" autoplay playsinline></video><span class="participant-label">You</span><span class="participant-state" id="camera-status">Camera off</span></div><div class="participant ai-participant" id="ai-presence" data-state="${state.interviewState}"><div class="video-avatar">AI</div><span class="participant-label">AI Interviewer</span><span class="participant-state" id="voice-status">${state.interviewState === 'IDLE' ? 'Preparing...' : state.interviewState}</span></div></div></div><div class="question-card realtime-question"><div class="question-meta">QUESTION ${state.question} OF 10</div><h2>${state.remoteQuestion || 'Preparing your first question...'}</h2><div class="voice-transcript"><strong>Live transcript</strong><p id="live-transcript-text">${state.transcript || 'Listening for your answer...'}</p><span class="muted" id="microphone-status">Microphone off</span></div></div><div class="control-bar"><button class="icon-btn" id="camera-toggle" aria-label="Toggle camera">${icon('video')}</button><button class="icon-btn" id="speaker-toggle" aria-label="Toggle speaker">${icon('speaker')}</button><button class="icon-btn" id="retry-mic" aria-label="Retry microphone">${icon('mic')}</button><button class="btn btn-danger end" id="end-interview">End interview</button></div></section><aside class="ai-panel"><div class="ai-panel-header"><div class="ai-title"><span class="ai-small-mark">${icon('spark')}</span><div><strong>Interview Assistant</strong><span class="status" id="ai-status">${state.interviewState === 'IDLE' ? 'Preparing...' : state.interviewState}</span></div></div></div><div class="focus-box"><div class="focus-title"><strong>Current focus</strong><span>Question ${state.question} / 10</span></div><div class="progress"><span style="width:${Math.min(state.question * 10, 100)}%"></span></div></div><div class="transcript"><div class="message"><span class="message-label">AI Interviewer</span><p>${state.remoteQuestion || 'Preparing your personalized question...'}</p></div><div class="message you"><span class="message-label">You</span><p id="panel-transcript">${state.transcript || 'Your live answer will appear here.'}</p></div></div><div class="insights"><h3>Live insights</h3>${[['Communication','communication_score'],['Technical depth','technical_score'],['Confidence','confidence_score']].map(([label, key]) => { const score = state.feedback?.[key]; return `<div class="insight"><div class="insight-label"><span>${label}</span><strong>${score == null ? 'Not scored yet' : `${Math.round(score)}%`}</strong></div><div class="progress"><span style="width:${score == null ? 0 : `${Math.round(score)}%`}"></span></div></div>`; }).join('')}</div></aside></main>`); startTimer(); initializeRealtimeInterview(); updateRealtimeMediaUi(); }
function emptyState(title, detail, action = '') { return `<section class="card empty-state"><div class="empty-icon">${icon('spark')}</div><h3>${title}</h3><p class="subtle">${detail}</p>${action}</section>`; }
function accountDashboard() {
  const completed = state.interviews.filter(item => item.status === 'COMPLETED');
  const scores = completed.map(item => item.overall_score).filter(score => score !== null && score !== undefined);
  const average = scores.length ? `${Math.round(scores.reduce((total, score) => total + score, 0) / scores.length)}%` : '-';
  shell(`<main class="page">${pageHeading('Your workspace', `Good to see you, ${state.user?.full_name || 'there'}`, 'Your practice data belongs to this account.', '<button class="btn btn-primary" data-view="resume">Start new interview ' + icon('arrow') + '</button>')}<section class="stat-grid"><article class="card stat-card"><div class="stat-top"><span>Interviews completed</span><span class="stat-icon">↗</span></div><strong class="stat-value">${completed.length}</strong><span class="muted">Saved to your account</span></article><article class="card stat-card"><div class="stat-top"><span>Resumes</span><span class="stat-icon">${icon('file')}</span></div><strong class="stat-value">${state.resumes.length}</strong><span class="muted">Uploaded resumes</span></article><article class="card stat-card"><div class="stat-top"><span>Average score</span><span class="stat-icon">✦</span></div><strong class="stat-value">${average}</strong><span class="muted">Completed interviews only</span></article><article class="card stat-card"><div class="stat-top"><span>Jobs prepared</span><span class="stat-icon">◷</span></div><strong class="stat-value">${state.jobs.length}</strong><span class="muted">Personalized job contexts</span></article></section>${state.interviews.length ? `<section class="card panel"><div class="panel-heading"><h3>Recent practice</h3><button class="btn btn-quiet" data-view="history">View all ${icon('arrow')}</button></div><div class="activity-list">${state.interviews.slice(0, 5).map(item => `<div class="activity"><span class="activity-badge">✦</span><div class="activity-copy"><strong>${item.interview_type}</strong><span>${new Date(item.created_at).toLocaleString()} · ${item.status}</span></div><span class="score-pill">${item.overall_score == null ? '-' : `${Math.round(item.overall_score)}%`}</span></div>`).join('')}</div></section>` : emptyState('Your dashboard is ready', 'Complete your first interview to see progress here.', '<button class="btn btn-secondary" data-view="resume">Set up an interview</button>')}</main>`);
}
function accountHistory() {
  shell(`<main class="page">${pageHeading('Your progress', 'Interview history', 'Only interviews from your authenticated account appear here.', '<button class="btn btn-primary" data-view="resume">Start new interview ' + icon('arrow') + '</button>')}${state.interviews.length ? `<section class="card table-wrap"><table class="history-table"><thead><tr><th>Date</th><th>Interview type</th><th>Score</th><th>Duration</th><th>Status</th></tr></thead><tbody>${state.interviews.map(item => `<tr><td class="muted">${new Date(item.created_at).toLocaleString()}</td><td class="role">${item.interview_type}</td><td class="table-score">${item.overall_score == null ? '-' : `${Math.round(item.overall_score)}%`}</td><td class="muted">${item.actual_duration_seconds ? `${Math.round(item.actual_duration_seconds / 60)} min` : '-'}</td><td><span class="status">${item.status}</span></td></tr>`).join('')}</tbody></table></section>` : emptyState('No interviews yet', 'Your completed and in-progress interviews will appear here.')}</main>`);
}
function accountProfile() {
  const user = state.user || {};
  shell(`<main class="page">${pageHeading('Account', 'Profile & settings', 'This profile is loaded from the current authenticated session.')}<section class="profile-grid"><article class="card profile-card"><div class="profile-head"><div class="profile-avatar">${userInitials()}</div><div><h3 style="margin-bottom:2px">${user.full_name || 'Account'}</h3><span class="muted">${user.email || ''}</span></div></div><div class="profile-details"><div class="profile-detail"><span>Account status</span><strong>${user.is_active ? 'Active' : 'Inactive'}</strong></div><div class="profile-detail"><span>Resume</span><strong>${state.resumes[0]?.original_filename || 'No resume uploaded'}</strong></div><div class="profile-detail"><span>Interviews</span><strong>${state.interviews.length}</strong></div></div></article><article class="card profile-card"><h3>Your current data</h3><p class="subtle">${state.resumes.length} resume(s), ${state.jobs.length} job context(s), and ${state.interviews.length} interview(s) are associated with this account.</p></article></section></main>`);
}
async function loadUserData() {
  if (!getAuthToken()) return;
  try {
    const [user, resumes, jobs, interviews] = await Promise.all([userApi.profile(), resumeApi.list(), jobApi.list(), interviewApi.history()]);
    Object.assign(state, { user, resumes, jobs, interviews });
    if (state.view !== 'auth') render();
  } catch (error) {
    if (error.status === 401) { resetUserState(); window.history.replaceState({}, '', '#login'); render(); }
    else showToast('Could not load your account', normalizeApiError(error));
  }
}
function render() { ({ dashboard: accountDashboard, resume, setup, lobby, interview: realtimeLiveInterview, results: resultsFromApi, history: accountHistory, profile: accountProfile, auth }[state.view] || accountDashboard)(); }
let timerId;
function startTimer() { clearInterval(timerId); timerId = setInterval(() => { if (state.view !== 'interview') return clearInterval(timerId); state.timer = Math.max(0, state.timer - 1); const timer = document.querySelector('#timer'); if (timer) timer.textContent = formatTime(state.timer); if (state.timer === 0) { clearInterval(timerId); showEndModal(); } }, 1000); }
function bindEvents() {
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => { state.view = button.dataset.view; render(); }));
  document.querySelectorAll('[data-option]').forEach(button => button.addEventListener('click', () => { state[button.dataset.option] = button.dataset.value; render(); }));
  document.querySelectorAll('.filter').forEach(button => button.addEventListener('click', () => { document.querySelectorAll('.filter').forEach(item => item.classList.remove('active')); button.classList.add('active'); showToast('Filter updated', `Showing ${button.textContent.toLowerCase()} sessions.`); }));
  document.querySelectorAll('.review-toggle').forEach(button => button.addEventListener('click', () => button.closest('.review-item').classList.toggle('open')));
  document.querySelectorAll('.switch').forEach(button => button.addEventListener('click', () => button.classList.toggle('on')));
  const input = document.querySelector('#resume-input'); const zone = document.querySelector('#upload-zone');
  if (input && zone) { input.addEventListener('change', event => handleFile(event.target.files[0])); ['dragenter','dragover'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.add('dragover'); })); ['dragleave','drop'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.remove('dragover'); })); zone.addEventListener('drop', event => handleFile(event.dataTransfer.files[0])); if (state.resume) document.querySelector('#resume-result').innerHTML = resumeResult(); }
    if (input && zone) { input.addEventListener('change', event => handleFile(event.target.files[0])); ['dragenter','dragover'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.add('dragover'); })); ['dragleave','drop'].forEach(type => zone.addEventListener(type, event => { event.preventDefault(); zone.classList.remove('dragover'); })); zone.addEventListener('drop', event => handleFile(event.dataTransfer.files[0])); if (state.resume || state.resumes.length) document.querySelector('#resume-result').innerHTML = resumeResult(); }
  document.querySelector('#remove-resume')?.addEventListener('click', () => { state.resume = null; render(); });
  document.querySelector('#auth-switch')?.addEventListener('click', () => { state.authMode = state.authMode === 'login' ? 'register' : 'login'; render(); });
  document.querySelector('#auth-submit')?.addEventListener('click', async () => { const error = document.querySelector('#auth-error'); try { const payload = { email: document.querySelector('#auth-email').value, password: document.querySelector('#auth-password').value }; if (state.authMode === 'register') { payload.full_name = document.querySelector('#auth-name').value; await authApi.register(payload); } else { await authApi.login(payload); } state.view = 'dashboard'; window.history.replaceState({}, '', window.location.pathname); render(); await loadUserData(); } catch (authError) { if (error) error.textContent = normalizeApiError(authError); } });
  document.querySelector('#prepare-interview')?.addEventListener('click', async () => { state.role = document.querySelector('#role').value || state.role; showToast('Preparing your interview', 'Generating personalized questions...'); if (getAuthToken()) { try { const job = await api('/api/jobs', { method: 'POST', body: JSON.stringify({ title: state.role, job_description: document.querySelector('#description')?.value || '' }) }); const interview = await interviewApi.create({ job_id: job.id, resume_id: state.resume?.id || null, interview_type: state.type, difficulty: state.difficulty, duration_target_minutes: Number.parseInt(state.duration, 10) }); state.interviewId = interview.id; } catch (error) { showToast('Interview setup failed', error.message); return; } } setTimeout(() => { state.view = 'lobby'; render(); }, 650); });
  document.querySelector('[data-view="interview"]')?.addEventListener('click', async () => { if (getAuthToken() && state.interviewId) { try { await ensureInterviewStarted(); render(); } catch (error) { showToast('Interview could not start', error.message); } } });
  document.querySelector('#camera-toggle')?.addEventListener('click', toggleCamera);
  document.querySelector('#speaker-toggle')?.addEventListener('click', event => { state.speaker = !state.speaker; if (!state.speaker) { state.textToSpeech?.stop(); if (state.interviewState === 'AI_SPEAKING') beginListening(); } updateRealtimeMediaUi(); showToast(state.speaker ? 'Speaker on' : 'Speaker off'); });
  document.querySelector('#retry-mic')?.addEventListener('click', () => { if (state.interviewState === 'LISTENING') beginListening(); else initializeRealtimeInterview(); });
  document.querySelector('#end-interview')?.addEventListener('click', showEndModal);
}
async function handleFile(file) { if (!file) return; const valid = ['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document']; if (!valid.includes(file.type) && !/\.(pdf|docx)$/i.test(file.name)) return showToast('Resume upload failed', 'Please upload a PDF or DOCX under 10MB.'); if (file.size > 10 * 1024 * 1024) return showToast('Resume upload failed', 'Please choose a file under 10MB.'); state.resume = { name: file.name, size: `${(file.size / 1024 / 1024).toFixed(1)} MB` }; document.querySelector('#resume-result').innerHTML = `<div class="thinking" style="margin-top:18px">${icon('spark')} Analyzing resume... <i></i><i></i><i></i></div>`; if (getAuthToken()) { try { const uploaded = await resumeApi.upload(file); state.resume.id = uploaded.id; } catch (error) { showToast('Resume upload failed', error.message); return; } } setTimeout(() => { const result = document.querySelector('#resume-result'); if (result) { result.innerHTML = resumeResult(); bindEvents(); showToast('Resume analyzed', 'Your interview context is ready.'); } }, 900); }
function showEndModal() { const backdrop = document.createElement('div'); backdrop.className = 'modal-backdrop'; backdrop.innerHTML = `<div class="modal" role="dialog" aria-modal="true" aria-labelledby="end-title"><p class="eyebrow">Finish session</p><h2 id="end-title">End this interview?</h2><p class="subtle">Your progress will be saved and you will receive a performance summary.</p><div class="modal-actions"><button class="btn btn-secondary" id="cancel-end">Cancel</button><button class="btn btn-danger" id="confirm-end">End interview</button></div></div>`; document.body.append(backdrop); backdrop.querySelector('#cancel-end').addEventListener('click', () => backdrop.remove()); backdrop.querySelector('#confirm-end').addEventListener('click', async () => { cleanupRealtimeInterview(); if (getAuthToken() && state.interviewId) { try { await interviewApi.end(state.interviewId); } catch (error) { showToast('Could not save interview', error.message); return; } } backdrop.remove(); state.interviewState = 'INTERVIEW_COMPLETE'; state.view = 'results'; render(); }); }
render();
loadUserData();
