"""Tests for Telegram bot thread lifecycle in the desktop pipeline."""

import threading

from src import pipeline


def test_start_telegram_bot_thread_reuses_running_instance(monkeypatch) -> None:
    pipeline._telegram_bot_thread = None  # noqa: SLF001

    started = threading.Event()
    release = threading.Event()

    def fake_loop() -> None:
        started.set()
        release.wait(timeout=2)

    monkeypatch.setattr(pipeline, "run_telegram_bot_loop", fake_loop)

    first = pipeline.start_telegram_bot_thread()
    assert first.reused_existing is False
    assert first.thread is not None
    assert started.wait(timeout=1)

    second = pipeline.start_telegram_bot_thread()
    assert second.reused_existing is True
    assert second.thread is first.thread

    release.set()
    first.thread.join(timeout=1)

    pipeline._telegram_bot_thread = None  # noqa: SLF001
