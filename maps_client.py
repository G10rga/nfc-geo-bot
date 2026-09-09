from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class PlaceResult:
    name_on_maps: str
    verified_location: str
    phone: str
    website: str


class MapsClient:
    """Look up a business on Google Maps via a real browser (no Places API)."""

    def __init__(self, headless: bool = True, timeout_ms: int = 25000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms

    def lookup(self, name: str, location: str = "") -> PlaceResult | None:
        query = " ".join(part for part in [name.strip(), location.strip()] if part)
        if not query:
            raise ValueError("Business name is required")

        url = f"https://www.google.com/maps/search/{quote_plus(query)}"

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context = browser.new_context(
                locale="en-US",
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                page.goto(url, wait_until="domcontentloaded")
                self._dismiss_consent(page)
                self._wait_for_place_or_results(page)
                self._open_first_result_if_needed(page)
                result = self._extract_place(page)
            finally:
                browser.close()

        if not result.name_on_maps and not result.verified_location:
            return None
        return result

    def _dismiss_consent(self, page) -> None:
        # Cookie / consent dialogs vary by region.
        candidates = [
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            'button:has-text("Reject all")',
            'form[action*="consent"] button',
        ]
        for selector in candidates:
            try:
                btn = page.locator(selector).first
                if btn.is_visible(timeout=1500):
                    btn.click(timeout=2000)
                    page.wait_for_timeout(800)
                    return
            except PlaywrightTimeout:
                continue
            except Exception:  # noqa: BLE001
                continue

    def _wait_for_place_or_results(self, page) -> None:
        try:
            page.wait_for_selector(
                'h1, div[role="feed"], a[href*="/maps/place/"]',
                timeout=self.timeout_ms,
            )
        except PlaywrightTimeout as exc:
            raise RuntimeError(
                "Google Maps did not load results (blocked, captcha, or slow network)."
            ) from exc

    def _open_first_result_if_needed(self, page) -> None:
        # Already on a place page (single match).
        if page.locator("h1").count() and page.locator(
            'button[data-item-id="address"], button[data-item-id^="phone:"]'
        ).count():
            return

        # Results list → open first place.
        first = page.locator('a[href*="/maps/place/"]').first
        try:
            if first.is_visible(timeout=3000):
                first.click()
                page.wait_for_selector("h1", timeout=self.timeout_ms)
                page.wait_for_timeout(1200)
        except PlaywrightTimeout:
            return

    def _extract_place(self, page) -> PlaceResult:
        name = ""
        try:
            name = page.locator("h1").first.inner_text(timeout=5000).strip()
        except PlaywrightTimeout:
            name = ""

        address = self._aria_or_text(
            page,
            [
                'button[data-item-id="address"]',
                'button[data-tooltip="Copy address"]',
            ],
        )
        phone = self._aria_or_text(
            page,
            [
                'button[data-item-id^="phone:"]',
                'button[data-tooltip="Copy phone number"]',
            ],
        )
        phone = self._normalize_phone(phone)

        website = ""
        try:
            link = page.locator('a[data-item-id="authority"]').first
            if link.count():
                website = (link.get_attribute("href") or "").strip()
        except Exception:  # noqa: BLE001
            website = ""

        return PlaceResult(
            name_on_maps=name,
            verified_location=address,
            phone=phone,
            website=website,
        )

    def _aria_or_text(self, page, selectors: list[str]) -> str:
        for selector in selectors:
            loc = page.locator(selector).first
            try:
                if not loc.count():
                    continue
                label = (loc.get_attribute("aria-label") or "").strip()
                if label:
                    # e.g. "Address: 49 Simon Kandelaki Street..."
                    # e.g. "Phone: 032 2 00 00 00"
                    parts = label.split(":", 1)
                    return parts[1].strip() if len(parts) > 1 else label
                text = loc.inner_text().strip()
                if text:
                    return text
            except Exception:  # noqa: BLE001
                continue
        return ""

    @staticmethod
    def _normalize_phone(raw: str) -> str:
        if not raw:
            return ""
        # Keep digits and common phone punctuation.
        cleaned = re.sub(r"[^\d+\-\s().]", "", raw).strip()
        return cleaned or raw.strip()
