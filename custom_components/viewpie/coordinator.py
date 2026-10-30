from __future__ import annotations
import logging
from typing import Any, Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .api_client import ViewpieApiClient
from .const import DOMAIN, OPTION_GRID, UPDATE_INTERVAL
_LOGGER = logging.getLogger(__name__)

class ViewpieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Viewpie and expose control helpers."""
    config_entry: ConfigEntry
    def __init__(self, hass: HomeAssistant, client: ViewpieApiClient, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}_{entry.entry_id}", update_interval=UPDATE_INTERVAL)
        self.client, self.entry = client, entry
    async def _async_update_data(self) -> dict[str, Any]:
        try: data = await self.client.get_status()
        except Exception as err: raise UpdateFailed(f"Error polling viewpie status: {err}") from err
        try:
            panels = await self.client.get_panels()
            data["panels"] = [str(p.get("id") if isinstance(p, dict) else p) for p in panels if (p.get("id") if isinstance(p, dict) else p)]
        except Exception as err:
            _LOGGER.debug("Could not refresh panel list: %s", err); data.setdefault("panels", [])
        active = data.get("active_panel")
        if active and str(active) not in data["panels"]: data["panels"].append(str(active))
        try:
            cameras = await self.client.get_cameras()
            # Keep DTO runtime fields but never expose RTSP URLs/credentials as HA attributes.
            data["camera_details"] = [c for c in cameras if isinstance(c, dict) and c.get("name")]
            data["cameras"] = [str(c.get("name")) if isinstance(c, dict) else str(c) for c in cameras if (c.get("name") if isinstance(c, dict) else c)]
        except Exception as err:
            _LOGGER.debug("Could not refresh camera list: %s", err); data.setdefault("camera_details", []); data.setdefault("cameras", [])
        return data
    async def async_pause(self) -> None: await self.client.pause(); await self.async_request_refresh()
    async def async_resume(self) -> None: await self.client.resume(); await self.async_request_refresh()
    async def async_grid(self) -> None: await self.client.grid(); await self.async_request_refresh()
    async def async_fullscreen(self, camera: str, duration: Optional[int] = None) -> None:
        if camera == OPTION_GRID: await self.async_grid(); return
        await self.client.fullscreen(camera, duration); await self.async_request_refresh()
    async def async_activate_panel(self, panel_id: str) -> None: await self.client.activate_panel(panel_id); await self.async_request_refresh()
    async def async_update_settings(self, **kwargs: Any) -> None: await self.client.update_settings(**kwargs); await self.async_request_refresh()
    async def async_reload_config(self) -> None: await self.client.reload_config(); await self.async_request_refresh()
