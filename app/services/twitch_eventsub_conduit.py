import asyncio
import websockets
import json
import aiohttp
from app.services.websocket_manager import WebSocketManager
from app.core.config import settings  # Your .env loader


class TwitchEventSubConduit:
    def __init__(self, ws_manager: WebSocketManager):
        self.ws_manager = ws_manager
        self.session_id = None
        self.twitch_ws_url = "wss://eventsub.wss.twitch.tv/ws"
        self.connected = False

        async def connect(self):
            print("[TwitchEventSub] Connecting to Twitch WebSocket Conduit...")
            try:
                async with websockets.connect(self.twitch_ws_url) as ws:
                    self.connected = True
                    while self.connected:
                        raw_data = await ws.recv()

                        if isinstance(raw_data, memoryview):
                            message = raw_data.tobytes().decode("utf-8")
                        elif isinstance(raw_data, (bytes, bytearray)):
                            message = raw_data.decode("utf-8")
                        else:
                            message = str(raw_data)

                        await self.handle_message(message)

            except Exception as e:
                print(f"[TwitchEventSub] Connection error: {e}")
                self.connected = False


    async def handle_message(self, message: str):
        try:
            data = json.loads(message)
            metadata = data.get("metadata", {})
            msg_type = metadata.get("message_type")
            payload = data.get("payload", {})

            if msg_type == "session_welcome":
                self.session_id = payload["session"]["id"]
                print(f"[TwitchEventSub] Connected! Session ID: {self.session_id}")
                await self.subscribe_to_events(self.session_id)

            elif msg_type == "notification":
                event = payload.get("event", {})
                await self.route_event(event)

            elif msg_type == "session_keepalive":
                print("[TwitchEventSub] Keepalive received.")

        except Exception as e:
            print(f"[TwitchEventSub] Error handling message: {e}")

    async def subscribe_to_events(self, session_id: str):
        headers = {
            "Authorization": f"Bearer {settings.TWITCH_APP_ACCESS_TOKEN}",
            "Client-Id": settings.TWITCH_CLIENT_ID,
            "Content-Type": "application/json"
        }

        base = {
            "transport": {
                "method": "websocket",
                "session_id": session_id
            }
        }

        event_types = [
            {"type": "channel.subscribe"},
            {"type": "channel.raid"},
            {"type": "channel.follow"},
            {"type": "channel.cheer"},
            {"type": "channel.subscription.gift"}
        ]

        async with aiohttp.ClientSession() as session:
            for event in event_types:
                payload = {
                    **event,
                    "version": "1",
                    "condition": {
                        "broadcaster_user_id": settings.TWITCH_BROADCASTER_ID
                    },
                    **base
                }
                async with session.post(
                    "https://api.twitch.tv/helix/eventsub/subscriptions",
                    headers=headers,
                    json=payload
                ) as resp:
                    if resp.status == 202:
                        print(f"[TwitchEventSub] Subscribed to {event['type']}")
                    else:
                        error = await resp.text()
                        print(f"[TwitchEventSub] Subscription failed for {event['type']}: {error}")

    async def route_event(self, event: dict):
        print(f"[TwitchEventSub] Event received: {event}")
        await self.ws_manager.broadcast(json.dumps({
            "type": event.get("type"),
            "user": event.get("user_name", "unknown"),
            "viewer_count": event.get("viewer_count", None),
            "tier": event.get("tier", None),
            "bits": event.get("bits", None),
            "gifter": event.get("gifter_user_name", None),
            "count": event.get("total", None)
        }))
