import regex # Using 'regex' for more complete Unicode emoji support
import logging
from typing import Optional, List
import os

logger = logging.getLogger(__name__)

def remove_emojis(text: str) -> str:
    if not text:
        return ""
    emoji_pattern = regex.compile(
        r'[\p{Emoji_Presentation}\p{Emoji}\p{Extended_Pictographic}]',
        flags=regex.UNICODE
    )
    return emoji_pattern.sub(r'', text)

def should_respond_to_penny_mention(message: str) -> bool:
    lowered = message.lower()
    return (
        "penny" in lowered and (
            "?" in lowered or
            "can" in lowered or
            "do you" in lowered or
            "think" in lowered or
            "hey" in lowered or
            lowered.startswith("penny")
        )
    )