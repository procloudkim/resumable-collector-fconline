import os
from pathlib import Path
import types

import pytest


def make_resp(status: int, content: bytes = b""):
    r = types.SimpleNamespace()
    r.status_code = status
    r.content = content
    return r


def test_try_download_head_403_then_get_200(monkeypatch, tmp_path):
    from app.services import images as mod

    calls = {"head": 0, "get": 0}

    def fake_head(url, headers=None, timeout=None):
        calls["head"] += 1
        return make_resp(403)

    def fake_get(url, headers=None, timeout=None):
        calls["get"] += 1
        return make_resp(200, b"ok")

    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(head=fake_head, get=fake_get))
    out = tmp_path / "x.png"
    ok = mod._try_download("https://cdn/x.png", out)
    assert ok is True
    assert out.exists() and out.read_bytes() == b"ok"
    assert calls["head"] == 1 and calls["get"] == 1


def test_try_download_head_404(monkeypatch, tmp_path):
    from app.services import images as mod

    def fake_head(url, headers=None, timeout=None):
        return make_resp(404)

    def fake_get(url, headers=None, timeout=None):
        raise AssertionError("GET should not be called after 404 HEAD")

    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(head=fake_head, get=fake_get))
    out = tmp_path / "x.png"
    ok = mod._try_download("https://cdn/x.png", out)
    assert ok is False
    assert not out.exists()


def test_try_download_get_403(monkeypatch, tmp_path):
    from app.services import images as mod

    def fake_head(url, headers=None, timeout=None):
        return make_resp(200)

    def fake_get(url, headers=None, timeout=None):
        return make_resp(403)

    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(head=fake_head, get=fake_get))
    out = tmp_path / "x.png"
    ok = mod._try_download("https://cdn/x.png", out)
    assert ok is False
    assert not out.exists()


def test_candidate_urls_contains_pid_and_zero_padded():
    from app.services import images as mod
    # choose an spid whose pid has < 6 digits to see zero-padding
    spid = 123456789  # pid = 456789 -> 6 digits, zero-padded still same
    pid = spid % 1_000_000
    pid6 = f"{pid:06d}"
    urls = mod.candidate_urls(spid)
    s = "\n".join(urls)
    assert str(pid) in s and pid6 in s


def test_ensure_player_image_ttl_skip(monkeypatch, tmp_path):
    from app.services import images as mod

    # Redirect IMAGES to tmp_path
    monkeypatch.setattr(mod, "IMAGES", tmp_path)

    # Prepare cached file
    spid = 260226
    out = tmp_path / f"{spid}.png"
    out.write_bytes(b"old")

    # Set mtime to now so TTL check passes
    os.utime(out, None)

    # requests should not be called when TTL is valid
    def fake_head(*a, **k):
        raise AssertionError("network should not be called when TTL valid")

    def fake_get(*a, **k):
        raise AssertionError("network should not be called when TTL valid")

    monkeypatch.setattr(mod, "requests", types.SimpleNamespace(head=fake_head, get=fake_get))

    p = mod.ensure_player_image(spid, ttl_days=365)
    assert p == out
