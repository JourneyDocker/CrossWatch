# tests/test_mdblist_pause_watched_clamp.py
# CrossWatch - MDBList pause progress clamp tests
# Copyright (c) 2025-2026 CrossWatch / Cenodude (https://github.com/cenodude/CrossWatch)
from __future__ import annotations

from dataclasses import replace
from importlib import import_module

import pytest

from providers.scrobble.scrobble import ScrobbleEvent


def event(**changes):
    return replace(
        ScrobbleEvent(
            "pause",
            "movie",
            {"tmdb": "123"},
            "Test movie",
            2020,
            None,
            None,
            85,
            "test-user",
            "test-server",
            "test-session",
            {},
        ),
        **changes,
    )


@pytest.fixture()
def mdblist(monkeypatch):
    module = import_module("providers.scrobble.mdblist.sink")
    sink = module.MDBListSink()
    calls: list[tuple[str, dict]] = []

    monkeypatch.setattr(sink, "_note_watch", lambda *a, **kw: None)
    monkeypatch.setattr(module, "record_scrobble_event", lambda *a, **kw: None)
    monkeypatch.setattr(module, "_auto_remove_across", lambda *a, **kw: None)

    def send_http(path, body, *args):
        calls.append((path, dict(body)))
        return {"ok": True, "status": 201, "resp": {"action": path.rsplit("/", 1)[-1]}}

    monkeypatch.setattr(sink, "_send_http", send_http)

    cfg = {
        "mdblist": {"api_key": "test-key"},
        "scrobble": {"trakt": {"watched_at": 90}, "watch": {"pause_debounce_seconds": 1}},
    }
    return sink, cfg, calls


@pytest.mark.parametrize("progress", [80, 85, 90, 99, 100])
def test_pause_at_or_above_80_is_sent_at_79(mdblist, progress):
    sink, cfg, calls = mdblist

    sink.send(event(progress=progress), cfg)

    assert calls and calls[-1][0] == "/scrobble/pause"
    assert calls[-1][1]["progress"] == 79.0


@pytest.mark.parametrize("progress", [1, 45, 79])
def test_pause_below_80_keeps_its_progress(mdblist, progress):
    sink, cfg, calls = mdblist

    sink.send(event(progress=progress), cfg)

    assert calls and calls[-1][0] == "/scrobble/pause"
    assert calls[-1][1]["progress"] == float(int(progress))


def test_stop_held_below_watched_at_sends_clamped_pause(mdblist):
    sink, cfg, calls = mdblist

    sink.send(event(action="stop", progress=85), cfg)

    assert calls and calls[-1][0] == "/scrobble/pause"
    assert calls[-1][1]["progress"] == 79.0


def test_stop_at_or_above_watched_at_still_sends_stop(mdblist):
    sink, cfg, calls = mdblist

    sink.send(event(action="stop", progress=95), cfg)

    assert calls and calls[-1][0] == "/scrobble/stop"
    assert calls[-1][1]["progress"] == 95.0


def test_clamped_pause_keeps_real_session_progress(mdblist):
    sink, cfg, calls = mdblist

    sink.send(event(progress=95), cfg)
    assert calls[-1][1]["progress"] == 79.0

    sink.send(event(action="stop", progress=96), cfg)

    assert calls[-1][0] == "/scrobble/stop"
    assert calls[-1][1]["progress"] == 96.0
