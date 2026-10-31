"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up viewpie switch entities."""
    coordinator: ViewpieCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        [
            ViewpiePauseSwitch(coordinator),
            ViewpiePauseOffScreenSwitch(coordinator),
        ]
    )


class ViewpiePauseSwitch(ViewpieEntity, SwitchEntity):
    """Switch the camera wall screen off / on."""

    _attr_name = "Выключение экрана"
    _attr_icon = "mdi:pause-circle"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the pause switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pause"

    @property
    def is_on(self) -> bool:
        """Return True when the camera wall screen is off."""
        return bool(self.status.get("paused", False))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the camera wall screen off."""
        try:
            await self.coordinator.async_pause()
        except ViewpieConnectionError as err:
            raise HomeAssistantError(f"Failed to pause viewpie: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the camera wall screen on."""
        try:
            await self.coordinator.async_resume()
        except ViewpieConnectionError as err:
            raise HomeAssistantError(f"Failed to resume viewpie: {err}") from err


class ViewpiePauseOffScreenSwitch(ViewpieEntity, SwitchEntity):
    """Switch for auto-pause when the screen is off (settings-backed)."""

    _attr_name = "Auto-pause when screen off"
    _attr_icon = "mdi:monitor-off"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the setting switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pause_off_screen"

    @property
    def available(self) -> bool:
        """Available only while we have data containing the setting."""
        return self.coordinator.last_update_success and "pause_off_screen" in (
            self.coordinator.data or {}
        )

    @property
    def is_on(self) -> bool:
        """Return True when auto-pause is enabled."""
        return bool(self.status.get("pause_off_screen", True))

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable auto-pause on screen off."""
        try:
            await self.coordinator.async_update_settings(pause_off_screen=True)
        except ViewpieConnectionError as err:
            raise HomeAssistantError(
                f"Failed to update viewpie settings: {err}"
            ) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable auto-pause on screen off."""
        try:
            await self.coordinator.async_update_settings(pause_off_screen=False)
        except ViewpieConnectionError as err:
            raise HomeAssistantError(
                f"Failed to update viewpie settings: {err}"
            ) from err
