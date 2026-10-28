"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api_client import ViewpieApiClient
from .const import DOMAIN, OPTION_GRID, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


class ViewpieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that polls viewpie status and exposes control helpers."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: ViewpieApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch the latest status from the device every update interval."""
        try:
            data = await self.client.get_status()
        except Exception as err:  # noqa: BLE001 - convert to UpdateFailed
            raise UpdateFailed(f"Error polling viewpie status: {err}") from err

        # Enrich with dynamic lists so entities can build option sets.
        try:
            panels = await self.client.get_panels()
            data["panels"] = [
                p.get("id") if isinstance(p, dict) else p
                for p in panels
                if (p.get("id") if isinstance(p, dict) else p)
            ]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not refresh panel list: %s", err)
            data.setdefault("panels", [])

        # Guarantee the active panel is present in the option list, otherwise
        # HA's select entity would report an unknown state (current_option must
        # be one of options).
        active_panel = data.get("active_panel")
        if active_panel and str(active_panel) not in data["panels"]:
            data["panels"] = [*data["panels"], str(active_panel)]

        try:
            cameras = await self.client.get_cameras()
            data["cameras"] = [
                c.get("name") if isinstance(c, dict) else c
                for c in cameras
                if (c.get("name") if isinstance(c, dict) else c)
            ]
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("Could not refresh camera list: %s", err)
            data.setdefault("cameras", [])

        return data

    # ------------------------------------------------------------------
    # Control helpers (called by entities and services)
    # ------------------------------------------------------------------
    async def async_pause(self) -> None:
        """Pause the camera wall."""
        await self.client.pause()
        await self.async_request_refresh()

    async def async_resume(self) -> None:
        """Resume the camera wall."""
        await self.client.resume()
        await self.async_request_refresh()

    async def async_grid(self) -> None:
        """Return to grid layout."""
        await self.client.grid()
        await self.async_request_refresh()

    async def async_fullscreen(
        self, camera: str, duration: Optional[int] = None
    ) -> None:
        """Show a camera full-screen (with optional auto-return timer)."""
        if camera == OPTION_GRID:
            await self.async_grid()
            return
        await self.client.fullscreen(camera, duration)
        await self.async_request_refresh()

    async def async_activate_panel(self, panel_id: str) -> None:
        """Activate a panel/scene by id."""
        await self.client.activate_panel(panel_id)
        await self.async_request_refresh()

    async def async_update_settings(self, **kwargs: Any) -> None:
        """Push setting changes to the device."""
        await self.client.update_settings(**kwargs)
        await self.async_request_refresh()

    async def async_reload_config(self) -> None:
        """Reload the viewpie configuration on the device."""
        await self.client.reload_config()
        await self.async_request_refresh()
