"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api_client import ViewpieConnectionError
from .const import DOMAIN, OPTION_GRID
from .coordinator import ViewpieCoordinator
from .entity import ViewpieEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up viewpie select entities."""
    coordinator: ViewpieCoordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    async_add_entities(
        [
            ViewpiePanelSelect(coordinator),
            ViewpieFullscreenSelect(coordinator),
        ]
    )


class _LastOption(ExtraStoredData):
    """Serializable extra restore-state data for select entities."""

    def __init__(self, option: str | None) -> None:
        """Initialize."""
        self.option = option

    def as_dict(self) -> dict[str, Any]:
        """Return a dict representation of this extra data."""
        return {"option": self.option}

    @classmethod
    def from_dict(cls, serialized: dict[str, Any]) -> "_LastOption":
        """Restore from a serialized dict."""
        return cls(serialized.get("option"))


class ViewpieSelectBase(ViewpieEntity, RestoreEntity, SelectEntity):
    """Common logic for viewpie select entities.

    ``options`` is a *cached property* in Home Assistant's select component,
    so it must be recomputed explicitly whenever new coordinator data arrives
    (e.g. panels or cameras were added/removed on the device). The last
    user-selected option is remembered via ``RestoreEntity`` so the select
    keeps a sensible state even while the device is temporarily unavailable.
    """

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the base select entity."""
        super().__init__(coordinator)
        self._base_unique_id = coordinator.entry.entry_id
        self._last_option: str | None = None

    # -- options handling ------------------------------------------------

    def _build_options(self) -> list[str]:
        """Return the current option list. Implemented by subclasses."""
        raise NotImplementedError

    @property
    def options(self) -> list[str]:  # type: ignore[override]
        """Return the set of selectable options (bypasses HA caching)."""
        return self._build_options()

    @property
    def state_attributes(self) -> dict[str, Any]:
        """Expose ``current_option`` explicitly.

        The stock select component puts ``options`` into *capability*
        attributes only and relies on the entity state for the selection.
        Because we override the cached ``options``/``current_option``
        properties with dynamic ones, we publish the current option as a
        regular state attribute as well so automations and UI templates can
        read it reliably.
        """
        attrs: dict[str, Any] = {}
        current = self.current_option
        if current is not None:
            attrs["current_option"] = current
        return attrs

    def _handle_coordinator_update(self) -> None:
        """Drop stale cached select properties on every poll."""
        self.__dict__.pop("options", None)
        self.__dict__.pop("current_option", None)
        super()._handle_coordinator_update()

    # -- state / restore -------------------------------------------------

    @property
    def current_option(self) -> str | None:
        """Return the currently selected option."""
        raise NotImplementedError

    async def async_added_to_hass(self) -> None:
        """Restore the last selected option when added to hass."""
        await super().async_added_to_hass()
        if (extra := await self.async_get_last_extra_data()) is not None:
            self._last_option = extra.as_dict().get("option")

    @property
    def extra_restore_state_data(self) -> _LastOption:
        """Return the option to persist for the next HA start."""
        return _LastOption(self.current_option)

    async def async_will_remove_from_hass(self) -> None:
        """Persist the current option before removal."""
        if self.available:
            self._last_option = self.current_option
        await super().async_will_remove_from_hass()

    # -- helpers ---------------------------------------------------------

    def _remembered_valid_option(self) -> str | None:
        """Return the restored option if it is still a valid choice."""
        if self._last_option and self._last_option in self.options:
            return self._last_option
        return None

    def _record_selection(self, option: str) -> None:
        """Remember the option chosen by the user."""
        self._last_option = option


class ViewpiePanelSelect(ViewpieSelectBase):
    """Select the active panel (scene)."""

    _attr_name = "Panel"
    _attr_icon = "mdi:view-dashboard"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the panel select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._base_unique_id}_panel"

    def _build_options(self) -> list[str]:
        """Panel ids reported by the device."""
        return [str(p) for p in self.status.get("panels", [])]

    @property
    def current_option(self) -> str | None:
        """Currently active panel id."""
        panel = self.status.get("active_panel")
        if panel is not None and str(panel) in self.options:
            return str(panel)
        return self._remembered_valid_option()

    async def async_select_option(self, option: str) -> None:
        """Activate the chosen panel."""
        try:
            await self.coordinator.async_activate_panel(option)
        except ViewpieConnectionError as err:
            raise HomeAssistantError(
                f"Failed to activate panel '{option}': {err}"
            ) from err
        self._record_selection(option)


class ViewpieFullscreenSelect(ViewpieSelectBase):
    """Select a camera to display full-screen, or return to grid."""

    _attr_name = "Fullscreen camera"
    _attr_icon = "mdi:fullscreen"

    def __init__(self, coordinator: ViewpieCoordinator) -> None:
        """Initialize the fullscreen select."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._base_unique_id}_fullscreen"

    def _build_options(self) -> list[str]:
        """Grid plus all configured cameras."""
        cameras = [str(c) for c in self.status.get("cameras", [])]
        return [OPTION_GRID, *cameras]

    @property
    def current_option(self) -> str:
        """Currently shown camera, or Grid when none is fullscreened."""
        fullscreen = self.status.get("fullscreen_camera")
        if fullscreen is not None and str(fullscreen) in self.options:
            return str(fullscreen)
        return OPTION_GRID

    async def async_select_option(self, option: str) -> None:
        """Show the camera fullscreen or return to the grid."""
        try:
            if option == OPTION_GRID:
                await self.coordinator.async_grid()
            else:
                await self.coordinator.async_fullscreen(option)
        except ViewpieConnectionError as err:
            raise HomeAssistantError(
                f"Failed to switch view to '{option}': {err}"
            ) from err
        self._record_selection(option)
