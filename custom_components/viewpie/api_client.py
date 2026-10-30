"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import aiohttp
from aiohttp import ClientTimeout

from .const import (
    API_CAMERAS,
    API_FULLSCREEN,
    API_GRID,
    API_PANELS,
    API_PANELS_ACTIVATE,
    API_PAUSE,
    API_RELOAD,
    API_RESUME,
    API_SETTINGS,
    API_STATUS,
    REQUEST_TIMEOUT_SECONDS,
)

_LOGGER = logging.getLogger(__name__)


class ViewpieConnectionError(Exception):
    """Raised when the viewpie device cannot be reached or returns an error."""


class ViewpieApiClient:
    """Async HTTP client for the modified viewpie REST API."""

    def __init__(
        self,
        host: str,
        port: int,
        api_key: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        """Initialize the client.

        If an external ``aiohttp.ClientSession`` is provided (e.g. the shared
        Home Assistant session), it is used and will NOT be closed by this
        client. Otherwise an internal session is created lazily and must be
        closed via :meth:`async_close`.
        """
        self._host = host
        self._port = port
        self._api_key = api_key
        self._base_url = f"http://{host}:{port}"
        self._session = session
        self._owns_session = session is None
        self._connector: Optional[aiohttp.TCPConnector] = None

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------
    async def async_init(self) -> None:
        """Create an internal aiohttp session if none was injected.

        ``connector_owner=False`` lets us close the session without waiting
        for pooled connections to expire (they are owned by a shared
        connector); the connector itself is closed in :meth:`async_close`.
        This avoids "Unclosed client session" warnings and lingering sockets.
        """
        if self._session is None:
            loop = asyncio.get_running_loop()
            # Resolve DNS via the standard library in a thread executor
            # instead of aiodns. This avoids known aiodns/uvloop API
            # incompatibilities (Channel.getaddrinfo signature changes) and
            # keeps resolution working even when third-party DNS plugins are
            # loaded or sockets are restricted by the test harness.
            resolver = aiohttp.ThreadedResolver(loop=loop)
            connector = aiohttp.TCPConnector(
                limit=4,
                ttl_dns_cache=300,
                force_close=True,
                resolver=resolver,
            )
            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
                connector=connector,
                connector_owner=False,
            )
            self._connector = connector
            self._owns_session = True

    async def async_close(self) -> None:
        """Close the internal session and connector (only if we own them)."""
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None
            connector = getattr(self, "_connector", None)
            if connector is not None:
                await connector.close()
                self._connector = None

    # ------------------------------------------------------------------
    # Low-level request helper
    # ------------------------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        data: Optional[dict[str, Any]] = None,
    ) -> Any:
        """Perform an HTTP request against the viewpie API.

        Raises :class:`ViewpieConnectionError` on any network / HTTP error.
        """
        if self._session is None:
            await self.async_init()
        assert self._session is not None

        url = f"{self._base_url}{path}"
        _LOGGER.debug("viewpie request: %s %s", method, url)
        try:
            async with self._session.request(
                method, url, json=data, headers=self._headers()
            ) as response:
                response.raise_for_status()
                text = await response.text()
                if not text:
                    return {}
                return json.loads(text)
        except aiohttp.ClientError as err:
            _LOGGER.error("viewpie request failed (%s %s): %s", method, url, err)
            raise ViewpieConnectionError(f"Request to {url} failed: {err}") from err
        except (json.JSONDecodeError, ValueError) as err:
            _LOGGER.error("viewpie returned invalid JSON (%s %s): %s", method, url, err)
            raise ViewpieConnectionError(
                f"Invalid JSON response from {url}: {err}"
            ) from err
        except TimeoutError as err:
            _LOGGER.error("viewpie request timed out (%s %s)", method, url)
            raise ViewpieConnectionError(
                f"Request to {url} timed out"
            ) from err

    # ------------------------------------------------------------------
    # API methods
    # ------------------------------------------------------------------
    async def get_status(self) -> dict[str, Any]:
        """Return the current device status payload."""
        result = await self._request("GET", API_STATUS)
        return result if isinstance(result, dict) else {}

    async def pause(self) -> dict[str, Any]:
        """Pause the camera wall."""
        result = await self._request("POST", API_PAUSE)
        return result if isinstance(result, dict) else {}

    async def resume(self) -> dict[str, Any]:
        """Resume the camera wall."""
        result = await self._request("POST", API_RESUME)
        return result if isinstance(result, dict) else {}

    async def grid(self) -> dict[str, Any]:
        """Return to the grid layout."""
        result = await self._request("POST", API_GRID)
        return result if isinstance(result, dict) else {}

    async def fullscreen(
        self, camera: str, duration: Optional[int] = None
    ) -> dict[str, Any]:
        """Show a single camera full-screen, optionally with auto-return."""
        data: dict[str, Any] = {"camera": camera}
        if duration:
            data["duration_seconds"] = int(duration)
        result = await self._request("POST", API_FULLSCREEN, data)
        return result if isinstance(result, dict) else {}

    async def get_settings(self) -> dict[str, Any]:
        """Return the current settings payload."""
        result = await self._request("GET", API_SETTINGS)
        return result if isinstance(result, dict) else {}

    async def update_settings(self, **kwargs: Any) -> dict[str, Any]:
        """Update one or more settings via PUT /api/settings."""
        result = await self._request("PUT", API_SETTINGS, dict(kwargs))
        return result if isinstance(result, dict) else {}

    async def get_panels(self) -> list[Any]:
        """Return the list of configured panels/scenes."""
        response = await self._request("GET", API_PANELS)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return response.get("panels", [])
        return []

    async def activate_panel(self, panel_id: str) -> dict[str, Any]:
        """Activate a panel by id."""
        path = API_PANELS_ACTIVATE.format(panel_id=panel_id)
        result = await self._request("POST", path)
        return result if isinstance(result, dict) else {}

    async def get_cameras(self) -> list[Any]:
        """Return the list of configured cameras."""
        response = await self._request("GET", API_CAMERAS)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return response.get("cameras", [])
        return []

    async def reload_config(self) -> dict[str, Any]:
        """Ask viewpie to reload its configuration file."""
        result = await self._request("POST", API_RELOAD)
        return result if isinstance(result, dict) else {}

    async def test_connection(self) -> bool:
        """Return True if the device responds to a status request."""
        try:
            await self.get_status()
            return True
        except ViewpieConnectionError:
            return False
