import logging
import os
import tempfile
import asyncio
from pydub import AudioSegment
from pydub.exceptions import CouldntDecodeError

from app.core.event_bus import EventBus
from app.core.events import SpeakRequestEvent, TTSSpeakingStateEvent, AIResponseEvent
from app.core.config import AppConfig
from app.utils.helpers import remove_emojis

logger = logging.getLogger(__name__)

class TTSService:
    def __init__(self, event_bus: EventBus, settings: AppConfig):
        self.event_bus = event_bus
        self.settings = settings
        self.volume_db_reduction = getattr(settings, 'TTS_INITIAL_VOLUME_REDUCTION_DB', 0.0)
        self.speech_speed = getattr(settings, 'TTS_SPEECH_SPEED', 1.0)
        self.pitch_semitones = getattr(settings, 'TTS_PITCH_SEMITONES', 0.0)

    async def start(self):
        logger.info("TTSService starting (headless mode, no playback).")
        self.event_bus.subscribe_async(SpeakRequestEvent, self.handle_speak_request)
        logger.info("TTSService ready to synthesize speech.")

    async def handle_speak_request(self, event: SpeakRequestEvent):
        logger.info(f"[TTSService] SpeakRequestEvent: '{event.text[:100]}'")

        if not event.text.strip():
            logger.warning("Empty speak request received. Skipping.")
            return

        wav_path = await self._synthesize_and_process(event.text)

        # Optionally emit speaking state or notify other services
        await self.event_bus.publish(TTSSpeakingStateEvent(is_speaking=False))

        # For now we don't auto-play or send to Discord — just return WAV path or handle in API

    async def _synthesize_and_process(self, text: str) -> str:
        safe_text = remove_emojis(text)
        if not safe_text.strip():
            logger.info("Skipping TTS, text is empty after emoji removal.")
            return ""

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_f:
            tmp_path = tmp_f.name

        logger.info(f"Calling Piper CLI for: '{safe_text[:60]}'")

        process = await asyncio.create_subprocess_exec(
            self.settings.PIPER_PATH,
            "--model", self.settings.PIPER_VOICE_MODEL,
            "--output_file", tmp_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate(input=safe_text.encode("utf-8"))

        if process.returncode != 0:
            err = stderr.decode(errors="ignore")
            logger.error(f"Piper failed: {err}")
            return ""

        try:
            audio = AudioSegment.from_wav(tmp_path)

            # Apply speed
            if self.speech_speed != 1.0:
                new_rate = int(audio.frame_rate * self.speech_speed)
                audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate})
                audio = audio.set_frame_rate(44100)

            # Apply pitch shift
            if self.pitch_semitones != 0.0:
                semitones = self.pitch_semitones / 12.0
                new_rate = int(audio.frame_rate * (2.0 ** semitones))
                audio = audio._spawn(audio.raw_data, overrides={"frame_rate": new_rate})
                audio = audio.set_frame_rate(44100)

            # Apply volume change
            if self.volume_db_reduction != 0.0:
                audio = audio - self.volume_db_reduction

            audio.export(tmp_path, format="wav")
            logger.info(f"TTS synthesis complete. Output saved to: {tmp_path}")
            return tmp_path

        except CouldntDecodeError:
            logger.error("Pydub failed to decode Piper output.")
            return ""
        
    def speak_to_file(self, text: str) -> str:
        """Generate speech from text and return path to the WAV file."""
        import tempfile
        import subprocess

        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_f:
            tmp_path = tmp_f.name

        process = subprocess.run(
            [
                self.settings.PIPER_PATH,
                "--model", self.settings.PIPER_VOICE_MODEL,
                "--output_file", tmp_path,
            ],
            input=text.encode("utf-8"),
            capture_output=True,
        )

        if process.returncode != 0:
            raise RuntimeError(f"Piper failed: {process.stderr.decode().strip()}")

        return tmp_path
    async def synthesize_to_wav(self, text: str) -> str:
        """
        Queue speech but skip playback. Only generate the WAV and return its path.
        This is for API-based use like /respond.
        """
        import tempfile
        import subprocess

        if not text.strip():
            raise ValueError("TTS input text is empty.")

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_f:
            tmp_path = tmp_f.name

        process = await asyncio.create_subprocess_exec(
            self.settings.PIPER_PATH,
            "--model", self.settings.PIPER_VOICE_MODEL,
            "--output_file", tmp_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate(input=text.encode("utf-8"))

        if process.returncode != 0:
            raise RuntimeError(f"Piper error: {stderr.decode().strip()}")

        return tmp_path
