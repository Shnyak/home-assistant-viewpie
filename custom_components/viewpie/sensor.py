"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
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
    """Set up viewpie sensor entities."""
    coordinator: ViewpieCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        [
            ViewpieCpuTempSensor(coordinator),
            ViewpieActiveStreamsSensor(coordinator),
            ViewpieUptimeSensor(coordinator),
            ViewpieActivePanelSensor(coordinator),
        ]
    )


class ViewpieSensorBase(ViewpieEntity, SensorEntity):
    """Base sensor reading a single key from the status payload."""

    _key: str
    _default: Any = None

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{self._key}"

    @property
    def native_value(self) -> Any:
        """Return the current value from the polled status data."""
        if not self.coordinator.last_update_success:
            return None
        return self.status.get(self._key, self._default)


class ViewpieCpuTempSensor(ViewpieSensorBase):
    """CPU temperature of the Raspberry Pi running viewpie."""

    _attr_name = "CPU temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _key = "cpu_temp_c"


class ViewpieActiveStreamsSensor(ViewpieSensorBase):
    """Number of active RTSP streams."""

    _attr_name = "Active streams"
    _attr_icon = "mdi:video"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _key = "active_streams"
    _default = 0


class ViewpieUptimeSensor(ViewpieSensorBase):
    """Device uptime in seconds."""

    _attr_name = "Uptime"
    _attr_icon = "mdi:timer"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _key = "uptime_seconds"
    _default = 0


class ViewpieActivePanelSensor(ViewpieSensorBase):
    """Name of the currently active panel/scene."""

    _attr_name = "Active panel"
    _attr_icon = "mdi:view-dashboard"
    _key = "active_panel_name"
