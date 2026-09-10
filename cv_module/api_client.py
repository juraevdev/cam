"""
HTTP client for posting detected plates to the Django backend.
"""

from __future__ import annotations

from typing import Any

import requests

from config import REQUEST_TIMEOUT_SECONDS, SCAN_ENDPOINT


def post_scan(
    license_plate: str,
    *,
    camera_type: str = "auto",
    endpoint: str = SCAN_ENDPOINT,
    timeout: float = REQUEST_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """
    POST /api/scan/

    Returns parsed JSON body. Raises requests.HTTPError on transport/HTTP errors
    except 402 Payment Required (returned as a normal business response).
    """
    payload = {
        "license_plate": license_plate,
        "camera_type": camera_type,
    }
    response = requests.post(endpoint, json=payload, timeout=timeout)

    # 402 is an expected business outcome (require_payment).
    if response.status_code == 402:
        data = response.json()
        data.setdefault("_http_status", 402)
        return data

    response.raise_for_status()
    data = response.json()
    data.setdefault("_http_status", response.status_code)
    return data
