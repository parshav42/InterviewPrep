import { test, expect } from '@playwright/test';

const apiBase = process.env.E2E_API_BASE || 'http://127.0.0.1:8002/api';
const password = 'correct horse battery';

function pdfFixture() {
  return Buffer.from('JVBERi0xLjcKJcK1wrYKCjEgMCBvYmoKPDwvVHlwZS9DYXRhbG9nL1BhZ2VzIDIgMCBSPj4KZW5kb2JqCgoyIDAgb2JqCjw8L1R5cGUvUGFnZXMvQ291bnQgMS9LaWRzWzQgMCBSXT4+CmVuZG9iagoKMyAwIG9iago8PC9Gb250PDwvaGVsdiA1IDAgUj4+Pj4KZW5kb2JqCgo0IDAgb2JqCjw8L1R5cGUvUGFnZS9NZWRpYUJveFswIDAgNTk1IDg0Ml0vUm90YXRlIDAvUmVzb3VyY2VzIDMgMCBSL1BhcmVudCAyIDAgUi9Db250ZW50c1s2IDAgUl0+PgplbmRvYmoKCjUgMCBvYmoKPDwvVHlwZS9Gb250L1N1YnR5cGUvVHlwZTEvQmFzZUZvbnQvSGVsdmV0aWNhL0VuY29kaW5nL1dpbkFuc2lFbmNvZGluZz4+CmVuZG9iagoKNiAwIG9iago8PC9MZW5ndGggMTA2L0ZpbHRlci9GbGF0ZURlY29kZT4+CnN0cmVhbQp42hWLMQpCQQxE+5wiNzDJJpO/IBaCjZ2QTiz3Y6GFjec3MszwGHj0oXORsnSU0zhTuN50eK7Xl1W5dr4ffUCx4JhdTUeYhORs2rBjmTj6H+muIT5NELnlf62daHcgTo+60qXoRj/3URnbCmVuZHN0cmVhbQplbmRvYmoKCnhyZWYKMCA3CjAwMDAwMDAwMDAgMDAwMDEgZiAKMDAwMDAwMDAxNiAwMDAwMCBuIAowMDAwMDAwMDYyIDAwMDAwIG4gCjAwMDAwMDAxMTQgMDAwMDAgbiAKMDAwMDAwMDE1NSAwMDAwMCBuIAowMDAwMDAwMjYyIDAwMDAwIG4gCjAwMDAwMDAzNTEgMDAwMDAgbiAKCnRyYWlsZXIKPDwvU2l6ZSA3L1Jvb3QgMSAwIFIvSURbPEMzOUNDMzhENURD MkIxQzJBNzQ3NjQ1Nzc5QzM5MDZBPjw5MkFEQkI1NUM4MkVDNDQ2OTlCQTFEQTUyOUFFRjU3Nz5dPj4Kc3RhcnR4cmVmCjUyNgolJUVPRgo='.replaceAll(' ', ''), 'base64');
}

test('fake-media authenticated interview flow', async ({ page, request }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const register = await request.post(`${apiBase}/auth/register`, { data: { email, password, full_name: 'E2E Candidate' } });
  expect(register.status()).toBe(201);
  const registered = await register.json();
  const auth = registered;
  const verification = await request.post(`${apiBase}/auth/verify-email`, { params: { token: auth.verification_token } });
  expect(verification.status()).toBe(200);
  const pageErrors = [];
  const consoleMessages = [];
  const answerRequests = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', message => consoleMessages.push(message.text()));
  page.on('request', request => { if (request.url().includes('/answer') && request.method() === 'POST') answerRequests.push(request); });

  await page.addInitScript(({ accessToken, apiBaseUrl }) => {
    localStorage.setItem('interviewai_access_token', accessToken);
    window.INTERVIEW_API_BASE = apiBaseUrl;
    window.__mediaStreams = [];
    window.__unhandledRejections = [];
    window.addEventListener('unhandledrejection', event => window.__unhandledRejections.push(String(event.reason)));
    const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
    navigator.mediaDevices.getUserMedia = async constraints => {
      const stream = await originalGetUserMedia(constraints);
      window.__mediaStreams.push(stream);
      return stream;
    };
    window.SpeechSynthesisUtterance = class { constructor(text) { this.text = text; } };
    const order = [];
    window.__voiceOrder = order;
    window.speechSynthesis.getVoices = () => [{ lang: 'en-US', name: 'Fake English' }];
    window.speechSynthesis.speak = utterance => {
      order.push('speak-called');
      window.__ttsCalls = (window.__ttsCalls || 0) + 1;
      (window.__ttsTexts || (window.__ttsTexts = [])).push(utterance.text);
      setTimeout(() => { order.push('speak-resolved'); utterance.onstart?.(); utterance.onend?.(); }, 50);
    };
    window.speechSynthesis.cancel = () => {};
    Object.defineProperty(window.speechSynthesis, 'speaking', { configurable: true, get: () => false });
    class FakeRecognition {
      constructor() { window.__recognition = this; }
      start() { window.__voiceOrder.push('recognition-start'); window.__recognitionStarted = true; this.onstart?.(); }
      stop() { this.onend?.(); }
    }
    window.SpeechRecognition = FakeRecognition;
    window.webkitSpeechRecognition = FakeRecognition;
  }, { accessToken: auth.access_token, apiBaseUrl: apiBase });
  await page.goto('/');
  await expect(page.getByText('Your workspace')).toBeVisible();
  await expect(page.locator('body')).toContainText(/Your workspace/i);

  await page.getByRole('button', { name: /Start new interview/ }).click();
  await page.locator('#resume-input').setInputFiles({ name: 'resume.pdf', mimeType: 'application/pdf', buffer: pdfFixture() });
  await expect(page.locator('#resume-result')).toContainText('Resume analyzed');
  expect(await page.locator('#resume-result').innerText()).toContain('Resume detected');
  await page.getByRole('button', { name: /Continue to job setup/ }).click();
  await page.locator('#prepare-interview').click();
  await expect(page.getByText("You're all set.")).toBeVisible();
  await page.getByRole('button', { name: /Enter interview/ }).click();
  await expect(page.locator('#user-video')).toBeVisible();
  await expect(page.locator('.interviewer-card h1')).not.toHaveText('Waiting for interviewer...');
  expect(await page.locator('.interviewer-card h1').innerText()).toMatch(/project|experience|role/i);
  expect(await page.evaluate(() => window.__ttsCalls)).toBeGreaterThan(0);
  await expect.poll(() => page.evaluate(() => window.__recognitionStarted)).toBe(true);
  await expect.poll(() => page.evaluate(() => typeof window.__recognition?.onresult)).toBe('function');
  expect(await page.evaluate(() => window.__voiceOrder.indexOf('speak-resolved') < window.__voiceOrder.indexOf('recognition-start'))).toBe(true);
  const questionOne = await page.locator('.interviewer-card h1').innerText();
  await page.waitForTimeout(1000);
  await page.evaluate(question => {
    window.__recognition.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: question } }] });
  }, questionOne);
  await page.waitForTimeout(100);
  await page.waitForTimeout(100);
  expect(answerRequests).toHaveLength(0);
  expect(await page.evaluate(() => window.__mediaStreams.some(stream => stream.getVideoTracks()[0]?.readyState === 'live'))).toBe(true);
  expect(await page.evaluate(() => window.__mediaStreams.some(stream => stream.getAudioTracks()[0]?.readyState === 'live'))).toBe(true);
  expect(await page.evaluate(() => window.__recognition !== undefined)).toBe(true);
  const initialTimer = await page.locator('#timer').innerText();
  await page.waitForTimeout(2100);
  expect(await page.locator('#timer').innerText()).not.toBe(initialTimer);
  const answers = [
    'I built a reliable machine learning pipeline with measurable latency improvements.',
    'I validated the model with holdout data and monitored precision in production.',
    'I worked with product partners to define success metrics and ship the system.'
  ];
  const questionNumbers = ['Question 2', 'Question 3', 'Question 4'];
  for (let index = 0; index < answers.length; index += 1) {
    const answerResponse = page.waitForResponse(response => response.url().includes('/answer') && response.request().method() === 'POST');
    await page.evaluate(answer => {
      window.__recognition.onresult?.({ resultIndex: 0, results: [{ isFinal: true, 0: { transcript: answer } }] });
    }, answers[index]);
    await answerResponse;
    await expect(page.locator('.question-count')).toContainText(questionNumbers[index]);
  }
  const spokenQuestions = await page.evaluate(() => window.__ttsTexts);
  expect(spokenQuestions).toHaveLength(4);
  expect(new Set(spokenQuestions).size).toBe(spokenQuestions.length);
  expect(await page.locator('.question-count').innerText()).toContain('Question 4 of 10');
  await page.getByRole('button', { name: 'End interview' }).click();
  await page.getByRole('button', { name: 'End interview' }).last().click();
  await expect(page.locator('.results-hero h2')).toHaveText('Interview complete');
  await expect(page.locator('.results-hero')).toContainText('solid interview');

  expect(pageErrors.filter(message => message.includes('ReferenceError'))).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(await page.evaluate(() => window.__unhandledRejections)).toEqual([]);
  console.log(JSON.stringify({ spokenQuestions, echoDiscarded: consoleMessages.includes('[echo-filter] discarded STT result matching question') }));
});
