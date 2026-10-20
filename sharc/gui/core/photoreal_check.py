"""Connectivity checks for the photorealistic 3D sources (Google Map Tiles key, Cesium ion token).

The preview loads Google Photorealistic 3D Tiles either through a Cesium ion token (asset 2275207,
which must be added to the account's "My Assets" first) or directly with a Google Map Tiles API key.
Both fail in ways the 3D view only reports as a generic error, so these checks give a precise reason.
Each function returns (ok, message) and never raises.
"""
from __future__ import annotations

from typing import Tuple

GOOGLE_ROOT = "https://tile.googleapis.com/v1/3dtiles/root.json"
ION_ASSET = "https://api.cesium.com/v1/assets/2275207"
ION_TERRAIN_ASSET = "https://api.cesium.com/v1/assets/1"      # Cesium World Terrain
TIMEOUT_S = 8


def _get(url: str, **kw):
    import requests
    return requests.get(url, timeout=TIMEOUT_S, **kw)


def check_google_key(key: str) -> Tuple[bool, str]:
    key = (key or "").strip()
    if not key:
        return False, "Enter a Google Map Tiles API key first."
    try:
        r = _get(GOOGLE_ROOT, params={"key": key})
    except Exception as exc:  # noqa: BLE001 - network errors of any kind
        return False, f"Could not reach Google ({type(exc).__name__}). Check the internet connection."
    if r.status_code == 200:
        return True, "Google Photorealistic 3D Tiles: key accepted."
    reason = ""
    try:
        reason = r.json().get("error", {}).get("message", "").rstrip(".")
    except Exception:  # noqa: BLE001
        pass
    if r.status_code in (400, 401):
        return False, f"Google rejected the key ({r.status_code}): {reason or 'invalid API key'}."
    if r.status_code == 403:
        return False, ("Google refused access (403): enable the 'Map Tiles API' for this key's project "
                       f"and billing. {reason}").strip()
    if r.status_code == 429:
        return False, "Google quota exceeded (429). Try again later."
    return False, f"Google returned HTTP {r.status_code}. {reason}".strip()


def check_ion_token(token: str) -> Tuple[bool, str]:
    token = (token or "").strip()
    if not token:
        return False, "Enter a Cesium ion access token first."
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = _get(ION_ASSET, headers=headers)
        rt = _get(ION_TERRAIN_ASSET, headers=headers)
    except Exception as exc:  # noqa: BLE001
        return False, f"Could not reach Cesium ion ({type(exc).__name__}). Check the internet connection."
    if r.status_code == 401 or rt.status_code == 401:
        return False, "Cesium ion rejected the token (401): copy a valid access token from ion.cesium.com."
    parts = []
    ok = True
    if r.status_code == 200:
        parts.append("Photorealistic 3D Tiles available")
    else:
        ok = False
        parts.append("Photorealistic 3D Tiles NOT in this account: open ion.cesium.com > Asset Depot, "
                     "add 'Google Photorealistic 3D Tiles' (asset 2275207) to My Assets")
    parts.append("Cesium World Terrain available" if rt.status_code == 200 else "Cesium World Terrain not reachable")
    return ok, "Cesium ion token valid: " + "; ".join(parts) + "."
