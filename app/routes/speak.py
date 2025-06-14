import os
import logging
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import FileResponse

from app.core.event_bus import EventBus
from app.services.transcribe_service import TranscribeService
from app.services.streaming_openai_service import StreamingOpenAIService
from app.services.context_manager import ContextManager
from app.services.tts_service import TTSService
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# Initialize the EventBus singleton
event_bus = EventBus.get_instance()

# Instantiate services correctly
context_manager = ContextManager(max_history=5)
transcribe_service = TranscribeService(event_bus, context_manager)
llm_service = StreamingOpenAIService(event_bus, context_manager)
tts_service = TTSService(event_bus, settings)

@router.post("/respond")
async def respond(audio: UploadFile = File(...)):
    logger.info("[/respond] Received audio file for response")

    # Save audio file
    temp_path = f"/tmp/{audio.filename}"
    with open(temp_path, "wb") as f:
        f.write(await audio.read())

    # Transcribe to text
    with open(temp_path, "rb") as f:
        audio_bytes = f.read()
    text = await transcribe_service.transcribe_and_publish(audio_bytes, source=temp_path)

    # Use ContextManager to build prompt
    prompt = context_manager.build_prompt_from_transcription(text)

    # Query the LLM
    reply = await llm_service.get_response(prompt)
    if not reply or not reply.strip():
        return {"error": "LLM did not generate a valid reply."}

    # Speak to file
    output_path = tts_service.speak_to_file(reply)    

    return FileResponse(output_path, media_type="audio/wav")
