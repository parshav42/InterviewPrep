import test from 'node:test';
import assert from 'node:assert/strict';

const makeDocument = () => {
  const iconLink = { rel: 'icon', href: '/favicon.ico' };
  return {
    title: 'InterviewAI | Practice with purpose',
    hidden: false,
    addEventListener: () => {},
    removeEventListener: () => {},
    head: { appendChild: () => {} },
    querySelector: (selector) => {
      if (selector === 'link[rel*="icon"]') return iconLink;
      return null;
    },
  };
};

test('useTabTitleAnimation restores the original title and clears the interval on focus', async () => {
  const originalDocument = globalThis.document;
  const originalWindow = globalThis.window;

  globalThis.document = makeDocument();
  globalThis.window = {
    matchMedia: () => ({ matches: false }),
    addEventListener: () => {},
    removeEventListener: () => {},
    focus: () => {},
  };

  try {
    const { useTabTitleAnimation } = await import('./useTabTitleAnimation.mjs');
    const cleanup = useTabTitleAnimation();

    cleanup.stop();
    assert.equal(globalThis.document.title, 'InterviewAI | Practice with purpose');
  } finally {
    globalThis.document = originalDocument;
    globalThis.window = originalWindow;
  }
});
