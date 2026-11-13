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
    API_RESTART,
    API_RESUME,
    API_SETTINGS,
    API_STATUS,
    API_UPDATE_CHECK,
    API_UPDATE_STATUS,
    API_UPDATE_INSTALL,
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
        extra_headers: Optional[dict[str, str]] = None,
        request_timeout: Optional[ClientTimeout] = None,
    ) -> Any:
        if self._session is None:
            await self.async_init()
        assert self._session is not None
        url = f"{self._base_url}{path}"
        headers = self._headers()
        if extra_headers:
            headers.update(extra_headers)
        _LOGGER.debug("viewpie request: %s %s", method, url)
        try:
            async with self._session.request(
                method, url, json=data, headers=headers, timeout=request_timeout
            ) as response:
                text = await response.text()
                if response.status >= 400:
                    detail = text.strip()
                    try:
                        payload = json.loads(text) if text else {}
                        if isinstance(payload, dict):
                            detail = str(payload.get("error") or payload.get("message") or detail)
                    except (json.JSONDecodeError, ValueError):
                        pass
                    if not (
                        method == "GET"
                        and path == API_UPDATE_STATUS
                        and response.status == 404
                    ):
                        _LOGGER.error(
                            "viewpie request rejected (%s %s): HTTP %s: %s",
                            method, url, response.status, detail or response.reason,
                        )
                    raise ViewpieConnectionError(
                        f"Viewpie returned HTTP {response.status}: {detail or response.reason}"
                    )
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

    async def check_update(self) -> dict[str, Any]:
        """Fetch latest architecture-matched Viewpie release metadata."""
        result = await self._request("GET", API_UPDATE_CHECK)
        return result if isinstance(result, dict) else {}

    async def get_camera_snapshot(self, name: str) -> bytes:
        """Fetch a one-shot JPEG snapshot for the layout editor."""
        if self._session is None:
            await self.async_init()
        assert self._session is not None
        url = f"{self._base_url}/api/cameras/{quote(name, safe='')}/snapshot"
        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                timeout=ClientTimeout(total=15),
            ) as response:
                if response.status >= 400:
                    detail = (await response.text()).strip()
                    raise ViewpieConnectionError(
                        f"Viewpie snapshot request returned HTTP {response.status}: {detail[:400]}"
                    )
                content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                if content_type != "image/jpeg":
                    raise ViewpieConnectionError(
                        f"Viewpie snapshot endpoint returned unexpected content type: {content_type or 'missing'}"
                    )
                data = await response.read()
                if len(data) < 4 or not data.startswith(b"\\xff\\xd8") or not data.endswith(b"\\xff\\xd9"):
                    raise ViewpieConnectionError("Viewpie returned an invalid JPEG snapshot")
                return data
        except aiohttp.ClientError as err:
            raise ViewpieConnectionError(f"Snapshot request to {url} failed: {err}") from err
        except TimeoutError as err:
            raise ViewpieConnectionError(f"Snapshot request to {url} timed out") from err
    async def get_update_status(self) -> dict[str, Any]:
        """Fetch the current updater phase and bounded diagnostic journal."""
        result = await self._request("GET", API_UPDATE_STATUS)
        return result if isinstance(result, dict) else {}

    async def install_update(self, token: str) -> dict[str, Any]:
        """Request installation of the latest checksum-verified release."""
        result = await self._request(
            "POST", API_UPDATE_INSTALL,
            extra_headers={"Authorization": f"Bearer {token}"},
        )
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
        result = await self._request(
            "POST", API_FULLSCREEN, data, request_timeout=ClientTimeout(total=15)
        )
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

    async def reorder_panels(self, order: list[str]) -> dict[str, Any]:
        """Persist the exact order of all configured panels."""
        result = await self._request("PUT", f"{API_PANELS}/order", {"order": list(order)})
        return result if isinstance(result, dict) else {}

    async def get_cameras(self) -> list[Any]:
        response = await self._request("GET", API_CAMERAS)
        if isinstance(response, list):
            return response
        if isinstance(response, dict):
            return response.get("cameras", [])
        return []

    async def create_camera(
        self, name: str, url: str, fullscreen_url: Optional[str] = None, decoder: str = "auto"
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, "url": url, "decoder": decoder}
        if fullscreen_url is not None:
            payload["fullscreen_url"] = fullscreen_url
        result = await self._request("POST", API_CAMERAS, payload)
        return result if isinstance(result, dict) else {}

    async def update_camera(
        self, name: str, url: str, fullscreen_url: Optional[str] = None, decoder: str = "auto"
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"name": name, "url": url, "decoder": decoder}
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

    async def restart_host(self, token: str) -> dict[str, Any]:
        """Request a protected host reboot with the dedicated restart token."""
        result = await self._request(
            "POST", API_RESTART, extra_headers={"Authorization": f"Bearer {token}"}
        )
        return result if isinstance(result, dict) else {}

    async def test_connection(self) -> bool:
        try:
            await self.get_status()
            return True
        except ViewpieConnectionError:
            return False
