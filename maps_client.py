from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

# Sidebar title when Maps shows a list, not a single place (any language).
_RESULTS_TITLES = {
    "results",
    "შედეგები",
    "resultados",
    "résultats",
    "ergebnisse",
    "risultati",
    "результаты",
}


@dataclass(frozen=True)
class PlaceResult:
    name_on_maps: str
    verified_location: str
    phone: str
    website: str


class MapsClient:
    """Look up a business on Google Maps via a real browser (no Places API)."""

    def __init__(self, headless: bool = True, timeout_ms: int = 35000) -> None:
        self.headless = headless
        self.timeout_ms = timeout_ms

    def lookup(self, name: str, location: str = "") -> PlaceResult | None:
        query = " ".join(part for part in [name.strip(), location.strip()] if part)
        if not query:
            raise ValueError("Business name is required")

        # hl=en keeps UI labels more stable; query can still be Georgian.
        url = (
            "https://www.google.com/maps/search/"
            f"{quote_plus(query)}?hl=en"
        )

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
                self._wait_until_place_loaded(page)
                result = self._extract_place(page)
            finally:
                browser.close()

        if self._is_results_title(result.name_on_maps) and not result.verified_location:
            return None
        if not result.name_on_maps and not result.verified_location:
            return None
        return result

    def _dismiss_consent(self, page) -> None:
        candidates = [
            'button:has-text("Accept all")',
            'button:has-text("I agree")',
            'button:has-text("Reject all")',
            'button:has-text("Accept")',
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
                'div[role="feed"], a[href*="/maps/place/"], '
                'button[data-item-id="address"], h1',
                timeout=self.timeout_ms,
            )
            page.wait_for_timeout(1500)
        except PlaywrightTimeout as exc:
            raise RuntimeError(
                "Google Maps did not load results (blocked, captcha, or slow network)."
            ) from exc

    def _is_on_place_page(self, page) -> bool:
        if "/maps/place/" in page.url:
            return True
        try:
            if page.locator('button[data-item-id="address"]').count():
                return True
            if page.locator('button[data-item-id^="phone:"]').count():
                return True
        except Exception:  # noqa: BLE001
            return False
        return False

    def _open_first_result_if_needed(self, page) -> None:
        if self._is_on_place_page(page):
            # Still might be a results h1 with no details yet — check title.
            title = self._read_h1(page)
            if title and not self._is_results_title(title):
                return

        # Prefer links inside the results feed (avoids map pins / unrelated links).
        candidates = [
            'div[role="feed"] a[href*="/maps/place/"]',
            'a[href*="/maps/place/"]',
        ]
        clicked = False
        for selector in candidates:
            link = page.locator(selector).first
            try:
                if link.is_visible(timeout=4000):
                    link.click(timeout=5000)
                    clicked = True
                    break
            except PlaywrightTimeout:
                continue
            except Exception:  # noqa: BLE001
                continue

        if not clicked:
            return

        try:
            page.wait_for_url(re.compile(r".*/maps/place/.*"), timeout=self.timeout_ms)
        except PlaywrightTimeout:
            pass
        page.wait_for_timeout(1500)

    def _wait_until_place_loaded(self, page) -> None:
        try:
            page.wait_for_selector(
                'button[data-item-id="address"], '
                'button[data-item-id^="phone:"], '
                'a[data-item-id="authority"]',
                timeout=self.timeout_ms,
            )
        except PlaywrightTimeout:
            # Place may have no phone/website; name-only is still useful.
            page.wait_for_timeout(1000)

    def _read_h1(self, page) -> str:
        try:
            return page.locator("h1").first.inner_text(timeout=4000).strip()
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _is_results_title(title: str) -> bool:
        return title.strip().casefold() in _RESULTS_TITLES

    def _extract_place(self, page) -> PlaceResult:
        name = self._read_h1(page)
        if self._is_results_title(name):
            # Sometimes the place name is the second heading.
            try:
                headings = page.locator("h1")
                if headings.count() > 1:
                    name = headings.nth(1).inner_text().strip()
            except Exception:  # noqa: BLE001
                name = ""

        address = self._aria_or_text(
            page,
            [
                'button[data-item-id="address"]',
                'button[data-tooltip="Copy address"]',
                'button[aria-label*="Address"]',
            ],
        )
        phone = self._aria_or_text(
            page,
            [
                'button[data-item-id^="phone:"]',
                'button[data-tooltip="Copy phone number"]',
                'button[aria-label*="Phone"]',
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

        if self._is_results_title(name):
            name = ""

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
        cleaned = re.sub(r"[^\d+\-\s().]", "", raw).strip()
        return cleaned or raw.strip()
