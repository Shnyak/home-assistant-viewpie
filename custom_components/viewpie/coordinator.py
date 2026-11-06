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
        # Fetch full panel definitions for the visual editor. These objects contain
        # layout/viewport metadata only; camera source URLs are not included here.
        panel_details: dict[str, dict[str, Any]] = {}
        for panel_id in data["panels"]:
            try:
                panel = await self.client.get_panel(panel_id)
                if isinstance(panel, dict) and panel:
                    panel_details[panel_id] = panel
            except Exception as err:
                _LOGGER.debug("Could not fetch panel %s details: %s", panel_id, err)
        data["panel_details"] = panel_details

        # Keep the registered Viewpie device version in sync with every poll.
        # The initial DeviceInfo is only used when entities are first added;
        # later API version changes must explicitly update the device registry.
        software_version = data.get("software_version") or data.get("viewpie_version") or data.get("version")
        if software_version:
            from homeassistant.helpers import device_registry as dr

            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get_device({(DOMAIN, self.entry.entry_id)})
            if device is not None and device.sw_version != str(software_version):
                device_registry.async_update_device(
                    device.id, sw_version=str(software_version)
                )
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
    async def async_grid(self) -> None:
        """Leave fullscreen mode and return to the currently active panel."""
        await self.client.grid()
        await self.async_refresh()

    async def _async_ensure_screen_on(self) -> None:
        """Wake the HDMI output before changing the visible camera or panel."""
        if bool((self.data or {}).get("paused", False)):
            await self.client.resume()
            await self.async_request_refresh()

    async def async_fullscreen(self, camera: str, duration: Optional[int] = None) -> None:
        """Wake the screen if needed, then show a camera or return to the grid."""
        if camera == OPTION_GRID:
            await self.async_grid()
            return
        await self._async_ensure_screen_on()
        await self.client.fullscreen(camera, duration)
        await self.async_refresh()

    async def async_activate_panel(self, panel_id: str) -> None:
        """Wake the screen if needed, then activate the requested panel."""
        await self._async_ensure_screen_on()
        # Viewpie retains the selected panel as a background scene in fullscreen.
        # Leave fullscreen before activating a panel so the visible output and
        # Home Assistant entity state cannot disagree.
        await self.client.grid()
        await self.client.activate_panel(panel_id)
        await self.async_refresh()
    async def async_update_settings(self, **kwargs: Any) -> None: await self.client.update_settings(**kwargs); await self.async_request_refresh()
    async def async_reload_config(self) -> None: await self.client.reload_config(); await self.async_request_refresh()
