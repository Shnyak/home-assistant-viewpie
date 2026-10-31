"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib.parse import quote

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
        self._host = host
        self._port = port
        self._api_key = api_key
        self._base_url = f"http://{host}:{port}"
        self._session = session
        self._owns_session = session is None
        self._connector: Optional[aiohttp.TCPConnector] = None

    async def async_init(self) -> None:
        """Create an internal aiohttp session if none was injected."""
        if self._session is None:
            connector = aiohttp.TCPConnector(
                limit=4,
                ttl_dns_cache=300,
                force_close=True,
            )
            self._session = aiohttp.ClientSession(
                timeout=ClientTimeout(total=REQUEST_TIMEOUT_SECONDS),
                connector=connector,
                connector_owner=False,
            )
            self._connector = connector
            self._owns_session = True

    async def async_close(self) -> None:
        """Close only sessions owned by this client."""
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None
            if self._connector is not None:
                await self._connector.close()
                self._connector = None

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
                return json.loads(text) if text else {}
        except aiohttp.ClientError as err:
            _LOGGER.error("viewpie request failed (%s %s): %s", method, url, err)
            raise ViewpieConnectionError(f"Request to {url} failed: {err}") from err
        except (json.JSONDecodeError, ValueError) as err:
            _LOGGER.error("viewpie returned invalid JSON (%s %s): %s", method, url, err)
            raise ViewpieConnectionError(f"Invalid JSON response from {url}: {err}") from err
        except TimeoutError as err:
            _LOGGER.error("viewpie request timed out (%s %s)", method, url)
            raise ViewpieConnectionError(f"Request to {url} timed out") from err

    async def get_status(self) -> dict[str, Any]:
        result = await self._request("GET", API_STATUS)
        return result if isinstance(result, dict) else {}

    async def pause(self) -> dict[str, Any]:
        result = await self._request("POST", API_PAUSE)
        return result if isinstance(result, dict) else {}

    async def resume(self) -> dict[str, Any]:
        result = await self._request("POST", API_RESUME)
        return result if isinstance(result, dict) else {}

    async def grid(self) -> dict[str, Any]:
        result = await self._request("POST", API_GRID)
        return result if isinstance(result, dict) else {}

    async def fullscreen(self, camera: str, duration: Optional[int] = None) -> dict[str, Any]:
        data: dict[str, Any] = {"camera": camera}
        if duration:
            data["duration_seconds"] = int(duration)
        result = await self._request("POST", API_FULLSCREEN, data)
        return result if isinstance(result, dict) else {}

    async def get_settings(self) -> dict[str, Any]:
        result = await self._request("GET", API_SETTINGS)
        return result if isinstance(result, dict) else {}

    async def update_settings(self, **kwargs: Any) -> dict[str, Any]:
        result = await self._request("PUT", API_SETTINGS, dict(kwargs))
        return result if isinstance(result, dict) else {}

    async def get_panels(self) -> list[Any]:
        response = await self._request("GET", API_PANELS)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return response.get("panels", [])
        return []

    async def get_panel(self, panel_id: str) -> dict[str, Any]:
        result = await self._request("GET", f"{API_PANELS}/{quote(panel_id, safe='')}")
        return result if isinstance(result, dict) else {}

    async def create_panel(self, panel_id: str, panel: dict[str, Any]) -> dict[str, Any]:
        payload = dict(panel)
        payload["id"] = panel_id
        result = await self._request("POST", API_PANELS, payload)
        return result if isinstance(result, dict) else {}

    async def update_panel(self, panel_id: str, panel: dict[str, Any]) -> dict[str, Any]:
        result = await self._request(
            "PUT", f"{API_PANELS}/{quote(panel_id, safe='')}", dict(panel)
        )
        return result if isinstance(result, dict) else {}

    async def delete_panel(self, panel_id: str) -> dict[str, Any]:
        result = await self._request("DELETE", f"{API_PANELS}/{quote(panel_id, safe='')}")
        return result if isinstance(result, dict) else {}

    async def activate_panel(self, panel_id: str) -> dict[str, Any]:
        path = API_PANELS_ACTIVATE.format(panel_id=quote(panel_id, safe=""))
        result = await self._request("POST", path)
        return result if isinstance(result, dict) else {}

    async def get_cameras(self) -> list[Any]:
        response = await self._request("GET", API_CAMERAS)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return response.get("cameras", [])
        return []

    async def create_camera(
        self, name: str, url: str, fullscreen_url: Optional[str] = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, "url": url}
        if fullscreen_url is not None:
            payload["fullscreen_url"] = fullscreen_url
        result = await self._request("POST", API_CAMERAS, payload)
        return result if isinstance(result, dict) else {}

    async def update_camera(
        self, name: str, url: str, fullscreen_url: Optional[str] = None
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, "url": url}
        if fullscreen_url is not None:
            # An explicit empty string clears the optional fullscreen URL.
            payload["fullscreen_url"] = fullscreen_url
        result = await self._request(
            "PUT", f"{API_CAMERAS}/{quote(name, safe='')}", payload
        )
        return result if isinstance(result, dict) else {}

    async def delete_camera(self, name: str) -> dict[str, Any]:
        result = await self._request("DELETE", f"{API_CAMERAS}/{quote(name, safe='')}")
        return result if isinstance(result, dict) else {}

    async def test_camera(self, name: str) -> dict[str, Any]:
        result = await self._request(
            "POST", f"{API_CAMERAS}/{quote(name, safe='')}/test"
        )
        return result if isinstance(result, dict) else {}

    async def reload_config(self) -> dict[str, Any]:
        result = await self._request("POST", API_RELOAD)
        return result if isinstance(result, dict) else {}

    async def test_connection(self) -> bool:
        try:
            await self.get_status()
            return True
        except ViewpieConnectionError:
            return False
