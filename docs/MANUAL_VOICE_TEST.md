# Manual browser voice verification

Use this checklist on a real Chrome browser with a working camera and microphone.

1. Start the API on port 8002 and open `http://127.0.0.1:8002/` in Chrome.
2. Register, enter the verification token, and confirm the dashboard appears.
3. Upload a real text-bearing PDF resume. Expected: `Resume analyzed` and `Resume detected` appear.
4. Choose a role and interview settings, then enter the interview. Expected: a real question appears.
5. Allow camera and microphone permissions. Expected: camera preview and both permissions are active.
6. Confirm the question is spoken aloud by browser speech synthesis.
7. Speak a clear answer. Expected: the final transcript appears.
8. Stop speaking and stay silent for about 2.5 seconds. Expected: the answer POST completes and the next question appears.
9. End the interview. Expected: final feedback and score render.
10. Repeat with camera permission denied. Expected: camera fallback is shown and the interview continues.
11. Repeat with microphone permission denied. Expected: microphone error and text input fallback appear.
12. Repeat in a browser without speech recognition. Expected: text input fallback appears instead of blocking the session.

If any step fails, inspect the browser console for permission errors, confirm the site is a secure context, confirm the selected microphone/camera is available, and verify `/health` and `/health/llm`. If speech is unavailable, use the text fallback; if permissions are denied, grant them and retry the interview.
