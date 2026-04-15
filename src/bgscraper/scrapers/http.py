"""HTTP client with UA rotation, retry, and jittered delays."""
from __future__ import annotations

import random
import time
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..config import Settings, get_settings
from ..logging_setup import get_logger

log = get_logger(__name__)

_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class RetryableHttpError(Exception):
    """HTTP error worth retrying."""


def _load_user_agents() -> list[str]:
    here = Path(__file__).resolve().parent.parent / "resources" / "user_agents.txt"
    if not here.exists():
        return [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ]
    return [line.strip() for line in here.read_text(encoding="utf-8").splitlines() if line.strip()]


class HttpClient:
    """Thin wrapper over httpx.Client with random UA, retry, and jitter."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.user_agents = _load_user_agents()
        proxy = self.settings.http_proxy or None
        self._client = httpx.Client(
            http2=True,
            timeout=httpx.Timeout(self.settings.request_timeout, connect=10.0),
            follow_redirects=True,
            proxy=proxy,
            headers={
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "bg-BG,bg;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> HttpClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _random_ua(self) -> str:
        return random.choice(self.user_agents)

    def _jitter(self) -> None:
        lo = self.settings.request_min_delay
        hi = max(lo, self.settings.request_max_delay)
        time.sleep(random.uniform(lo, hi))

    def get(self, url: str, *, params: dict | None = None, referer: str | None = None) -> str:
        self._jitter()
        return self._do_get(url, params=params, referer=referer)

    def _do_get(self, url: str, *, params: dict | None, referer: str | None) -> str:
        attempts = max(1, self.settings.request_max_retries)

        @retry(
            reraise=True,
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=2, min=2, max=30),
            retry=retry_if_exception_type((RetryableHttpError, httpx.TransportError)),
        )
        def _call() -> str:
            headers = {"User-Agent": self._random_ua()}
            if referer:
                headers["Referer"] = referer
            try:
                resp = self._client.get(url, params=params, headers=headers)
            except httpx.TransportError as e:
                log.warning("http.transport_error", url=url, error=str(e))
                raise
            if resp.status_code in _RETRYABLE_STATUSES:
                log.warning("http.retryable_status", url=url, status=resp.status_code)
                raise RetryableHttpError(f"{resp.status_code} for {url}")
            resp.raise_for_status()
            return resp.text

        return _call()
