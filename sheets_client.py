from __future__ import annotations

from pathlib import Path
from typing import Any

import gspread

from maps_client import NO_PHONE

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Matches your NFC Geo sheet layout (+ Phone)
HEADERS = [
    "Name",
    "Location",
    "Sold",
    "Name on Maps",
    "Verified Location",
    "Phone",
]


def _phone_for_sheet(phone: str) -> str:
    text = (phone or "").strip()
    if not text or text.casefold() in {"(none)", "none", "n/a", "na"}:
        return NO_PHONE
    return text


class SheetsClient:
    def __init__(
        self,
        oauth_credentials_file: Path,
        oauth_token_file: Path,
        sheet_id: str,
        tab_name: str,
    ) -> None:
        # First run opens a browser to sign in with your Google account.
        # Later runs reuse token.json automatically.
        self.gc = gspread.oauth(
            credentials_filename=str(oauth_credentials_file),
            authorized_user_filename=str(oauth_token_file),
            scopes=SCOPES,
        )
        self.spreadsheet = self.gc.open_by_key(sheet_id)
        self.worksheet = self._open_or_create_tab(tab_name)
        self._ensure_headers()

    def _open_or_create_tab(self, tab_name: str) -> gspread.Worksheet:
        try:
            return self.spreadsheet.worksheet(tab_name)
        except gspread.WorksheetNotFound:
            return self.spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=10)

    def _ensure_headers(self) -> None:
        existing = self.worksheet.row_values(1)
        if not existing:
            self.worksheet.update("A1:F1", [HEADERS])
            return

        # Add Phone column if the sheet only has A–E from manual use
        if len(existing) < 6 or existing[5].strip().lower() != "phone":
            self.worksheet.update_cell(1, 6, "Phone")

    def append_business(
        self,
        name: str,
        location: str,
        name_on_maps: str,
        verified_location: str,
        phone: str,
        sold: str = "",
    ) -> int:
        row = [
            name,
            location,
            sold,
            name_on_maps,
            verified_location,
            _phone_for_sheet(phone),
        ]
        self.worksheet.append_row(row, value_input_option="USER_ENTERED")
        return len(self.worksheet.get_all_values())

    def rows_needing_enrichment(
        self, *, fix_locations: bool = False
    ) -> list[dict[str, Any]]:
        """Rows missing Name on Maps, or needing phone placeholder / district fix."""
        from location_utils import has_district

        records = self.worksheet.get_all_records()
        pending: list[dict[str, Any]] = []
        for idx, record in enumerate(records, start=2):  # row 1 = headers
            name = str(record.get("Name") or "").strip()
            if not name:
                continue
            maps_name = str(record.get("Name on Maps") or "").strip()
            phone = str(record.get("Phone") or "").strip()
            verified = str(record.get("Verified Location") or "").strip()
            location = str(record.get("Location") or "").strip()

            needs_maps = not maps_name
            needs_phone_placeholder = bool(maps_name) and not phone
            needs_location = fix_locations and not has_district(location)
            if not needs_maps and not needs_phone_placeholder and not needs_location:
                continue

            pending.append(
                {
                    "row": idx,
                    "name": name,
                    "location": location,
                    "sold": str(record.get("Sold") or "").strip(),
                    "name_on_maps": maps_name,
                    "verified_location": verified,
                    "phone": phone,
                    "needs_maps": needs_maps,
                    "needs_phone_placeholder": needs_phone_placeholder,
                    "needs_location": needs_location,
                }
            )
        return pending

    def update_phone_placeholder(self, row: int) -> None:
        self.worksheet.update_cell(row, 6, NO_PHONE)

    def update_enrichment(
        self,
        row: int,
        general_location: str,
        name_on_maps: str,
        verified_location: str,
        phone: str,
    ) -> None:
        # Keep existing values when a re-scrape returns blanks.
        existing = self.worksheet.row_values(row)
        while len(existing) < 6:
            existing.append("")

        def prefer(new: str, old: str) -> str:
            return new.strip() or old.strip()

        location = prefer(general_location, existing[1] if len(existing) > 1 else "")
        maps_name = prefer(name_on_maps, existing[3] if len(existing) > 3 else "")
        verified = prefer(verified_location, existing[4] if len(existing) > 4 else "")
        old_phone = existing[5] if len(existing) > 5 else ""
        phone_val = _phone_for_sheet(prefer(phone, old_phone))

        # B=Location, D=Name on Maps, E=Verified Location, F=Phone
        self.worksheet.update(
            f"B{row}",
            [[location]],
            value_input_option="USER_ENTERED",
        )
        self.worksheet.update(
            f"D{row}:F{row}",
            [[maps_name, verified, phone_val]],
            value_input_option="USER_ENTERED",
        )
