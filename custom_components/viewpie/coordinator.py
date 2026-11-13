from __future__ import annotations
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Optional
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_track_time_interval
from .api_client import ViewpieApiClient
from .const import DOMAIN, OPTION_GRID, UPDATE_INTERVAL
_LOGGER = logging.getLogger(__name__)

class ViewpieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll Viewpie and expose control helpers."""
    config_entry: ConfigEntry
    def __init__(self, hass: HomeAssistant, client: ViewpieApiClient, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, config_entry=entry, name=f"{DOMAIN}_{entry.entry_id}", update_interval=UPDATE_INTERVAL)
        self.client, self.entry = client, entry
        self._update_info: dict[str, Any] = {}
        self._last_update_failure: str | None = None
        self._update_journal_unsub = None
        self._update_check_unsub = None
        self._update_journal_poll_attempts = 0
        self._update_install_pending = False
        self._update_install_baseline_started_at = ""
    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.get_status()
        except Exception as err:
            # The updater deliberately restarts the Viewpie API during an
            # installation. Keep the last known entities available instead
            # of making the whole integration unavailable during that window.
            if self._update_install_pending and self.data is not None:
                _LOGGER.debug("Viewpie API is restarting during installation: %s", err)
                return dict(self.data)
            raise UpdateFailed(f"Error polling viewpie status: {err}") from err
        try:
            update_status = await self.client.get_update_status()
            if self._update_install_pending:
                started_at = str(update_status.get("started_at") or "")
                if not started_at or started_at == self._update_install_baseline_started_at:
                    # Ignore the previous run while waiting for the updater
                    # to publish a journal with a new start timestamp.
                    update_status = (self.data or {}).get("update_status", update_status)
                elif update_status.get("status") in ("success", "failed"):
                    self._update_install_pending = False
            data["update_status"] = update_status
            failure = (
                str(update_status.get("error") or update_status.get("message") or "")
                if update_status.get("status") == "failed" else ""
            )
            if failure:
                signature = f"{update_status.get('updated_at', '')}:{failure}"
                if signature != self._last_update_failure:
                    _LOGGER.error(
                        "Viewpie update failed during %s: %s",
                        update_status.get("phase", "unknown"), failure,
                    )
                    self._last_update_failure = signature
            elif update_status.get("status") == "success":
                self._last_update_failure = None
        except Exception as err:
            _LOGGER.debug("Could not refresh Viewpie update journal: %s", err)
            data["update_status"] = (self.data or {}).get("update_status", {})
        try:
            settings = await self.client.get_settings()
            if isinstance(settings, dict):
                data.update(settings)
        except Exception as err:
            _LOGGER.debug("Could not refresh Viewpie settings: %s", err)
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
        current_version = data.get("software_version")
        if current_version and self._update_info.get("latest_version") == str(current_version):
            self._update_info.update({
                "installed_version": str(current_version),
                "update_available": False,
                "can_install": False,
            })
        if self._update_info:
            data.update(self._update_info)
        return data

    def async_start_update_checks(self) -> None:
        """Check GitHub once at startup and then every six hours."""
        if self._update_check_unsub is not None:
            return
        self._update_check_unsub = async_track_time_interval(
            self.hass, self._async_periodic_update_check, timedelta(hours=6)
        )
        self.hass.async_create_task(self._async_periodic_update_check(None))

    def async_stop_update_checks(self) -> None:
        if self._update_check_unsub is not None:
            self._update_check_unsub()
            self._update_check_unsub = None

    async def _async_periodic_update_check(self, _now) -> None:
        if self._update_install_pending:
            return
        try:
            await self.async_check_update()
        except Exception as err:
            _LOGGER.warning("Automatic Viewpie update check failed: %s", err)

    async def async_check_update(self) -> dict[str, Any]:
        """Check GitHub and retain the latest result for manual and scheduled checks."""
        checked_at = datetime.now(timezone.utc).isoformat()
        try:
            info = await self.client.check_update()
        except Exception as err:
            self._update_info = {
                **self._update_info,
                "update_check_status": "error",
                "update_check_message": str(err),
                "update_checked_at": checked_at,
            }
            await self.async_request_refresh()
            raise
        self._update_info = {
            **info,
            "update_check_status": "checked",
            "update_check_message": "",
            "update_checked_at": checked_at,
        }
        await self.async_request_refresh()
        return dict(self._update_info)

    def async_start_update_journal_polling(self) -> None:
        """Poll the update log every two seconds while an install is starting/running."""
        if self._update_journal_unsub is not None:
            return
        self._update_journal_poll_attempts = 90
        self._update_journal_unsub = async_track_time_interval(
            self.hass, self._async_poll_update_journal, timedelta(seconds=2)
        )

    def async_stop_update_journal_polling(self) -> None:
        if self._update_journal_unsub is not None:
            self._update_journal_unsub()
            self._update_journal_unsub = None

    async def _async_poll_update_journal(self, _now) -> None:
        try:
            update_status = await self.client.get_update_status()
            started_at = str(update_status.get("started_at") or "")
            if self._update_install_pending and (
                not started_at or started_at == self._update_install_baseline_started_at
            ):
                # The API may come back before the updater has written its new
                # journal. Do not re-publish the previous installation log.
                self._update_journal_poll_attempts -= 1
            else:
                data = dict(self.data or {})
                data["update_status"] = update_status
                self.async_set_updated_data(data)
                status = str(update_status.get("status") or "unknown")
                if status == "running":
                    self._update_journal_poll_attempts = 90
                elif status in ("success", "failed"):
                    self._update_install_pending = False
                    self.async_stop_update_journal_polling()
                    return
                else:
                    self._update_journal_poll_attempts -= 1
        except Exception as err:
            _LOGGER.debug("Could not poll Viewpie updater journal: %s", err)
            self._update_journal_poll_attempts -= 1
        if self._update_journal_poll_attempts <= 0:
            self._update_install_pending = False
            self.async_stop_update_journal_polling()

    async def async_install_update(self, token: str) -> dict[str, Any]:
        """Start installation through the restricted backend updater."""
        previous = (self.data or {}).get("update_status", {})
        previous = previous if isinstance(previous, dict) else {}
        self._update_install_baseline_started_at = str(previous.get("started_at") or "")
        self._update_install_pending = True
        # Clear the stale journal in coordinator state immediately, before
        # the request can restart the remote API or interrupt HA polling.
        data = dict(self.data or {})
        data["update_status"] = {
            **previous,
            "status": "starting",
            "phase": "request",
            "message": "Home Assistant requested a new Viewpie installation",
            "error": "",
            "log": "",
        }
        self.async_set_updated_data(data)
        self.async_start_update_journal_polling()
        try:
            result = await self.client.install_update(token)
        except Exception as err:
            self._update_install_pending = False
            _LOGGER.exception("Could not start Viewpie update")
            data = dict(self.data or {})
            timestamp = datetime.now(timezone.utc).isoformat()
            line = f"[ha-request] {timestamp} ERROR: {err}"
            old_log = str(previous.get("log") or "")
            data["update_status"] = {
                **previous,
                "status": "failed",
                "phase": "ha_request",
                "message": "Home Assistant could not start the update request",
                "error": str(err),
                "updated_at": timestamp,
                "finished_at": timestamp,
                "exit_code": None,
                "log": (old_log + "\n" + line).strip(),
            }
            self.async_set_updated_data(data)
            self.async_stop_update_journal_polling()
            raise
        try:
            await self.async_request_refresh()
        except Exception as err:
            # The worker may restart the API immediately after accepting the
            # request. This does not mean the update itself failed to start.
            _LOGGER.debug("Update started; immediate status refresh was interrupted: %s", err)
        return result

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

    async def async_reorder_panels(self, order: list[str]) -> None:
        """Persist a complete panel order and refresh entity options."""
        await self.client.reorder_panels(order)
        await self.async_refresh()
    async def async_update_settings(self, **kwargs: Any) -> None: await self.client.update_settings(**kwargs); await self.async_request_refresh()
    async def async_reload_config(self) -> None: await self.client.reload_config(); await self.async_request_refresh()
