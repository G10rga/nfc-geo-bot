from __future__ import annotations

from dataclasses import dataclass

import requests

PLACES_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
    ]
)


@dataclass(frozen=True)
class PlaceResult:
    place_id: str
    name_on_maps: str
    verified_location: str
    phone: str
    website: str


class PlacesClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.session = requests.Session()

    def lookup(self, name: str, location: str = "") -> PlaceResult | None:
        query = " ".join(part for part in [name.strip(), location.strip()] if part)
        if not query:
            raise ValueError("Business name is required")

        response = self.session.post(
            PLACES_SEARCH_URL,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": FIELD_MASK,
            },
            json={"textQuery": query, "languageCode": "en"},
            timeout=30,
        )
        if not response.ok:
            detail = response.text[:500]
            raise RuntimeError(
                f"Places API error {response.status_code}: {detail}"
            )

        places = response.json().get("places") or []
        if not places:
            return None

        place = places[0]
        display = place.get("displayName") or {}
        phone = (
            place.get("nationalPhoneNumber")
            or place.get("internationalPhoneNumber")
            or ""
        )
        return PlaceResult(
            place_id=place.get("id", ""),
            name_on_maps=display.get("text", ""),
            verified_location=place.get("formattedAddress", ""),
            phone=phone,
            website=place.get("websiteUri", ""),
        )
