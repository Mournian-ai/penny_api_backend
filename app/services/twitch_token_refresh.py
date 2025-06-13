# app/services/twitch_token_manager.py

import os
import logging
import aiohttp
import json
import time
import asyncio
from typing import Optional
from dotenv import load_dotenv, set_key
from app.core.config import settings

logger = logging.getLogger(__name__)
TWITCH_TOKEN_URL = "https://id.twitch.tv/oauth2/token"
SETTINGS_FILE = "settings.json"
THREE_HOURS = 3 * 60 * 60

class TwitchTokenManager:
    def __init__(self, env_path: str = ".env"):
        self.env_path = os.getenv("ENV_PATH", env_path)

    def _update_settings_json(self, updates: dict):
        try:
            data = {}
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            data.setdefault('tokens', {}).update(updates)

            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            logger.info(f"[TokenManager] Updated {SETTINGS_FILE}: {list(updates.keys())}")
        except Exception as e:
            logger.error(f"[TokenManager] Failed to update {SETTINGS_FILE}: {e}", exc_info=True)

    async def refresh_app_token(self) -> Optional[str]:
        payload = {
            "grant_type": "client_credentials",
            "client_id": settings.TWITCH_CLIENT_ID,
            "client_secret": settings.TWITCH_CLIENT_SECRET,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(TWITCH_TOKEN_URL, data=payload) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        token = data.get("access_token")
                        expires_in = data.get("expires_in")
                        if token:
                            expires_at = int(time.time()) + expires_in
                            settings.TWITCH_APP_ACCESS_TOKEN = token
                            if os.path.exists(self.env_path):
                                set_key(self.env_path, "TWITCH_APP_ACCESS_TOKEN", token)
                            self._update_settings_json({"TWITCH_APP_TOKEN_EXPIRES_AT": expires_at})
                            logger.info(f"[TokenManager] App token refreshed. Expires at {expires_at}")
                            return token
                    logger.error(f"[TokenManager] App token refresh failed: {data}")
        except Exception as e:
            logger.error(f"[TokenManager] App token exception: {e}", exc_info=True)
        return None

    async def refresh_chat_token(self) -> Optional[str]:
        return await self._refresh_token(
            refresh_token=settings.TWITCH_CHAT_REFRESH_TOKEN,
            access_token_key="TWITCH_CHAT_TOKEN",
            refresh_token_key="TWITCH_CHAT_REFRESH_TOKEN",
            expires_at_key="TWITCH_CHAT_TOKEN_EXPIRES_AT",
            context="Chat"
        )

    async def _refresh_token(
        self,
        refresh_token: str,
        access_token_key: str,
        refresh_token_key: str,
        expires_at_key: str,
        context: str
    ) -> Optional[str]:
        if not refresh_token:
            logger.error(f"[TokenManager] {context} refresh token is missing.")
            return None

        payload = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.TWITCH_CLIENT_ID,
            "client_secret": settings.TWITCH_CLIENT_SECRET,
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(TWITCH_TOKEN_URL, data=payload) as resp:
                    data = await resp.json()
                    if resp.status == 200:
                        access_token = data.get("access_token")
                        new_refresh_token = data.get("refresh_token")
                        expires_in = data.get("expires_in")
                        if access_token:
                            expires_at = int(time.time()) + expires_in
                            setattr(settings, access_token_key, access_token)
                            if os.path.exists(self.env_path):
                                set_key(self.env_path, access_token_key, access_token)
                                if new_refresh_token:
                                    setattr(settings, refresh_token_key, new_refresh_token)
                                    set_key(self.env_path, refresh_token_key, new_refresh_token)
                            self._update_settings_json({expires_at_key: expires_at})
                            logger.info(f"[TokenManager] {context} token refreshed. Expires at {expires_at}")
                            return access_token
                    logger.error(f"[TokenManager] {context} token refresh failed: {data}")
        except Exception as e:
            logger.error(f"[TokenManager] Exception refreshing {context} token: {e}", exc_info=True)

        return None
    
    THREE_HOURS = 3 * 60 * 60

    def _should_refresh(self, expires_at_key: str) -> bool:
        """Returns True if the token is expiring within 3 hours or missing."""
        try:
            if not os.path.exists(SETTINGS_FILE):
                return True
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            expires_at = data.get("tokens", {}).get(expires_at_key, 0)
            if not isinstance(expires_at, int):
                return True
            return (expires_at - time.time()) < self.THREE_HOURS
        except Exception as e:
            logger.error(f"[TokenManager] Failed checking expiry for {expires_at_key}: {e}")
            return True

    async def start_periodic_refresh_loop(self, interval_seconds: int = 1800):
        """Background loop to refresh tokens every X seconds if needed."""
        while True:
            try:
                if self._should_refresh("TWITCH_APP_TOKEN_EXPIRES_AT"):
                    await self.refresh_app_token()
                if self._should_refresh("TWITCH_CHAT_TOKEN_EXPIRES_AT"):
                    await self.refresh_chat_token()
            except Exception as e:
                logger.error(f"[TokenManager] Error during scheduled refresh: {e}", exc_info=True)
            await asyncio.sleep(interval_seconds)
