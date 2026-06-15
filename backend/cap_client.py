import logging
from typing import Any

import httpx
from urllib.parse import urlencode, quote

from config import CAP_BASE_URL

log = logging.getLogger("procurement-ai.cap")
DEFAULT_TIMEOUT = 5.0


async def _get_json(url: str, auth: tuple[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        resp = await client.get(url, auth=auth)
        resp.raise_for_status()
        return resp.json()


async def fetch_vendors_from_cap(category: str = "") -> list[dict[str, Any]]:
    """Fetch vendor data from the local CAP backend."""
    auth = ("procurement_officer", "pass123")
    base = f"{CAP_BASE_URL}/odata/v4/procurement/Vendors"
    filter_str = "isActive eq true"
    if category:
        filter_str += f" and category eq '{category}'"
    params = {"$filter": filter_str, "$top": 20}
    qs = urlencode(params, quote_via=quote)
    url = f"{base}?{qs}"

    try:
        data = await _get_json(url, auth)
        return data.get("value", [])
    except Exception as exc:
        log.error("CAP vendor fetch failed: %s", exc)
        raise RuntimeError("Failed to fetch vendors from CAP backend.") from exc


async def fetch_budget_from_cap(department: str) -> dict[str, Any]:
    """Fetch a budget row from the local CAP backend via a trusted function."""
    auth = ("admin", "admin123")
    base = f"{CAP_BASE_URL}/odata/v4/procurement/getBudget"
    params = {"department": department}
    qs = urlencode(params, quote_via=quote)
    url = f"{base}?{qs}"

    try:
        data = await _get_json(url, auth)
        if not data:
            raise RuntimeError(f"No budget found for department '{department}'.")
        return data
    except Exception as exc:
        log.error("CAP budget fetch failed: %s", exc)
        raise RuntimeError("Failed to fetch budget from CAP backend.") from exc
