from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote_plus, unquote

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from location_utils import format_general_location

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

NO_PHONE = "no number stated"


@dataclass(frozen=True)
class PlaceResult:
    name_on_maps: str
    verified_location: str
    general_location: str
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
                link_name = self._open_first_result_if_needed(page)
                self._wait_until_place_loaded(page)
                result = self._extract_place(
                    page,
                    city_hint=location,
                    fallback_name=link_name or name.strip(),
                )
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

    def _open_first_result_if_needed(self, page) -> str:
        """Open first result if needed; return a name hint from the clicked link."""
        if self._is_on_place_page(page):
            title = self._read_place_name(page)
            if title and not self._is_results_title(title):
                return title

        candidates = [
            'div[role="feed"] a[href*="/maps/place/"]',
            'a[href*="/maps/place/"]',
        ]
        link_name = ""
        clicked = False
        for selector in candidates:
            link = page.locator(selector).first
            try:
                if link.is_visible(timeout=4000):
                    link_name = self._name_from_result_link(link)
                    link.click(timeout=5000)
                    clicked = True
                    break
            except PlaywrightTimeout:
                continue
            except Exception:  # noqa: BLE001
                continue

        if not clicked:
            return link_name

        try:
            page.wait_for_url(re.compile(r".*/maps/place/.*"), timeout=self.timeout_ms)
        except PlaywrightTimeout:
            pass
        page.wait_for_timeout(1800)
        return link_name

    def _wait_until_place_loaded(self, page) -> None:
        try:
            page.wait_for_selector(
                'button[data-item-id="address"], '
                'button[data-item-id^="phone:"], '
                'a[data-item-id="authority"], '
                "h1",
                timeout=self.timeout_ms,
            )
            page.wait_for_timeout(800)
        except PlaywrightTimeout:
            page.wait_for_timeout(1000)

    def _read_place_name(self, page) -> str:
        # Prefer real place headings; skip the Results list title.
        try:
            headings = page.locator("h1")
            count = headings.count()
            for i in range(count):
                text = headings.nth(i).inner_text(timeout=2000).strip()
                if text and not self._is_results_title(text):
                    return text
        except Exception:  # noqa: BLE001
            pass
        return ""

    @staticmethod
    def _is_results_title(title: str) -> bool:
        return title.strip().casefold() in _RESULTS_TITLES

    @staticmethod
    def _name_from_result_link(link) -> str:
        try:
            aria = (link.get_attribute("aria-label") or "").strip()
            if aria:
                # Often "Place Name, Category, 4.5 stars, ..."
                return aria.split(",")[0].strip()
            text = link.inner_text().strip()
            if text:
                return text.split("\n")[0].strip()
        except Exception:  # noqa: BLE001
            return ""
        return ""

    @staticmethod
    def _name_from_url(url: str) -> str:
        match = re.search(r"/maps/place/([^/@]+)", url)
        if not match:
            return ""
        raw = unquote(match.group(1)).replace("+", " ").strip()
        # Drop trailing noise like data ids if any slipped in.
        raw = raw.split("?")[0].strip()
        if not raw or raw.casefold() in _RESULTS_TITLES:
            return ""
        return raw

    @staticmethod
    def _name_from_document_title(page) -> str:
        try:
            title = (page.title() or "").strip()
        except Exception:  # noqa: BLE001
            return ""
        for suffix in (" - Google Maps", " – Google Maps", " | Google Maps"):
            if suffix in title:
                name = title.split(suffix)[0].strip()
                if name and name.casefold() not in _RESULTS_TITLES:
                    return name
        return ""

    def _extract_place(
        self,
        page,
        city_hint: str = "",
        fallback_name: str = "",
    ) -> PlaceResult:
        name = self._read_place_name(page)
        if not name:
            name = self._name_from_document_title(page)
        if not name:
            name = self._name_from_url(page.url)
        if not name and fallback_name and not self._is_results_title(fallback_name):
            name = fallback_name.strip()

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
        phone = self._normalize_phone(phone) or NO_PHONE

        website = ""
        try:
            link = page.locator('a[data-item-id="authority"]').first
            if link.count():
                website = (link.get_attribute("href") or "").strip()
        except Exception:  # noqa: BLE001
            website = ""

        if self._is_results_title(name):
            name = ""

        page_text = self._sidebar_text(page)
        general = format_general_location(
            city_hint=city_hint,
            address=address,
            page_text=page_text,
        )

        return PlaceResult(
            name_on_maps=name,
            verified_location=address,
            general_location=general,
            phone=phone,
            website=website,
        )

    def _sidebar_text(self, page) -> str:
        """Grab visible place-panel text so district names can be detected."""
        selectors = [
            'div[role="main"]',
            'button[data-item-id="address"]',
        ]
        chunks: list[str] = []
        for selector in selectors:
            try:
                loc = page.locator(selector).first
                if loc.count():
                    chunks.append(loc.inner_text(timeout=2000))
            except Exception:  # noqa: BLE001
                continue
        return "\n".join(chunks)

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
