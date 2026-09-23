from typing import Protocol


class SpeechToTextProvider(Protocol):
    def transcribe_audio(self, audio: bytes, content_type: str) -> str: ...


class TextToSpeechProvider(Protocol):
    def generate_speech(self, text: str) -> bytes: ...


class UnconfiguredSpeechProvider:
    def transcribe_audio(self, audio: bytes, content_type: str) -> str:
        _ = (audio, content_type)
        raise RuntimeError("Speech-to-text provider is not configured")


class UnconfiguredTextToSpeechProvider:
    def generate_speech(self, text: str) -> bytes:
        _ = text
        raise RuntimeError("Text-to-speech provider is not configured")


class DeterministicSpeechProvider:
    def transcribe_audio(self, audio: bytes, content_type: str) -> str:
        _ = content_type
        return "Audio response received." if audio else ""


class DeterministicTextToSpeechProvider:
    def generate_speech(self, text: str) -> bytes:
        payload = text.encode("utf-8")[:16000]
        return b"RIFF" + (len(payload) + 36).to_bytes(4, "little") + b"WAVEfmt " + (16).to_bytes(4, "little") + (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + (8000).to_bytes(4, "little") + (16000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little") + b"data" + len(payload).to_bytes(4, "little") + payload
