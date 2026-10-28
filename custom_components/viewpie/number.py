"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client import ViewpieConnectionError
from .const import DOMAIN
from .coordinator import ViewpieCoordinator
from .entity import ViewpieEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up viewpie number entities."""
    coordinator: ViewpieCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        [
            ViewpieSpacingNumber(coordinator),
            ViewpieRotationIntervalNumber(coordinator),
            ViewpieFullscreenTimeoutNumber(coordinator),
        ]
    )


class ViewpieNumberBase(ViewpieEntity, NumberEntity):
    """Common behaviour for setting-backed number entities."""

    _setting_key: str
    _min_value: float
    _max_value: float
    _step_value: float
    _default_value: float

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_{self._setting_key}"
        )
        self._attr_native_min_value = self._min_value
        self._attr_native_max_value = self._max_value
        self._attr_native_step = self._step_value
        self._attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> float:
        """Current value from the device status/settings."""
        value = self.status.get(self._setting_key, self._default_value)
        try:
            return float(value)
        except (TypeError, ValueError):
            return self._default_value

    async def async_set_native_value(self, value: float) -> None:
        """Push the new value to the device settings."""
        try:
            await self.coordinator.async_update_settings(
                **{self._setting_key: int(value)}
            )
        except ViewpieConnectionError as err:
            raise HomeAssistantError(
                f"Failed to update {self._setting_key}: {err}"
            ) from err


class ViewpieSpacingNumber(ViewpieNumberBase):
    """Spacing (divider thickness) between camera tiles, in pixels."""

    _attr_name = "Camera spacing"
    _attr_icon = "mdi:grid"
    _attr_native_unit_of_measurement = "px"
    _setting_key = "spacing"
    _min_value = 0
    _max_value = 20
    _step_value = 1
    _default_value = 1


class ViewpieRotationIntervalNumber(ViewpieNumberBase):
    """Automatic camera rotation interval, in seconds."""

    _attr_name = "Rotation interval"
    _attr_icon = "mdi:rotate-3d-variant"
    _attr_native_unit_of_measurement = "s"
    _setting_key = "rotation_interval"
    _min_value = 5
    _max_value = 3600
    _step_value = 5
    _default_value = 20


class ViewpieFullscreenTimeoutNumber(ViewpieNumberBase):
    """Auto-return timeout of fullscreen mode, in seconds."""

    _attr_name = "Fullscreen timeout"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "s"
    _setting_key = "fullscreen_timeout"
    _min_value = 10
    _max_value = 3600
    _step_value = 10
    _default_value = 600
