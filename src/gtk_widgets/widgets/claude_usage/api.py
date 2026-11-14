"""Requests to Claude's API with Claude Code's login (stdlib)."""

import http.client
import json
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

from gtk_widgets.lib.parse import ParseError
from gtk_widgets.widgets.claude_usage.parse import parse_token
from gtk_widgets.widgets.claude_usage.usage import UsageError

CREDENTIALS = Path.home() / ".claude" / ".credentials.json"
OAUTH_BETA = "oauth-2025-04-20"


def load_token() -> str | UsageError:
    """The OAuth access token from Claude Code's credentials."""
    try:
        data: object = json.loads(CREDENTIALS.read_text())
    except OSError as e:
        return UsageError(f"credentials: {e}")
    except ValueError as e:
        return UsageError(str(e))
    match parse_token(data):
        case ParseError() as e:
            return UsageError(f"credentials: {e}")
        case token:
            return token


def oauth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "anthropic-beta": OAUTH_BETA}


def get[T](
    path: str,
    headers: dict[str, str],
    parse: Callable[[object], T | ParseError],
    timeout: float = 10,
) -> T | UsageError:
    """GET an API path and parse its JSON answer."""
    try:
        with urllib.request.urlopen(
            urllib.request.Request(f"https://api.anthropic.com{path}", headers=headers),
            timeout=timeout,
        ) as resp:
            data: object = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return UsageError(f"HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        return UsageError(f"network error: {e.reason}")
    except (OSError, ValueError, http.client.HTTPException) as e:
        return UsageError(str(e))
    match parse(data):
        case ParseError() as e:
            return UsageError(str(e))
        case parsed:
            return parsed
