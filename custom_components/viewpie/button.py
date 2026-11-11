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
from .const import CONF_RESTART_TOKEN, DOMAIN
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
            ViewpieRestartButton(coordinator),
            ViewpieCheckUpdatesButton(coordinator),
            ViewpieInstallUpdateButton(coordinator),
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


class ViewpieRestartButton(ViewpieEntity, ButtonEntity):
    """Safely request a Raspberry Pi reboot through the token-protected API."""

    _attr_name = "Перезагрузить Raspberry Pi"
    _attr_icon = "mdi:restart"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_restart_host"

    @property
    def _restart_token(self) -> str:
        return str(
            self.coordinator.entry.options.get(CONF_RESTART_TOKEN)
            or self.coordinator.entry.data.get(CONF_RESTART_TOKEN)
            or ""
        ).strip()

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and bool(self._restart_token)
            and bool(self.status.get("restart_available", False))
        )

    async def async_press(self) -> None:
        try:
            if not self._restart_token:
                raise HomeAssistantError("Сначала задайте токен перезагрузки в настройках интеграции Viewpie")
            await self.coordinator.client.restart_host(self._restart_token)
        except ViewpieConnectionError as err:
            raise HomeAssistantError(f"Не удалось перезагрузить Raspberry Pi: {err}") from err


class ViewpieCheckUpdatesButton(ViewpieEntity, ButtonEntity):
    """Manually check GitHub for a compatible Viewpie release."""

    _attr_name = "Проверить обновления Viewpie"
    _attr_icon = "mdi:cloud-search"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_check_updates"

    async def async_press(self) -> None:
        try:
            await self.coordinator.async_check_update()
        except ViewpieConnectionError as err:
            raise HomeAssistantError(f"Не удалось проверить обновления Viewpie: {err}") from err


class ViewpieInstallUpdateButton(ViewpieEntity, ButtonEntity):
    """Install the latest release after an explicit confirmation in the card."""

    _attr_name = "Установить обновление Viewpie"
    _attr_icon = "mdi:package-down"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry.entry_id}_install_update"

    @property
    def _restart_token(self) -> str:
        return str(
            self.coordinator.entry.options.get(CONF_RESTART_TOKEN)
            or self.coordinator.entry.data.get(CONF_RESTART_TOKEN)
            or ""
        ).strip()

    @property
    def available(self) -> bool:
        return (
            self.coordinator.last_update_success
            and bool(self._restart_token)
            and bool(self.status.get("can_install", False))
        )

    async def async_press(self) -> None:
        try:
            if not self._restart_token:
                raise HomeAssistantError("Сначала укажите токен Viewpie в настройках интеграции")
            await self.coordinator.async_install_update(self._restart_token)
        except ViewpieConnectionError as err:
            raise HomeAssistantError(f"Не удалось запустить обновление Viewpie: {err}") from err
