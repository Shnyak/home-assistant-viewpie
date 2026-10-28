"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import ViewpieCoordinator
from .entity import ViewpieEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up viewpie binary sensor entities."""
    coordinator: ViewpieCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        [
            ViewpiePausedBinarySensor(coordinator),
            ViewpieScreenOffBinarySensor(coordinator),
            ViewpieFullscreenBinarySensor(coordinator),
        ]
    )


class ViewpieBinarySensorBase(ViewpieEntity, BinarySensorEntity):
    """Base binary sensor reading a boolean key from the status payload."""

    _key: str
    _default: bool = False

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{self._key}"

    @property
    def is_on(self) -> bool | None:
        """Return True when the flag is set in the latest status data."""
        if not self.coordinator.last_update_success:
            return None
        return bool(self.status.get(self._key, self._default))


class ViewpiePausedBinarySensor(ViewpieBinarySensorBase):
    """Indicates that the camera wall is manually paused."""

    _attr_name = "Paused"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _key = "paused"


class ViewpieScreenOffBinarySensor(ViewpieBinarySensorBase):
    """Indicates that the HDMI output / screen is switched off."""

    _attr_name = "Screen off"
    _attr_device_class = BinarySensorDeviceClass.POWER
    _key = "screen_off"


class ViewpieFullscreenBinarySensor(ViewpieEntity, BinarySensorEntity):
    """Indicates that a camera is displayed in fullscreen mode."""

    _attr_name = "Fullscreen mode"
    _attr_icon = "mdi:fullscreen"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the fullscreen binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_fullscreen_active"

    @property
    def is_on(self) -> bool | None:
        """Return True while any camera is shown fullscreen."""
        if not self.coordinator.last_update_success:
            return None
        return self.status.get("fullscreen_camera") is not None
