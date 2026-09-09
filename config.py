from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    places_api_key: str
    sheet_id: str
    sheet_tab: str
    service_account_file: Path

    @classmethod
    def from_env(cls) -> Settings:
        places_key = os.getenv("GOOGLE_PLACES_API_KEY", "").strip()
        sheet_id = os.getenv("GOOGLE_SHEET_ID", "").strip()
        sheet_tab = os.getenv("GOOGLE_SHEET_TAB", "NFC Geo").strip() or "NFC Geo"
        sa_path = Path(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
        ).expanduser()
        if not sa_path.is_absolute():
            sa_path = ROOT / sa_path

        missing = []
        if not places_key or places_key.startswith("your_"):
            missing.append("GOOGLE_PLACES_API_KEY")
        if not sheet_id or sheet_id.startswith("your_"):
            missing.append("GOOGLE_SHEET_ID")
        if not sa_path.exists():
            missing.append(f"service account file at {sa_path}")

        if missing:
            raise SystemExit(
                "Missing config:\n  - "
                + "\n  - ".join(missing)
                + "\n\nCopy .env.example → .env and add service_account.json "
                "(see README)."
            )

        return cls(
            places_api_key=places_key,
            sheet_id=sheet_id,
            sheet_tab=sheet_tab,
            service_account_file=sa_path,
        )
