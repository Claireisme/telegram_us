from __future__ import annotations

import json
import urllib.error
import urllib.request


class TelegramSendError(RuntimeError):
    """Raised when Telegram rejects a message."""


def send_message(bot_token: str, channel_id: str, text: str, dry_run: bool = True) -> dict:
    if dry_run:
        print(text)
        return {"ok": True, "dry_run": True}

    if not bot_token:
        raise TelegramSendError("Missing TELEGRAM_BOT_TOKEN")
    if not channel_id:
        raise TelegramSendError("Missing TELEGRAM_CHANNEL_ID")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise TelegramSendError(f"Telegram HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise TelegramSendError(f"Telegram network error: {exc}") from exc

    result = json.loads(body)
    if not result.get("ok"):
        raise TelegramSendError(f"Telegram rejected message: {result}")
    return result

