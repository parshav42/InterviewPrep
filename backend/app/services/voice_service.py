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
