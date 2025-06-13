# app/services/interaction_service.py

import asyncio
import logging
import shlex
from typing import Optional

from app.core.config import settings, AppConfig
from app.core.event_bus import EventBus
from app.core.events import (
    AppShutdownEvent,
    UILogEvent,
    TwitchMessageEvent,
    SpeakRequestEvent,
    TwitchUserEvent,
    AIQueryEvent,
    SearchRequestEvent,
    SearchResultEvent
)
from app.services.api_client_service import APIClientService

logger = logging.getLogger(__name__)

class InteractionService:
    def __init__(self, event_bus: EventBus, api_client: APIClientService):
        self.event_bus = event_bus
        self.api_client = api_client
        self._bot_name = settings.TWITCH_NICKNAME.lower()
        self._command_prefix = getattr(settings, 'COMMAND_PREFIX', '!')

    async def start(self) -> None:
        logger.info("InteractionService starting...")
        self.event_bus.subscribe_async(TwitchMessageEvent, self.handle_twitch_message)
        self.event_bus.subscribe_async(TwitchUserEvent, self.handle_twitch_platform_event)
        self.event_bus.subscribe_async(SearchResultEvent, self.handle_search_result)
        self.event_bus.subscribe_async(AppShutdownEvent, self.handle_shutdown)
        logger.info("InteractionService started.")

    async def stop(self) -> None:
        logger.info("InteractionService stopping...")
        logger.info("InteractionService stopped.")

    async def handle_shutdown(self, event: AppShutdownEvent) -> None:
        await self.stop()

    async def handle_twitch_message(self, event: TwitchMessageEvent) -> None:
        logger.debug(f"[Interaction] {event.username}: {event.message}")
        message_content = event.message.strip()
        message_lower = message_content.lower()
        is_command = message_content.startswith(self._command_prefix)

        if is_command:
            try:
                parts = shlex.split(message_content)
                command = parts[0][len(self._command_prefix):].lower()
                args = parts[1:]
            except ValueError:
                logger.warning(f"Could not parse command: {message_content}")
                return

            if command in {"so", "shoutout"}:
                await self._handle_shoutout_command(args, event.username)
            elif command == "search":
                await self._handle_search_command(args, event.username)
            elif command in {"ask", "penny"}:
                await self._handle_ask_command(args, event.username)

        elif self._bot_name in message_lower or f"@{self._bot_name}" in message_lower:
            await self._handle_direct_mention(event.username, message_content)

    async def _handle_shoutout_command(self, args: list[str], sender: str) -> None:
        if args:
            target_username = args[0].lstrip('@')
            await self.event_bus.publish(UILogEvent(
                f"Shoutout command for {target_username} from {sender}.", level="INFO"
            ))
            speech_text = await self.api_client.get_api_shout_out_text(username=target_username)
            if speech_text:
                await self.event_bus.publish(SpeakRequestEvent(text=speech_text))
        else:
            help_text = f"To shout someone out, {sender}, please tell me their username, like !shoutout awesome_streamer."
            await self.event_bus.publish(SpeakRequestEvent(text=help_text))

    async def _handle_search_command(self, args: list[str], sender: str) -> None:
        if args:
            search_query = " ".join(args)
            await self.event_bus.publish(UILogEvent(
                f"Search command for '{search_query}' from {sender}.", level="INFO"
            ))
            await self.event_bus.publish(SearchRequestEvent(
                query=search_query,
                source="twitch_command",
                original_user=sender
            ))
        else:
            await self.event_bus.publish(SpeakRequestEvent(text=f"What should I search for, {sender}?"))

    async def _handle_ask_command(self, args: list[str], sender: str) -> None:
        if args:
            query_for_ai = " ".join(args)
            await self.event_bus.publish(AIQueryEvent(
                input_text=query_for_ai,
                instruction=f"User {sender} asked:"
            ))
        else:
            await self.event_bus.publish(SpeakRequestEvent(text=f"What would you like to ask, {sender}?"))

    async def _handle_direct_mention(self, username: str, message_content: str) -> None:
        await self.event_bus.publish(UILogEvent(
            f"Penny mentioned by {username}. Calling /respond_chat: {message_content}", level="INFO"
        ))
        speech_text = await self.api_client.get_api_chat_response_text(
            username=username,
            message_text=message_content
        )
        if speech_text:
            await self.event_bus.publish(SpeakRequestEvent(text=speech_text))

    async def handle_twitch_platform_event(self, event: TwitchUserEvent) -> None:
        logger.info(f"[Interaction] Platform Event: {event.event_type} from {event.username or 'N/A'}")
        speech_text = await self.api_client.get_api_event_reaction_text(
            event_type=event.event_type,
            username=event.username,
            details=event.details
        )
        if speech_text:
            await self.event_bus.publish(SpeakRequestEvent(text=speech_text))
        else:
            logger.warning(f"No speech text from /react_event API for {event.event_type} by {event.username}")

    async def handle_search_result(self, event: SearchResultEvent) -> None:
        if event.source != "twitch_command":
            return

        user = event.original_user or "someone"

        if event.error or not event.results:
            await self.event_bus.publish(SpeakRequestEvent(
                text=f"Sorry {user}, I couldn't find anything about {event.query}."
            ))
            return

        top_result = event.results[0]
        title = top_result.get('title', 'Unknown Title')
        snippet = top_result.get('snippet', 'No description available.')

        await self.event_bus.publish(AIQueryEvent(
            instruction=f"User '{user}' asked to search for '{event.query}'. The top result is '{title}'. Briefly summarize this snippet for them in your voice:",
            input_text=snippet
        ))
