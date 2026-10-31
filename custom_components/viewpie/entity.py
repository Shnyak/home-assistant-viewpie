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
        port = coordinator.entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._attr_suggested_entity_id = f"{DOMAIN}_{slugify(host)}"

        # This is the Viewpie device, not the HA integration package.
        # Only publish a software version when the device API reports one.
        status = coordinator.data or {}
        software_version = (
            status.get("software_version")
            or status.get("viewpie_version")
            or status.get("version")
        )
        device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": f"{DEFAULT_NAME} ({host})",
            "manufacturer": "Viewpie",
            "model": "Viewpie camera wall",
            "configuration_url": f"http://{host}:{port}",
        }
        if software_version:
            device_info["sw_version"] = str(software_version)
        self._attr_device_info = DeviceInfo(**device_info)

    @property
    def status(self) -> dict:
        """Latest status payload."""
        return self.coordinator.data or {}
