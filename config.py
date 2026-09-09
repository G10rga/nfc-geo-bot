from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


def _resolve_path(value: str, default_name: str) -> Path:
    raw = (value or default_name).strip()
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path


@dataclass(frozen=True)
class Settings:
    sheet_id: str
    sheet_tab: str
    oauth_credentials_file: Path
    oauth_token_file: Path
    headless: bool

    @classmethod
    def from_env(cls) -> Settings:
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        sheet_tab = os.getenv("GOOGLE_SHEET_TAB", "Sheet1").strip() or "Sheet1"
        oauth_credentials = _resolve_path(
            os.getenv("GOOGLE_OAUTH_CREDENTIALS_FILE", ""),
            "credentials.json",
        )
        oauth_token = _resolve_path(
            os.getenv("GOOGLE_OAUTH_TOKEN_FILE", ""),
            "token.json",
        )
        headless = os.getenv("MAPS_HEADLESS", "1").strip().lower() not in {
            "0",
            "false",
            "no",
        }

        missing = []
        if not sheet_id or sheet_id.startswith("your_"):
            missing.append("GOOGLE_SHEET_ID")
        if not oauth_credentials.exists():
            missing.append(
                f"OAuth client file at {oauth_credentials} "
                "(download Desktop credentials.json — see README)"
            )

        if missing:
            raise SystemExit(
                "Missing config:\n  - "
                + "\n  - ".join(missing)
                + "\n\nCopy .env.example → .env and follow README OAuth setup."
            )

        return cls(
            sheet_id=sheet_id,
            sheet_tab=sheet_tab,
            oauth_credentials_file=oauth_credentials,
            oauth_token_file=oauth_token,
            headless=headless,
        )
