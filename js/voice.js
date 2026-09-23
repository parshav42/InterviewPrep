export class BrowserTextToSpeechProvider {
  constructor() { this.synthesis = window.speechSynthesis; }

  get available() { return Boolean(this.synthesis && window.SpeechSynthesisUtterance); }

  speak(text, { onStart, onEnd, onError } = {}) {
    if (!this.available) {
      onError?.(new Error('Text-to-speech is not supported in this browser.'));
      return;
    }
    this.stop();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.96;
    utterance.pitch = 1;
    utterance.onstart = () => onStart?.();
    utterance.onend = () => onEnd?.();
    utterance.onerror = event => onError?.(new Error(event.error || 'Text-to-speech failed.'));
    this.synthesis.speak(utterance);
  }

  stop() { this.synthesis?.cancel(); }
}

export class BrowserSpeechToTextProvider {
  constructor() {
    this.Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    this.recognition = null;
    this.onInterim = null;
    this.onFinal = null;
    this.onStart = null;
    this.onEnd = null;
    this.onError = null;
  }

  get available() { return Boolean(this.Recognition); }

  start({ onInterim, onFinal, onStart, onEnd, onError } = {}) {
    if (!this.available) {
      onError?.(new Error('Voice input is not supported in this browser'));
      return false;
    }
    this.stop();
    this.onInterim = onInterim;
    this.onFinal = onFinal;
    this.onStart = onStart;
    this.onEnd = onEnd;
    this.onError = onError;
    const recognition = new this.Recognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';
    recognition.onresult = event => {
      let interim = '';
      let finalText = '';
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const transcript = event.results[index][0].transcript.trim();
        if (event.results[index].isFinal) finalText += `${transcript} `;
        else interim += `${transcript} `;
      }
      if (interim) this.onInterim?.(interim.trim());
      if (finalText) this.onFinal?.(finalText.trim());
    };
    recognition.onend = () => this.onEnd?.();
    recognition.onerror = event => {
      const message = event.error === 'not-allowed' || event.error === 'service-not-allowed'
        ? 'Microphone access is required for the voice interview.'
        : (event.error || 'Speech recognition failed.');
      this.onError?.(new Error(message));
    };
    this.recognition = recognition;
    recognition.onstart = () => this.onStart?.();
    try {
      recognition.start();
    } catch (error) {
      this.recognition = null;
      onError?.(error);
      return false;
    }
    return true;
  }

  stop() {
    if (!this.recognition) return;
    this.recognition.onend = null;
    this.recognition.onerror = null;
    try { this.recognition.stop(); } catch (error) { /* already stopped */ }
    this.recognition = null;
  }
}

export async function requestInterviewMedia() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera and microphone access are not supported in this browser.');
  return navigator.mediaDevices.getUserMedia({ video: true, audio: true });
}

export async function requestInterviewCamera() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access is not supported in this browser.');
  return navigator.mediaDevices.getUserMedia({ video: true, audio: false });
}

export async function requestInterviewMicrophone() {
  if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access is not supported in this browser.');
  return navigator.mediaDevices.getUserMedia({ video: false, audio: true });
}

export function stopInterviewMedia(stream) {
  stream?.getTracks().forEach(track => track.stop());
}
