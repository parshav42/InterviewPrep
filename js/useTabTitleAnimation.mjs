const DEFAULT_MESSAGES = [
  '🔥 Heyy',
  '👋 Heyyy, come back!',
  '💬 Don\'t leave us hanging',
  '✨ Your interview awaits',
];

function getFaviconLink() {
  if (typeof document === 'undefined') return null;
  const existing = document.querySelector('link[rel*="icon"]');
  if (existing) return existing;
  const link = document.createElement('link');
  link.rel = 'icon';
  link.type = 'image/svg+xml';
  document.head.appendChild(link);
  return link;
}

function buildNotifyFavicon() {
  const svg = `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
      <rect width="64" height="64" rx="14" fill="#0f172a"/>
      <circle cx="48" cy="16" r="10" fill="#ef4444"/>
      <path d="M18 20v22l18-11-18-11Z" fill="#f8fafc"/>
    </svg>
  `;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function useTabTitleAnimation({
  intervalMs = 1500,
  messages = DEFAULT_MESSAGES,
  reducedMotionMessage = 'Come back 👋',
} = {}) {
  if (typeof document === 'undefined' || typeof window === 'undefined') {
    return { start() {}, stop() {}, cleanup() {} };
  }

  const originalTitle = document.title || 'InterviewAI';
  const originalFaviconUrl = getFaviconLink()?.href || '/favicon.ico';
  const mediaQuery = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;

  let timerId = null;
  let isActive = false;
  let frameIndex = 0;
  let reducedMotion = Boolean(mediaQuery?.matches);

  const syncReducedMotion = () => {
    reducedMotion = Boolean(mediaQuery?.matches);
  };

  const applyFavicon = (url) => {
    const link = getFaviconLink();
    if (!link) return;
    link.rel = 'icon';
    link.type = 'image/svg+xml';
    link.href = url;
  };

  const restoreOriginalState = () => {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
    document.title = originalTitle;
    applyFavicon(originalFaviconUrl);
    isActive = false;
    frameIndex = 0;
  };

  const start = () => {
    if (reducedMotion) {
      if (timerId) {
        clearInterval(timerId);
        timerId = null;
      }
      isActive = true;
      document.title = reducedMotionMessage;
      applyFavicon(buildNotifyFavicon());
      return;
    }

    if (timerId) {
      clearInterval(timerId);
    }

    const frames = [originalTitle, ...messages, originalTitle];
    isActive = true;
    frameIndex = 0;

    const tick = () => {
      if (!isActive) return;
      const nextTitle = frames[frameIndex % frames.length];
      document.title = nextTitle;
      applyFavicon(buildNotifyFavicon());
      frameIndex += 1;
    };

    tick();
    timerId = window.setInterval(tick, intervalMs);
  };

  const stop = () => {
    if (timerId) {
      clearInterval(timerId);
      timerId = null;
    }
    restoreOriginalState();
  };

  const handleVisibilityChange = () => {
    if (document.hidden) {
      start();
    } else {
      stop();
    }
  };

  const handleBlur = () => {
    start();
  };

  const handleFocus = () => {
    stop();
  };

  if (mediaQuery && mediaQuery.addEventListener) {
    mediaQuery.addEventListener('change', syncReducedMotion);
  } else if (mediaQuery && mediaQuery.addListener) {
    mediaQuery.addListener(syncReducedMotion);
  }

  document.addEventListener('visibilitychange', handleVisibilityChange);
  window.addEventListener('blur', handleBlur);
  window.addEventListener('focus', handleFocus);

  const cleanup = () => {
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    window.removeEventListener('blur', handleBlur);
    window.removeEventListener('focus', handleFocus);

    if (mediaQuery && mediaQuery.removeEventListener) {
      mediaQuery.removeEventListener('change', syncReducedMotion);
    } else if (mediaQuery && mediaQuery.removeListener) {
      mediaQuery.removeListener(syncReducedMotion);
    }

    stop();
  };

  return { start, stop, cleanup };
}

export default useTabTitleAnimation;
