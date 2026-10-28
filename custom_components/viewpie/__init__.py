"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api_client import ViewpieApiClient as _ViewpieApiClient
from .const import (
    ATTR_CAMERA,
    ATTR_DURATION,
    ATTR_ENTRY_ID,
    ATTR_PANEL,
    ATTR_SPACING,
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
    PLATFORMS,
    SERVICE_FULLSCREEN,
    SERVICE_SET_SPACING,
    SERVICE_SWITCH_PANEL,
)
from .coordinator import ViewpieCoordinator

_LOGGER = logging.getLogger(__name__)

# Re-export at package level; tests may patch this attribute
# (``custom_components.viewpie.ViewpieApiClient``) and both the config flow
# and entry setup resolve the class through it at call time.
ViewpieApiClient = _ViewpieApiClient


class ViewpieRuntimeData:
    """Runtime data stored per config entry."""

    def __init__(self, client: _ViewpieApiClient, coordinator: ViewpieCoordinator):
        self.client = client
        self.coordinator = coordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Viewpie from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data.get(CONF_PORT, DEFAULT_PORT)
    api_key: str | None = entry.data.get(CONF_API_KEY) or None

    # Looked up at call time via the package attribute so tests can patch
    # ``custom_components.viewpie.ViewpieApiClient`` and have both the
    # config flow and entry setup use the patched class.
    import custom_components.viewpie as vp

    client = vp.ViewpieApiClient(host, port, api_key)
    await client.async_init()

    coordinator = ViewpieCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    runtime = ViewpieRuntimeData(client, coordinator)
    entry.runtime_data = runtime
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _register_services(hass)

    _LOGGER.info("Viewpie integration set up for %s:%s", host, port)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        runtime: ViewpieRuntimeData | None = hass.data[DOMAIN].pop(
            entry.entry_id, None
        )
        if runtime is not None:
            await runtime.client.async_close()

    if not hass.data.get(DOMAIN):
        _LOGGER.debug("No viewpie entries left; removing services")
        for service in (SERVICE_FULLSCREEN, SERVICE_SWITCH_PANEL, SERVICE_SET_SPACING):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)

    return unload_ok


def _iter_coordinators(hass: HomeAssistant, call: ServiceCall):
    """Yield coordinators for all loaded entries (or a single targeted one)."""
    entry_id = call.data.get(ATTR_ENTRY_ID)
    for runtime in hass.data.get(DOMAIN, {}).values():
        if entry_id is None or runtime.coordinator.entry.entry_id == entry_id:
            yield runtime.coordinator


def _register_services(hass: HomeAssistant) -> None:
    """Register viewpie management services (idempotent)."""

    if hass.services.has_service(DOMAIN, SERVICE_FULLSCREEN):
        return

    async def handle_fullscreen(call: ServiceCall) -> None:
        camera: str = call.data[ATTR_CAMERA]
        duration: int | None = call.data.get(ATTR_DURATION)
        for coordinator in _iter_coordinators(hass, call):
            await coordinator.async_fullscreen(camera, duration)

    async def handle_switch_panel(call: ServiceCall) -> None:
        panel: str = call.data[ATTR_PANEL]
        for coordinator in _iter_coordinators(hass, call):
            await coordinator.async_activate_panel(panel)

    async def handle_set_spacing(call: ServiceCall) -> None:
        spacing: int = int(call.data[ATTR_SPACING])
        for coordinator in _iter_coordinators(hass, call):
            await coordinator.async_update_settings(spacing=spacing)

    hass.services.async_register(
        DOMAIN,
        SERVICE_FULLSCREEN,
        handle_fullscreen,
        schema=vol.Schema(
            {
                vol.Required(ATTR_CAMERA): cv.string,
                vol.Optional(ATTR_DURATION): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=3600)
                ),
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SWITCH_PANEL,
        handle_switch_panel,
        schema=vol.Schema(
            {
                vol.Required(ATTR_PANEL): cv.string,
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SPACING,
        handle_set_spacing,
        schema=vol.Schema(
            {
                vol.Required(ATTR_SPACING): vol.All(
                    vol.Coerce(int), vol.Range(min=0, max=20)
                ),
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )

    _LOGGER.debug("Registered viewpie services: fullscreen, switch_panel, set_spacing")
