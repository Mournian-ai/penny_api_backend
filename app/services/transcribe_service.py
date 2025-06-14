import logging, aiohttp
from tempfile import NamedTemporaryFile
from faster_whisper import WhisperModel

from app.core.event_bus import EventBus
from app.core.config import settings
from app.core.events import TranscriptionAvailableEvent, AIQueryEvent
from app.services.context_manager import ContextManager

logger = logging.getLogger(__name__)

def is_valid_transcription(text: str) -> bool:
    cleaned = text.strip().replace(" ", "")
    return bool(cleaned and cleaned not in {".", "..", "...", ". . .", "…"})

class TranscribeService:
    def __init__(self, event_bus: EventBus, context_manager: ContextManager, model_path: str = "base"):
        self.event_bus = event_bus
        self.context_manager = context_manager
        self.model = WhisperModel(model_path, compute_type="auto")
        self.transcribe_url = settings.FASTAPI_URL_TRANSCRIBE
        logger.info("Whisper model loaded.")

    async def transcribe_and_publish(self, audio_bytes: bytes, source: str = "unknown") -> str:
        with NamedTemporaryFile(suffix=".wav", delete=True) as tmp:
            tmp.write(audio_bytes)
            tmp.flush()

            logger.info(f"Transcribing audio from {source} ({len(audio_bytes)} bytes)...")
            segments, _ = self.model.transcribe(tmp.name)
            full_text = "".join([s.text for s in segments]).strip()

            logger.info(f"Transcription result: '{full_text}'")

            if is_valid_transcription(full_text):
                await self.event_bus.publish(TranscriptionAvailableEvent(
                    text=full_text,
                    is_final=True,
                    audio_path=source
                ))

                # Create contextualized prompt
                prompt = self.context_manager.build_prompt_from_transcription(full_text)

                await self.event_bus.publish(AIQueryEvent(
                    instruction="process_transcription",
                    input_text=prompt
                ))

            return full_text
        
    async def transcribe_file(self, file_path: str) -> str:
        async with aiohttp.ClientSession() as session:
            with open(file_path, 'rb') as f:
                form = aiohttp.FormData()
                form.add_field("file", f, filename="audio.wav", content_type="audio/wav")
                async with session.post(self.transcribe_url, data=form) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        return result.get("text", "")
                    else:
                        logging.error(f"Transcription failed: {resp.status}")
                        return ""