"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import slugify
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_HOST, CONF_PORT, DEFAULT_NAME, DEFAULT_PORT, DOMAIN, VERSION
from .coordinator import ViewpieCoordinator


class ViewpieEntity(CoordinatorEntity[ViewpieCoordinator]):
    """Base entity for all viewpie entities.

    Provides a shared device info block and a convenience accessor for the
    latest coordinator data.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        host = coordinator.entry.data.get(CONF_HOST, "viewpie")
        port = coordinator.entry.data.get(CONF_PORT, DEFAULT_PORT)
        # Derive a slug from the host so entity object_ids look like
        # switch.viewpie_pause instead of switch.127_0_0_1_viewpie_pause.
        self._attr_suggested_entity_id = f"{DOMAIN}_{slugify(host)}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry.entry_id)},
            name=f"{DEFAULT_NAME} ({host})",
            manufacturer="viewpie (AI-generated integration)",
            model="viewpie camera wall",
            sw_version=VERSION,
            configuration_url=f"http://{host}:{port}",
        )

    @property
    def status(self) -> dict:
        """Return the latest status payload (empty dict when unavailable)."""
        return self.coordinator.data or {}
