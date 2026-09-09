from __future__ import annotations

from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

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


class SheetsClient:
    def __init__(self, service_account_file: Path, sheet_id: str, tab_name: str) -> None:
        creds = Credentials.from_service_account_file(
            str(service_account_file), scopes=SCOPES
        )
        self.gc = gspread.authorize(creds)
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
        row = [name, location, sold, name_on_maps, verified_location, phone]
        self.worksheet.append_row(row, value_input_option="USER_ENTERED")
        return len(self.worksheet.get_all_values())

    def rows_needing_enrichment(self) -> list[dict[str, Any]]:
        """Rows with Name set but missing Name on Maps or Phone."""
        records = self.worksheet.get_all_records()
        pending: list[dict[str, Any]] = []
        for idx, record in enumerate(records, start=2):  # row 1 = headers
            name = str(record.get("Name") or "").strip()
            if not name:
                continue
            maps_name = str(record.get("Name on Maps") or "").strip()
            phone = str(record.get("Phone") or "").strip()
            if maps_name and phone:
                continue
            pending.append(
                {
                    "row": idx,
                    "name": name,
                    "location": str(record.get("Location") or "").strip(),
                    "sold": str(record.get("Sold") or "").strip(),
                    "name_on_maps": maps_name,
                    "verified_location": str(
                        record.get("Verified Location") or ""
                    ).strip(),
                    "phone": phone,
                }
            )
        return pending

    def update_enrichment(
        self,
        row: int,
        name_on_maps: str,
        verified_location: str,
        phone: str,
    ) -> None:
        # D=Name on Maps, E=Verified Location, F=Phone
        self.worksheet.update(
            f"D{row}:F{row}",
            [[name_on_maps, verified_location, phone]],
            value_input_option="USER_ENTERED",
        )
