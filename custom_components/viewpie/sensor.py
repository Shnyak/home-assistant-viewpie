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
            ViewpieCpuLoadSensor(coordinator),
            ViewpieLoadAverageSensor(coordinator),
            ViewpieActiveStreamsSensor(coordinator),
            ViewpieUptimeSensor(coordinator),
            ViewpieActivePanelSensor(coordinator),
            ViewpieSoftwareVersionSensor(coordinator),
            ViewpieSoftwareBuildDateSensor(coordinator),
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


class ViewpieCpuLoadSensor(ViewpieSensorBase):
    """CPU busy percentage on the Raspberry Pi."""

    _attr_name = "CPU usage"
    _attr_icon = "mdi:cpu-64-bit"
    _attr_native_unit_of_measurement = "%"
    _attr_suggested_display_precision = 1
    _attr_state_class = SensorStateClass.MEASUREMENT
    _key = "cpu_load_percent"


class ViewpieLoadAverageSensor(ViewpieSensorBase):
    """One-minute Linux load average."""

    _attr_name = "Load average (1m)"
    _attr_icon = "mdi:chart-line"
    _attr_suggested_display_precision = 2
    _attr_state_class = SensorStateClass.MEASUREMENT
    _key = "load_average_1m"


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


class ViewpieSoftwareVersionSensor(ViewpieSensorBase):
    """Installed Viewpie software version reported by the device API."""

    _attr_name = "Software version"
    _attr_icon = "mdi:package-variant"
    _key = "software_version"


class ViewpieSoftwareBuildDateSensor(ViewpieSensorBase):
    """Source build date of the installed Viewpie binary, not install time."""

    _attr_name = "Software build date"
    _attr_icon = "mdi:calendar-check"
    _key = "software_build_date"
