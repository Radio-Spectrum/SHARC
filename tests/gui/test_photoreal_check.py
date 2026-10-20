"""Access checks for Google Photorealistic 3D Tiles (Google key / Cesium ion token), with canned HTTP replies."""
import pytest

from core import photoreal_check as pc


class _Resp:
    def __init__(self, status, body=None):
        self.status_code = status
        self._body = body or {}

    def json(self):
        return self._body


def _patch(monkeypatch, replies):
    """`replies` maps a URL prefix to a response; unknown URLs fail the test."""
    def fake_get(url, **kw):
        for prefix, resp in replies.items():
            if url.startswith(prefix):
                return resp
        raise AssertionError(f"unexpected URL {url}")
    monkeypatch.setattr(pc, "_get", fake_get)


def test_empty_inputs_are_rejected_without_network():
    assert pc.check_google_key("  ")[0] is False
    assert pc.check_ion_token("")[0] is False


@pytest.mark.parametrize("status,needle", [(200, "accepted"), (400, "rejected"), (403, "Map Tiles API"), (429, "quota")])
def test_google_key_statuses(monkeypatch, status, needle):
    body = {"error": {"message": "API key not valid."}} if status == 400 else {}
    _patch(monkeypatch, {pc.GOOGLE_ROOT: _Resp(status, body)})
    ok, msg = pc.check_google_key("k")
    assert ok is (status == 200)
    assert needle in msg
    assert not msg.endswith("..")


def test_ion_token_valid_and_asset_present(monkeypatch):
    _patch(monkeypatch, {pc.ION_ASSET: _Resp(200), pc.ION_TERRAIN_ASSET: _Resp(200)})
    ok, msg = pc.check_ion_token("t")
    assert ok and "Photorealistic 3D Tiles available" in msg and "World Terrain available" in msg


def test_ion_token_valid_but_photoreal_asset_not_added(monkeypatch):
    _patch(monkeypatch, {pc.ION_ASSET: _Resp(404), pc.ION_TERRAIN_ASSET: _Resp(200)})
    ok, msg = pc.check_ion_token("t")
    assert not ok and "2275207" in msg and "World Terrain available" in msg


def test_ion_token_rejected(monkeypatch):
    _patch(monkeypatch, {pc.ION_ASSET: _Resp(401), pc.ION_TERRAIN_ASSET: _Resp(401)})
    ok, msg = pc.check_ion_token("t")
    assert not ok and "401" in msg


def test_network_failure_is_reported_not_raised(monkeypatch):
    def boom(url, **kw):
        raise OSError("down")
    monkeypatch.setattr(pc, "_get", boom)
    assert pc.check_google_key("k")[0] is False
    assert pc.check_ion_token("t")[0] is False
