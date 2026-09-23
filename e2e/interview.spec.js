import { test, expect } from '@playwright/test';

const apiBase = process.env.E2E_API_BASE || 'http://127.0.0.1:8002/api';
const password = 'correct horse battery';

function pdfFixture() {
  return Buffer.from('%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF');
}

test('fake-media authenticated interview flow', async ({ page, request }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const register = await request.post(`${apiBase}/auth/register`, { data: { email, password, full_name: 'E2E Candidate' } });
  expect(register.status()).toBe(201);
  const registered = await register.json();
  const token = registered.access_token;
  const headers = { Authorization: `Bearer ${token}` };

  const verification = await request.post(`${apiBase}/auth/verify-email`, { params: { token: process.env.E2E_VERIFY_TOKEN || 'invalid-token' } });
  expect([200, 400]).toContain(verification.status());

  const login = await request.post(`${apiBase}/auth/login`, { data: { email, password } });
  expect(login.status()).toBe(200);
  const auth = await login.json();
  const authHeaders = { Authorization: `Bearer ${auth.access_token}` };

  const job = await request.post(`${apiBase}/jobs`, { headers: authHeaders, data: { title: 'Machine Learning Engineer', job_description: 'Build machine learning systems.' } });
  expect(job.status()).toBe(201);
  const jobBody = await job.json();

  const resume = await request.post(`${apiBase}/resumes/upload`, {
    headers: authHeaders,
    multipart: { file: { name: 'resume.pdf', mimeType: 'application/pdf', buffer: pdfFixture() } }
  });
  expect([201, 422]).toContain(resume.status());
  const resumeBody = resume.status() === 201 ? await resume.json() : null;

  const interview = await request.post(`${apiBase}/interviews`, { headers: authHeaders, data: {
    job_id: jobBody.id, resume_id: resumeBody?.id, interview_type: 'Mixed Interview', difficulty: 'Intermediate', duration_target_minutes: 15
  } });
  expect(interview.status()).toBe(201);
  const interviewBody = await interview.json();

  await page.addInitScript(({ accessToken }) => {
    localStorage.setItem('interviewai_access_token', accessToken);
    window.speechSynthesis.speak = () => { window.__ttsCalls = (window.__ttsCalls || 0) + 1; };
    window.speechSynthesis.cancel = () => {};
  }, { accessToken: auth.access_token });
  await page.goto('/index.html');
  await expect(page.getByText('Your workspace')).toBeVisible();

  await page.evaluate((id) => { window.__e2eInterviewId = id; }, interviewBody.id);
  await expect(page.locator('body')).toContainText('Your workspace');
  const history = await request.get(`${apiBase}/interviews`, { headers: authHeaders });
  expect(history.status()).toBe(200);
});
