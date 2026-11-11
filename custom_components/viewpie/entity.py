"""
Viewpie Home Assistant entities.
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import slugify
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_PORT, DEFAULT_NAME, DEFAULT_PORT, DOMAIN
from .coordinator import ViewpieCoordinator


class ViewpieEntity(CoordinatorEntity[ViewpieCoordinator]):
    """Base entity shared by all Viewpie platforms."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator)
        host = coordinator.entry.data.get(CONF_HOST, "viewpie")
        self._host = host
        self._port = coordinator.entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._attr_suggested_entity_id = f"{DOMAIN}_{slugify(host)}"
        # hass.states does not include Home Assistant's config_entry_id.
        # Expose a stable integration-specific marker for the bundled Lovelace cards.
        self._attr_extra_state_attributes = {
            "viewpie_entry_id": coordinator.entry.entry_id,
        }

    @property
    def device_info(self) -> DeviceInfo:
        """Return live device metadata, including the latest reported software version.

        This supplies the latest version when the entity is added. Subsequent
        version changes are synchronized explicitly by the coordinator through
        the Home Assistant device registry.
        """
        status = self.coordinator.data or {}
        software_version = (
            status.get("software_version")
            or status.get("viewpie_version")
            or status.get("version")
        )
        device_info: dict[str, object] = {
            "identifiers": {(DOMAIN, self.coordinator.entry.entry_id)},
            "name": f"{DEFAULT_NAME} ({self._host})",
            "manufacturer": "Viewpie",
            "model": "Viewpie camera wall",
            "configuration_url": f"http://{self._host}:{self._port}",
        }
        if software_version:
            device_info["sw_version"] = str(software_version)
        return DeviceInfo(**device_info)

    @property
    def status(self) -> dict:
        """Latest status payload."""
        return self.coordinator.data or {}
