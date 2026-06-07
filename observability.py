"""Logging and lightweight profiling for Blind Quill.

Everything here writes to the log only — never to the UI. Three concerns live
together:

- `configure_logging()` sets up the `blind_quill` logger once.
- `resource_snapshot()` reports process memory, CPU, and (when available) GPU
  memory, never raising even when a metric is unavailable.
- `RunProfiler` times the stages of one request and logs a single summary line,
  so a slow or failing stitch is easy to locate in the log.
"""

from __future__ import annotations

import logging
import os
import time
from contextlib import contextmanager
from typing import Iterator

LOGGER_NAME = "blind_quill"

_configured = False


def configure_logging() -> None:
    """Attach a stderr handler to the `blind_quill` logger once.

    Idempotent: importing modules and `app.py` may both call it. The level comes
    from `BQ_LOG_LEVEL` (default INFO).
    """
    global _configured
    if _configured:
        return
    level_name = os.environ.get("BQ_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.propagate = False
    _configured = True


def get_logger(suffix: str | None = None) -> logging.Logger:
    configure_logging()
    name = LOGGER_NAME if not suffix else f"{LOGGER_NAME}.{suffix}"
    return logging.getLogger(name)


def resource_snapshot() -> dict[str, float]:
    """Best-effort process/GPU usage. Any missing metric is simply omitted."""
    snapshot: dict[str, float] = {}

    try:
        import psutil

        process = psutil.Process()
        snapshot["rss_mb"] = round(process.memory_info().rss / 1024 / 1024, 1)
        # interval=None returns usage since the previous call without blocking.
        snapshot["cpu_percent"] = round(process.cpu_percent(interval=None), 1)
    except Exception:  # noqa: BLE001 - metrics are optional; never break the request
        pass

    try:
        import torch

        if torch.cuda.is_available():
            snapshot["gpu_alloc_mb"] = round(torch.cuda.memory_allocated() / 1024 / 1024, 1)
            snapshot["gpu_reserved_mb"] = round(torch.cuda.memory_reserved() / 1024 / 1024, 1)
        elif getattr(torch.backends, "mps", None) is not None and torch.backends.mps.is_available():
            current = getattr(torch.mps, "current_allocated_memory", None)
            if callable(current):
                snapshot["mps_alloc_mb"] = round(current() / 1024 / 1024, 1)
    except Exception:  # noqa: BLE001 - torch may be absent or a backend may lack the API
        pass

    return snapshot


def _format_snapshot(snapshot: dict[str, float]) -> str:
    if not snapshot:
        return "n/a"
    return " ".join(f"{key}={value}" for key, value in snapshot.items())


class RunProfiler:
    """Times the stages of one request and logs a single summary line.

    Usage::

        profiler = RunProfiler("stitch", label="story=abc")
        with profiler.stage("plan"):
            ...
        profiler.note_message()
        profiler.summary()
    """

    def __init__(self, run: str, label: str = "") -> None:
        self.run = run
        self.label = label
        self.logger = get_logger(run)
        self._started = time.perf_counter()
        self._durations: dict[str, float] = {}
        self._messages = 0

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        before = resource_snapshot()
        start = time.perf_counter()
        self.logger.debug("%s stage '%s' start | %s", self.label, name, _format_snapshot(before))
        try:
            yield
        finally:
            elapsed = time.perf_counter() - start
            self._durations[name] = self._durations.get(name, 0.0) + elapsed
            after = resource_snapshot()
            self.logger.debug(
                "%s stage '%s' done in %.2fs | %s",
                self.label,
                name,
                elapsed,
                _format_snapshot(after),
            )

    def note_message(self, count: int = 1) -> None:
        """Record that `count` model messages were processed in this run."""
        self._messages += count

    @property
    def messages(self) -> int:
        return self._messages

    def summary(self) -> None:
        total = time.perf_counter() - self._started
        stages = " ".join(f"{name} {dur:.2f}s" for name, dur in self._durations.items())
        self.logger.info(
            "%s %s done in %.2fs | %s | messages=%d",
            self.run,
            self.label,
            total,
            stages or "no-stages",
            self._messages,
        )
