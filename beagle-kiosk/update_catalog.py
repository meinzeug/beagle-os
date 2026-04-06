#!/usr/bin/env python3
# Beagle OS Gaming Kiosk - (c) Dennis Wicht / meinzeug - MIT Licensed
"""Build the Beagle OS Gaming store catalog from official GFN data plus GMG search results."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

INSTALL_ROOT = Path(os.environ.get("BEAGLE_KIOSK_ROOT", "/opt/beagle-kiosk"))
GAMES_PATH = INSTALL_ROOT / "games.json"
COVER_CACHE_DIR = INSTALL_ROOT / "assets" / "covers"

REQUEST_TIMEOUT = int(os.environ.get("BEAGLE_KIOSK_CATALOG_TIMEOUT", "30") or "30")
CACHE_COVERS = os.environ.get("BEAGLE_KIOSK_CACHE_COVERS", "0") == "1"
CATALOG_LIMIT = int(os.environ.get("BEAGLE_KIOSK_CATALOG_LIMIT", "0") or "0")

GFN_ENDPOINT = os.environ.get(
    "BEAGLE_KIOSK_GFN_ENDPOINT",
    "https://api-prod.nvidia.com/services/gfngames/v1/gameList",
).strip()
GFN_COUNTRY = os.environ.get("BEAGLE_KIOSK_GFN_COUNTRY", "US").strip() or "US"
GFN_LANGUAGE = os.environ.get("BEAGLE_KIOSK_GFN_LANGUAGE", "en_US").strip() or "en_US"

GMG_STOREFRONT_URL = os.environ.get(
    "BEAGLE_KIOSK_GMG_STOREFRONT_URL",
    "https://www.greenmangaming.com/games/",
).strip()
GMG_APP_ID = os.environ.get("BEAGLE_KIOSK_GMG_ALGOLIA_APP_ID", "").strip()
GMG_API_KEY = os.environ.get("BEAGLE_KIOSK_GMG_ALGOLIA_API_KEY", "").strip()
GMG_INDEX_NAME = os.environ.get("BEAGLE_KIOSK_GMG_ALGOLIA_INDEX", "").strip()
GMG_COUNTRY_CODE = os.environ.get("BEAGLE_KIOSK_GMG_COUNTRY_CODE", "DE").strip() or "DE"
GMG_BATCH_SIZE = int(os.environ.get("BEAGLE_KIOSK_GMG_BATCH_SIZE", "24") or "24")
GMG_HITS_PER_QUERY = int(os.environ.get("BEAGLE_KIOSK_GMG_HITS_PER_QUERY", "8") or "8")

USER_AGENT = "BeagleOSGamingKiosk/0.3"
GMG_BASE_URL = "https://www.greenmangaming.com"
GMG_IMAGE_BASE_URL = "https://images.greenmangaming.com/"
GMG_SEARCH_PATH = "/search"

ALLOWED_EXTRA_TOKENS = {
    "standard",
    "edition",
    "digital",
    "deluxe",
    "ultimate",
    "gold",
    "complete",
    "definitive",
    "directors",
    "cut",
    "game",
    "of",
    "the",
    "year",
    "goty",
    "enhanced",
    "remastered",
    "collection",
    "bundle",
    "lspd",
    "vr",
    "premium",
    "founders",
    "launch",
}

REJECT_EXTRA_TOKENS = {
    "dlc",
    "soundtrack",
    "artbook",
    "expansion",
    "episode",
    "chapter",
    "pass",
    "pack",
    "credits",
    "coins",
    "currency",
    "points",
    "booster",
    "boiling",
    "point",
    "invasion",
    "waters",
    "skins",
    "skin",
}

DRM_NAME_MAP = {
    "STEAM": {"steam"},
    "EPIC": {"epic", "epic games", "epic games store"},
    "UPLAY": {"ubisoft", "ubisoft connect"},
    "XBOX": {"xbox"},
    "EAAPP": {"ea app", "origin"},
    "BATTLE.NET": {"battle.net", "battlenet"},
    "UNKNOWN": set(),
}


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    target = path.with_name(f".{path.name}.tmp")
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    target.replace(path)


def fetch_text(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> str:
    request = Request(
        url,
        data=data,
        method=method,
        headers={"User-Agent": USER_AGENT, **(headers or {})},
    )
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read().decode("utf-8")


def fetch_json(url: str, *, method: str = "GET", payload: Any | None = None, headers: dict[str, str] | None = None) -> Any:
    body = None
    request_headers = {"User-Agent": USER_AGENT, **(headers or {})}
    if payload is not None:
        if isinstance(payload, (bytes, bytearray)):
            body = bytes(payload)
        else:
            body = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    text = fetch_text(url, method=method, data=body, headers=request_headers)
    return json.loads(text)


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return response.read()


def normalize_title(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.replace("®", " ").replace("™", " ").replace("©", " ")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip().lower()


def slugify(value: str) -> str:
    return normalize_title(value).replace(" ", "-")


def cover_name(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    suffix = Path(url).suffix or ".jpg"
    return f"{digest}{suffix}"


def cache_cover(url: str) -> str:
    if not url:
        return ""
    if not CACHE_COVERS:
        return url
    COVER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    target = COVER_CACHE_DIR / cover_name(url)
    if not target.exists():
        target.write_bytes(fetch_bytes(url))
    return str(target)


def gfn_cover_url(gfn_game: dict[str, Any]) -> str:
    images = gfn_game.get("images") or {}
    if not isinstance(images, dict):
        return ""
    return str(images.get("TV_BANNER") or images.get("GAME_BOX_ART") or "").strip()


def gmg_search_url(title: str) -> str:
    query = str(title or "").strip()
    if not query:
        return urljoin(GMG_BASE_URL, GMG_SEARCH_PATH)
    return f"{urljoin(GMG_BASE_URL, GMG_SEARCH_PATH)}?{urlencode({'query': query})}"


def gmg_query_params(title: str) -> str:
    return urlencode(
        {
            "query": str(title or ""),
            "hitsPerPage": str(GMG_HITS_PER_QUERY),
        }
    )


def resolve_gmg_search_config() -> tuple[str, str, str]:
    if GMG_APP_ID and GMG_API_KEY and GMG_INDEX_NAME:
        return GMG_APP_ID, GMG_API_KEY, GMG_INDEX_NAME

    html = fetch_text(GMG_STOREFRONT_URL)
    patterns = {
        "app": r"algoliaAppId:\s*'([^']+)'",
        "key": r"algoliaApiKey:\s*'([^']+)'",
        "index": r"algoliaIndexName:\s*'([^']+)'",
    }
    matches = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, html)
        if not match:
            raise RuntimeError(f"Unable to locate GMG Algolia {key} in storefront HTML.")
        matches[key] = match.group(1).strip()
    return matches["app"], matches["key"], matches["index"]


def build_gfn_query(after_cursor: str) -> bytes:
    body = f"""
{{
  apps(country:"{GFN_COUNTRY}" language:"{GFN_LANGUAGE}" orderBy: "itemMetadata.gfnPopularityRank:ASC,sortName:ASC" after:"{after_cursor}") {{
    numberReturned
    pageInfo {{
      endCursor
      hasNextPage
    }}
    items {{
      title
      sortName
      images {{
        TV_BANNER
        GAME_BOX_ART
      }}
      gfn {{
        playType
        minimumMembershipTierLabel
      }}
      variants {{
        appStore
        publisherName
      }}
    }}
  }}
}}
""".strip()
    return body.encode("utf-8")


def fetch_gfn_catalog() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = ""

    while True:
        payload = fetch_json(
            GFN_ENDPOINT,
            method="POST",
            payload=build_gfn_query(cursor),
            headers={"Content-Type": "application/json"},
        )
        apps = ((payload or {}).get("data") or {}).get("apps") or {}
        page_items = apps.get("items") or []
        if not isinstance(page_items, list):
            break
        items.extend(item for item in page_items if isinstance(item, dict) and item.get("title"))

        page_info = apps.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        next_cursor = str(page_info.get("endCursor") or "").strip()
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor

        if CATALOG_LIMIT and len(items) >= CATALOG_LIMIT:
            return items[:CATALOG_LIMIT]

    return items[:CATALOG_LIMIT] if CATALOG_LIMIT else items


def algolia_multi_query(requests_payload: list[dict[str, str]], app_id: str, api_key: str) -> list[dict[str, Any]]:
    response = fetch_json(
        f"https://{app_id}-dsn.algolia.net/1/indexes/*/queries",
        method="POST",
        payload={"requests": requests_payload},
        headers={
            "X-Algolia-API-Key": api_key,
            "X-Algolia-Application-Id": app_id,
            "Content-Type": "application/json",
        },
    )
    results = response.get("results") if isinstance(response, dict) else None
    return results if isinstance(results, list) else []


def search_gmg_hits(batch: list[dict[str, Any]], app_id: str, api_key: str, index_name: str) -> list[list[dict[str, Any]]]:
    if not batch:
        return []

    requests_payload = [{"indexName": index_name, "params": gmg_query_params(game.get("title") or "")} for game in batch]

    try:
        results = algolia_multi_query(requests_payload, app_id, api_key)
    except HTTPError as error:
        if len(batch) == 1:
            title = str(batch[0].get("title") or "").strip() or "<unknown>"
            print(f"warning: GMG lookup failed for {title}: {error}", file=sys.stderr)
            return [[]]
        midpoint = max(1, len(batch) // 2)
        return search_gmg_hits(batch[:midpoint], app_id, api_key, index_name) + search_gmg_hits(
            batch[midpoint:], app_id, api_key, index_name
        )

    normalized_results: list[list[dict[str, Any]]] = []
    for offset in range(len(batch)):
        hits: list[dict[str, Any]] = []
        if offset < len(results) and isinstance(results[offset], dict):
            raw_hits = results[offset].get("hits") or []
            if isinstance(raw_hits, list):
                hits = [hit for hit in raw_hits if isinstance(hit, dict)]
        normalized_results.append(hits)
    return normalized_results


def allowed_drms(gfn_game: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for variant in gfn_game.get("variants") or []:
        for mapped in DRM_NAME_MAP.get(str(variant.get("appStore") or "").upper(), set()):
            names.add(mapped)
    return names


def normalize_drm_name(value: str) -> str:
    return normalize_title(value).replace(" store", "")


def extra_tokens(text: str, prefix: str) -> list[str]:
    if not text.startswith(prefix):
        return []
    suffix = text[len(prefix) :].strip()
    return [token for token in suffix.split(" ") if token]


def score_gmg_hit(gfn_game: dict[str, Any], hit: dict[str, Any]) -> int:
    if not hit.get("IsSellable") or not hit.get("Url"):
        return -1

    platforms = {normalize_title(item) for item in hit.get("PlatformName") or []}
    if "pc" not in platforms:
        return -1

    gfn_title = normalize_title(gfn_game.get("title"))
    hit_title = normalize_title(hit.get("DisplayName"))
    if not gfn_title or not hit_title:
        return -1

    allowed = allowed_drms(gfn_game)
    drm_name = normalize_drm_name(hit.get("DrmName") or "")
    if allowed and drm_name and drm_name not in allowed:
        return -1

    score = -1
    if hit_title == gfn_title:
        score = 1000
    elif hit_title.startswith(f"{gfn_title} "):
        score = 760
    elif hit_title.startswith(f"{gfn_title}:"):
        score = 680
    elif gfn_title in hit_title:
        score = 520
    elif hit_title in gfn_title:
        score = 420
    else:
        return -1

    franchise = normalize_title(hit.get("Franchise") or "")
    if franchise == gfn_title:
        score += 120

    extras = extra_tokens(hit_title.replace(":", " "), gfn_title)
    if extras:
        if any(token in REJECT_EXTRA_TOKENS for token in extras):
            score -= 260
        if all(token in ALLOWED_EXTRA_TOKENS for token in extras):
            score += 80

    best_selling_rank = hit.get("BestSellingRank") or 0
    if isinstance(best_selling_rank, (int, float)) and best_selling_rank > 0:
        score += max(0, 100 - min(int(best_selling_rank), 100))

    return score


def select_gmg_match(gfn_game: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any] | None:
    best_hit: dict[str, Any] | None = None
    best_score = -1
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        current_score = score_gmg_hit(gfn_game, hit)
        if current_score > best_score:
            best_score = current_score
            best_hit = hit
    if best_score < 500:
        return None
    return best_hit


def first_available_region(hit: dict[str, Any]) -> dict[str, Any]:
    regions = hit.get("Regions") or {}
    if not isinstance(regions, dict):
        return {}
    preferred = regions.get(GMG_COUNTRY_CODE)
    if isinstance(preferred, dict) and not preferred.get("IsExcludeFromCurrentCountry"):
        return preferred
    for region in regions.values():
        if isinstance(region, dict) and not region.get("IsExcludeFromCurrentCountry"):
            return region
    return {}


def format_price(region: dict[str, Any]) -> str:
    if not isinstance(region, dict):
        return "n/a"
    value = region.get("Drp")
    if value in (None, ""):
        value = region.get("Rrp")
    if value in (None, ""):
        value = region.get("Mrp")
    currency = str(region.get("CurrencyCode") or "").strip()
    if value in (None, ""):
        return "n/a"
    try:
        return f"{float(value):.2f} {currency}".strip()
    except Exception:
        return f"{value} {currency}".strip()


def absolute_gmg_url(path: str) -> str:
    return urljoin(GMG_BASE_URL, path or "")


def absolute_gmg_image_url(path: str) -> str:
    return urljoin(GMG_IMAGE_BASE_URL, path.lstrip("/") if isinstance(path, str) else "")


def build_catalog_entry(index: int, gfn_game: dict[str, Any], gmg_hit: dict[str, Any]) -> dict[str, Any]:
    region = first_available_region(gmg_hit)
    cover_url = gfn_cover_url(gfn_game) or absolute_gmg_image_url(gmg_hit.get("ImageUrl") or "")
    title = str(gfn_game.get("title") or gmg_hit.get("DisplayName") or "Unbenanntes Spiel").strip()
    genre = ", ".join(gmg_hit.get("Genre") or []) or "GFN Compatible"
    publisher = str(gmg_hit.get("PublisherName") or "").strip()
    release_timestamp = region.get("ReleaseDate") if isinstance(region, dict) else None
    release_year = None
    if isinstance(release_timestamp, (int, float)) and release_timestamp > 0:
        release_year = int(str(int(release_timestamp))[:4])

    store_url = absolute_gmg_url(gmg_hit.get("Url") or "")
    return {
        "id": slugify(title) or f"gfn-{index}",
        "gfn_id": gfn_game.get("sortName") or slugify(title) or f"gfn-{index}",
        "slug": slugify(title) or f"gfn-{index}",
        "title": title,
        "genre": genre,
        "description": (
            f"{publisher or 'Green Man Gaming'} direkt ueber GMG kaufen und danach in GeForce NOW starten."
        ),
        "cover_url": cache_cover(cover_url) if cover_url else "",
        "geforce_now_supported": True,
        "release_year": release_year,
        "popularity": max(1, 10000 - index),
        "system_requirements": [
            "GeForce NOW Konto",
            "Stabile Internetverbindung",
            "Controller oder Maus und Tastatur",
        ],
        "stores": [
            {
                "name": "GMG",
                "url": store_url,
                "price": format_price(region),
                "sku": str(gmg_hit.get("ProductId") or gmg_hit.get("GameVariantId") or "").strip(),
            }
        ],
        "publisher": publisher,
        "app_store": ", ".join(sorted({str(item.get("appStore") or "").strip() for item in gfn_game.get("variants") or [] if item.get("appStore")})),
    }


def build_search_fallback_entry(index: int, gfn_game: dict[str, Any]) -> dict[str, Any]:
    title = str(gfn_game.get("title") or "Unbenanntes Spiel").strip()
    cover_url = gfn_cover_url(gfn_game)
    return {
        "id": slugify(title) or f"gfn-{index}",
        "gfn_id": gfn_game.get("sortName") or slugify(title) or f"gfn-{index}",
        "slug": slugify(title) or f"gfn-{index}",
        "title": title,
        "genre": "GFN Compatible",
        "description": "Bei Green Man Gaming suchen und danach in GeForce NOW starten.",
        "cover_url": cover_url,
        "geforce_now_supported": True,
        "release_year": None,
        "popularity": max(1, 10000 - index),
        "system_requirements": [
            "GeForce NOW Konto",
            "Stabile Internetverbindung",
            "Controller oder Maus und Tastatur",
        ],
        "stores": [
            {
                "name": "GMG",
                "url": gmg_search_url(title),
                "price": "Bei GMG suchen",
                "sku": "",
            }
        ],
        "publisher": "",
        "app_store": ", ".join(
            sorted({str(item.get("appStore") or "").strip() for item in gfn_game.get("variants") or [] if item.get("appStore")})
        ),
    }


def build_catalog() -> list[dict[str, Any]]:
    gfn_games = fetch_gfn_catalog()
    if not gfn_games:
        return []

    app_id, api_key, index_name = resolve_gmg_search_config()
    catalog: list[dict[str, Any]] = []

    for batch_start in range(0, len(gfn_games), GMG_BATCH_SIZE):
        batch = gfn_games[batch_start : batch_start + GMG_BATCH_SIZE]
        results = search_gmg_hits(batch, app_id, api_key, index_name)
        for offset, game in enumerate(batch):
            hits = []
            if offset < len(results):
                hits = results[offset]
            match = select_gmg_match(game, hits)
            if match:
                catalog.append(build_catalog_entry(batch_start + offset, game, match))
            else:
                catalog.append(build_search_fallback_entry(batch_start + offset, game))

            if CATALOG_LIMIT and len(catalog) >= CATALOG_LIMIT:
                return catalog

    deduped: dict[str, dict[str, Any]] = {}
    for item in catalog:
        key = normalize_title(item.get("title")) or str(item.get("id"))
        if key not in deduped:
            deduped[key] = item
    return list(deduped.values())


def main() -> int:
    current = read_json(GAMES_PATH, [])
    try:
        catalog = build_catalog()
    except (HTTPError, URLError, TimeoutError, ValueError, RuntimeError) as error:
        print(f"warning: unable to refresh GMG catalog: {error}", file=sys.stderr)
        if isinstance(current, list) and current:
            return 0
        raise

    if not catalog and isinstance(current, list) and current:
        print("warning: catalog refresh returned no matches, keeping existing games.json", file=sys.stderr)
        return 0

    write_json(GAMES_PATH, catalog)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
