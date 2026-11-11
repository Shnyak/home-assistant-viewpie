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
from homeassistant.helpers.entity import slugify
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
    cameras = coordinator.data.get("cameras", []) if coordinator.data else []
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
            ViewpieLatestVersionSensor(coordinator),
            ViewpieUpdateAvailableSensor(coordinator),
            ViewpieDecoderStatusSensor(coordinator),
            ViewpieHardwareDecoderCountSensor(coordinator),
            ViewpieSoftwareDecoderCountSensor(coordinator),
            ViewpieUnknownDecoderCountSensor(coordinator),
            *[
                ViewpieCameraDecoderSensor(coordinator, camera)
                for camera in cameras
                if isinstance(camera, str) and camera
            ],
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
    """Number of streams currently decoding frames."""

    _attr_name = "Active streams"
    _attr_icon = "mdi:video"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _key = "active_streams"
    _default = 0

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.last_update_success:
            return None
        entries = _decoder_entries(self.coordinator)
        if entries:
            # In persistent-pool mode this counts every warmed camera that is
            # actually decoding, not just cameras visible in the selected panel.
            return sum(item.get("state") == "active" for item in entries)
        return self.status.get(self._key, self._default)


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


def _decoder_entries(coordinator: ViewpieCoordinator) -> list[dict[str, Any]]:
    """Return validated per-camera decoder telemetry from Viewpie."""
    status = (coordinator.data or {}).get("decoder_status", [])
    if not isinstance(status, list):
        return []
    return [
        item for item in status
        if isinstance(item, dict) and isinstance(item.get("camera"), str)
    ]


def _decoder_counts(coordinator: ViewpieCoordinator) -> dict[str, int]:
    """Count cameras currently producing frames through each decoder path."""
    entries = _decoder_entries(coordinator)
    active = [item for item in entries if item.get("state") == "active"]
    unresolved = [
        item for item in entries
        if item.get("state") != "paused"
        and (
            item.get("state") != "active"
            or item.get("mode") not in ("hardware", "software")
        )
    ]
    return {
        "hardware": sum(item.get("mode") == "hardware" for item in active),
        "software": sum(item.get("mode") == "software" for item in active),
        "unknown": len(unresolved),
    }


class ViewpieDecoderStatusSensor(ViewpieEntity, SensorEntity):
    """Summary of actual decoder paths, with details for every camera."""

    _attr_name = "Decoder status"
    _attr_icon = "mdi:chip"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_decoder_status"

    @property
    def native_value(self) -> str:
        counts = _decoder_counts(self.coordinator)
        total = sum(counts.values())
        if total == 0:
            return "No active decoder data"
        return (
            f"{counts['hardware']} hardware / "
            f"{counts['software']} software / "
            f"{counts['unknown']} unknown"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        counts = _decoder_counts(self.coordinator)
        cameras = {}
        for item in _decoder_entries(self.coordinator):
            camera = item["camera"]
            cameras[camera] = {
                "decoder": item.get("decoder"),
                "mode": item.get("mode"),
                "state": item.get("state", "unknown"),
                "fallback_reason": item.get("fallback_reason"),
            }
        return {
            "hardware_count": counts["hardware"],
            "software_count": counts["software"],
            "unknown_count": counts["unknown"],
            "cameras": cameras,
            "viewpie_entry_id": self.coordinator.entry.entry_id,
        }


class ViewpieDecoderCountSensor(ViewpieEntity, SensorEntity):
    """Base class for live hardware/software decoder counts."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _mode: str

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_decoder_{self._mode}"

    @property
    def native_value(self) -> int:
        return _decoder_counts(self.coordinator)[self._mode]


class ViewpieHardwareDecoderCountSensor(ViewpieDecoderCountSensor):
    _attr_name = "Hardware decoders"
    _attr_icon = "mdi:chip"
    _mode = "hardware"


class ViewpieSoftwareDecoderCountSensor(ViewpieDecoderCountSensor):
    _attr_name = "Software decoders"
    _attr_icon = "mdi:cpu-64-bit"
    _mode = "software"


class ViewpieUnknownDecoderCountSensor(ViewpieDecoderCountSensor):
    _attr_name = "Unknown decoder status"
    _attr_icon = "mdi:help-circle-outline"
    _mode = "unknown"


class ViewpieCameraDecoderSensor(ViewpieEntity, SensorEntity):
    """Actual decoder and runtime state for one configured camera."""

    _attr_icon = "mdi:video-wireless"

    def __init__(self, coordinator: ViewpieCoordinator, camera: str) -> None:
        super().__init__(coordinator)
        self._camera = camera
        self._attr_name = f"{camera} decoder"
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_camera_decoder_{slugify(camera)}"
        )

    def _camera_status(self) -> dict[str, Any]:
        for item in _decoder_entries(self.coordinator):
            if item["camera"] == self._camera:
                return item
        return {"camera": self._camera, "state": "unknown"}

    @property
    def native_value(self) -> str:
        status = self._camera_status()
        mode = status.get("mode") or "unknown"
        state = status.get("state") or "unknown"
        return f"{mode} ({state})"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        status = self._camera_status()
        return {
            "camera": self._camera,
            "decoder": status.get("decoder"),
            "mode": status.get("mode"),
            "state": status.get("state", "unknown"),
            "fallback_reason": status.get("fallback_reason"),
            "viewpie_entry_id": self.coordinator.entry.entry_id,
        }


class ViewpieLatestVersionSensor(ViewpieSensorBase):
    """Latest compatible release discovered by an explicit update check."""

    _attr_name = "Latest version"
    _attr_icon = "mdi:cloud-download"
    _key = "latest_version"
    _default = "Не проверено"


class ViewpieUpdateAvailableSensor(ViewpieSensorBase):
    """Whether a newer compatible release is available."""

    _attr_name = "Update available"
    _attr_icon = "mdi:update"
    _key = "update_available"

    @property
    def native_value(self) -> str:
        if self.status.get("update_check_status") == "error":
            return "Ошибка проверки"
        if not self.coordinator.last_update_success:
            return "Неизвестно"
        if "update_available" not in self.status:
            return "Не проверено"
        return "Да" if self.status.get("update_available") else "Нет"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "latest_version": self.status.get("latest_version"),
            "installed_version": self.status.get("installed_version"),
            "architecture": self.status.get("architecture"),
            "can_install": bool(self.status.get("can_install", False)),
            "package_available": bool(self.status.get("package_available", False)),
            "checksum_available": bool(self.status.get("checksum_available", False)),
            "release_url": self.status.get("release_url"),
            "release_notes": self.status.get("release_notes"),
            "checked_at": self.status.get("update_checked_at"),
            "check_message": self.status.get("update_check_message"),
            "viewpie_entry_id": self.coordinator.entry.entry_id,
        }
