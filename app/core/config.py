from pydantic_settings import BaseSettings
from dotenv import load_dotenv
import os
import json

load_dotenv()

class AppConfig(BaseSettings):
    TWITCH_CLIENT_ID: str = ""
    TWITCH_CLIENT_SECRET: str = ""
    TWITCH_APP_ACCESS_TOKEN: str = ""
    TWITCH_CHAT_REFRESH_TOKEN: str = ""
    TWITCH_BROADCASTER_ID: str = ""
    TWITCH_NICKNAME: str = ""

    OPENAI_API_KEY: str = ""

    PIPER_TTS_CMD: str = "piper --model default.onnx --output_file out.wav"
    WHISPER_MODEL: str = "base"
    EVENTSUB_SECRET: str = ""

    class Config:
        env_file = ".env"

    def get_dynamic_model_name(self) -> str:
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f).get("openai_model", "gpt-4o")
        except Exception:
            return "gpt-4o"

settings: AppConfig = AppConfig()
