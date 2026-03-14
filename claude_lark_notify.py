#!/usr/bin/env python3
"""Claude Code → Lark (飞书) notification hook.

Zero external dependencies — uses only Python stdlib.
Reads Claude Code hook event from stdin, sends a rich interactive card
to the configured Lark user via Bot API.

Usage:
    Configured as a Claude Code hook in ~/.claude/settings.json.
    Receives JSON on stdin from Claude Code Stop / Notification events.

Config:
    ~/.config/claude-lark/config.json
    {
        "app_id": "cli_xxx",
        "app_secret": "xxx",
        "open_id": "ou_xxx",
        "events": ["Stop", "Notification"]
    }
"""

from __future__ import annotations

import json
import platform
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".config" / "claude-lark"
CONFIG_PATH = CONFIG_DIR / "config.json"
TOKEN_CACHE_PATH = CONFIG_DIR / ".token_cache"

# ── Lark API ─────────────────────────────────────────────────────────
LARK_TOKEN_URL = (
    "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/"
)
LARK_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"

# ── Constants ────────────────────────────────────────────────────────
HTTP_TIMEOUT = 10
TOKEN_REFRESH_BUFFER = 300  # refresh 5 min before expiry
DEFAULT_EVENTS = ["Stop", "Notification"]


# ── Config & stdin ───────────────────────────────────────────────────


def _load_config() -> dict | None:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        if not all(cfg.get(k) for k in ("app_id", "app_secret", "open_id")):
            return None
        return cfg
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return None


def _read_stdin() -> dict:
    try:
        if sys.stdin.isatty():
            return {}
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, IOError):
        return {}


# ── Token management ────────────────────────────────────────────────


def _get_cached_token() -> str | None:
    try:
        with open(TOKEN_CACHE_PATH, "r") as f:
            cache = json.load(f)
        if cache.get("expires_at", 0) > time.time() + TOKEN_REFRESH_BUFFER:
            return cache.get("token")
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return None


def _save_token_cache(token: str, expires_in: int) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_CACHE_PATH, "w") as f:
            json.dump({"token": token, "expires_at": time.time() + expires_in}, f)
    except OSError:
        pass


def _fetch_tenant_token(app_id: str, app_secret: str) -> str | None:
    payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(
        LARK_TOKEN_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data = json.loads(resp.read())
        if data.get("code") != 0:
            return None
        token = data.get("tenant_access_token", "")
        if token:
            _save_token_cache(token, data.get("expire", 7200))
        return token or None
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return None


def get_token(app_id: str, app_secret: str) -> str | None:
    return _get_cached_token() or _fetch_tenant_token(app_id, app_secret)


# ── Helpers ──────────────────────────────────────────────────────────


def _now_str() -> str:
    cn = datetime.now(timezone.utc) + timedelta(hours=8)
    return cn.strftime("%Y-%m-%d %H:%M:%S")


def _project_name(cwd: str) -> str:
    return cwd.rsplit("/", 1)[-1] if cwd else "unknown"


def _hostname() -> str:
    return platform.node().split(".")[0] or "unknown"


def _truncate(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    # Collapse to first meaningful chunk
    text = text.strip()
    return text[:max_len] + "..." if len(text) > max_len else text


# ── Card builders ────────────────────────────────────────────────────


def _build_stop_card(event: dict) -> dict:
    """Rich card for Stop events — task completion."""
    cwd = event.get("cwd", "")
    project = _project_name(cwd)
    session_id = event.get("session_id", "")
    last_msg = event.get("last_assistant_message", "")
    host = _hostname()
    now = _now_str()

    # ── Elements ──
    elements: list[dict] = []

    # Row 1: project + host (two columns)
    elements.append(
        {
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "top",
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"📁 **项目**\n{project}",
                        }
                    ],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "top",
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": f"💻 **设备**\n{host}",
                        }
                    ],
                },
            ],
        }
    )

    # Divider
    elements.append({"tag": "hr"})

    # Last message
    if last_msg:
        snippet = _truncate(last_msg, 500)
        elements.append(
            {
                "tag": "markdown",
                "content": f"💬 **Claude 的回复**\n{snippet}",
            }
        )
        elements.append({"tag": "hr"})

    # Footer: directory + session + time
    footer_parts = []
    if cwd:
        footer_parts.append(f"📂 {cwd}")
    if session_id:
        footer_parts.append(f"🔑 {session_id[:12]}")
    footer_parts.append(f"🕐 {now}")

    elements.append(
        {
            "tag": "note",
            "elements": [
                {"tag": "plain_text", "content": "  |  ".join(footer_parts)}
            ],
        }
    )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": "✅ Claude Code 任务完成"},
            "template": "turquoise",
        },
        "elements": elements,
    }


def _build_notification_card(event: dict) -> dict:
    """Rich card for Notification events — needs attention."""
    cwd = event.get("cwd", "")
    project = _project_name(cwd)
    message = event.get("message", "")
    title_text = event.get("title", "")
    notif_type = event.get("notification_type", "")
    host = _hostname()
    now = _now_str()

    # Header style by notification type
    header_map = {
        "permission_prompt": ("⚠️ Claude Code 需要你的确认", "orange"),
        "idle_prompt": ("⏳ Claude Code 等待输入", "yellow"),
        "auth_success": ("✅ Claude Code 认证成功", "green"),
        "elicitation_dialog": ("📝 Claude Code 需要信息", "blue"),
    }
    header_title, header_color = header_map.get(
        notif_type, ("🔔 Claude Code 通知", "blue")
    )

    elements: list[dict] = []

    # Row 1: project + host
    elements.append(
        {
            "tag": "column_set",
            "flex_mode": "none",
            "background_style": "default",
            "columns": [
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "top",
                    "elements": [
                        {"tag": "markdown", "content": f"📁 **项目**\n{project}"}
                    ],
                },
                {
                    "tag": "column",
                    "width": "weighted",
                    "weight": 1,
                    "vertical_align": "top",
                    "elements": [
                        {"tag": "markdown", "content": f"💻 **设备**\n{host}"}
                    ],
                },
            ],
        }
    )

    elements.append({"tag": "hr"})

    # Title (if present)
    if title_text:
        elements.append({"tag": "markdown", "content": f"**{title_text}**"})

    # Message content
    if message:
        elements.append(
            {"tag": "markdown", "content": f"💬 {_truncate(message, 500)}"}
        )

    elements.append({"tag": "hr"})

    # Footer
    footer_parts = []
    if cwd:
        footer_parts.append(f"📂 {cwd}")
    footer_parts.append(f"🕐 {now}")

    elements.append(
        {
            "tag": "note",
            "elements": [
                {"tag": "plain_text", "content": "  |  ".join(footer_parts)}
            ],
        }
    )

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": header_title},
            "template": header_color,
        },
        "elements": elements,
    }


# ── Send ─────────────────────────────────────────────────────────────


def send_card(token: str, open_id: str, card: dict) -> bool:
    payload = json.dumps(
        {
            "receive_id": open_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        },
        ensure_ascii=False,
    ).encode("utf-8")

    req = urllib.request.Request(
        f"{LARK_MESSAGE_URL}?receive_id_type=open_id",
        data=payload,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return json.loads(resp.read()).get("code") == 0
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return False


# ── Main ─────────────────────────────────────────────────────────────


def main() -> None:
    config = _load_config()
    if not config:
        return

    event = _read_stdin()
    if not event:
        return

    # Event filtering
    event_name = event.get("hook_event_name", "")
    allowed = config.get("events", DEFAULT_EVENTS)
    if event_name and event_name not in allowed:
        return

    # Build card
    if event_name == "Stop":
        card = _build_stop_card(event)
    elif event_name == "Notification":
        card = _build_notification_card(event)
    else:
        card = _build_notification_card(event)

    # Send
    token = get_token(config["app_id"], config["app_secret"])
    if token:
        send_card(token, config["open_id"], card)


if __name__ == "__main__":
    main()
