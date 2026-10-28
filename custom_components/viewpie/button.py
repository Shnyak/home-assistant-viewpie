"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
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
    """Set up viewpie button entities."""
    coordinator: ViewpieCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        [
            ViewpieGridButton(coordinator),
            ViewpieReloadButton(coordinator),
        ]
    )


class ViewpieGridButton(ViewpieEntity, ButtonEntity):
    """Button to return the wall to grid layout."""

    _attr_name = "Return to grid"
    _attr_icon = "mdi:grid"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the grid button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_grid"

    async def async_press(self) -> None:
        """Press the button: switch back to grid view."""
        try:
            await self.coordinator.async_grid()
        except ViewpieConnectionError as err:
            raise HomeAssistantError(f"Failed to return to grid: {err}") from err


class ViewpieReloadButton(ViewpieEntity, ButtonEntity):
    """Button to reload the viewpie configuration on the device."""

    _attr_name = "Reload config"
    _attr_icon = "mdi:reload"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the reload button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_reload"

    async def async_press(self) -> None:
        """Press the button: ask viewpie to reload its config file."""
        try:
            await self.coordinator.async_reload_config()
        except ViewpieConnectionError as err:
            raise HomeAssistantError(
                f"Failed to reload viewpie config: {err}"
            ) from err
