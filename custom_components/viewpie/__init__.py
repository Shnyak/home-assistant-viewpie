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
        runtime: ViewpieRuntimeData | None = hass.data[DOMAIN].pop(entry.entry_id, None)
        if runtime is not None:
            await runtime.client.async_close()
    if not hass.data.get(DOMAIN):
        for service in (
            SERVICE_FULLSCREEN, SERVICE_SWITCH_PANEL, SERVICE_SET_SPACING,
            "manage_camera", "test_camera", "manage_panel",
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
    return unload_ok


def _iter_coordinators(hass: HomeAssistant, call: ServiceCall):
    """Yield coordinators for all loaded entries or a single targeted entry."""
    entry_id = call.data.get(ATTR_ENTRY_ID)
    for runtime in hass.data.get(DOMAIN, {}).values():
        if entry_id is None or runtime.coordinator.entry.entry_id == entry_id:
            yield runtime.coordinator


def _register_services(hass: HomeAssistant) -> None:
    """Register Viewpie control and management services once."""
    if hass.services.has_service(DOMAIN, SERVICE_FULLSCREEN):
        return

    async def refresh(coordinator: ViewpieCoordinator) -> None:
        await coordinator.async_request_refresh()

    async def handle_fullscreen(call: ServiceCall) -> None:
        for coordinator in _iter_coordinators(hass, call):
            await coordinator.async_fullscreen(
                call.data[ATTR_CAMERA], call.data.get(ATTR_DURATION)
            )

    async def handle_switch_panel(call: ServiceCall) -> None:
        for coordinator in _iter_coordinators(hass, call):
            await coordinator.async_activate_panel(call.data[ATTR_PANEL])

    async def handle_set_spacing(call: ServiceCall) -> None:
        for coordinator in _iter_coordinators(hass, call):
            await coordinator.async_update_settings(spacing=int(call.data[ATTR_SPACING]))

    async def handle_manage_camera(call: ServiceCall) -> None:
        operation = call.data["operation"]
        name = call.data["name"]
        for coordinator in _iter_coordinators(hass, call):
            client = coordinator.client
            if operation == "create":
                await client.create_camera(name, call.data["url"], call.data.get("fullscreen_url"))
            elif operation == "update":
                await client.update_camera(name, call.data["url"], call.data.get("fullscreen_url"))
            else:
                await client.delete_camera(name)
            await refresh(coordinator)

    async def handle_test_camera(call: ServiceCall) -> None:
        for coordinator in _iter_coordinators(hass, call):
            result = await coordinator.client.test_camera(call.data["name"])
            _LOGGER.info(
                "RTSP test for camera %s: ok=%s latency_ms=%s error=%s",
                call.data["name"], result.get("ok"), result.get("latency_ms"),
                result.get("error"),
            )
            await refresh(coordinator)

    async def handle_manage_panel(call: ServiceCall) -> None:
        operation = call.data["operation"]
        panel_id = call.data["panel_id"]
        panel = {
            key: call.data[key]
            for key in ("name", "layout", "viewports")
            if key in call.data
        }
        for coordinator in _iter_coordinators(hass, call):
            client = coordinator.client
            if operation == "create":
                await client.create_panel(panel_id, panel)
            elif operation == "update":
                await client.update_panel(panel_id, panel)
            else:
                await client.delete_panel(panel_id)
            await refresh(coordinator)

    entry_field = vol.Optional(ATTR_ENTRY_ID): cv.string
    hass.services.async_register(
        DOMAIN, SERVICE_FULLSCREEN, handle_fullscreen,
        schema=vol.Schema({
            vol.Required(ATTR_CAMERA): cv.string,
            vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            entry_field,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SWITCH_PANEL, handle_switch_panel,
        schema=vol.Schema({
            vol.Required(ATTR_PANEL): cv.string,
            vol.Optional(ATTR_ENTRY_ID): cv.string,
        }),
    )
    hass.services.async_register(
        DOMAIN, SERVICE_SET_SPACING, handle_set_spacing,
        schema=vol.Schema({
            vol.Required(ATTR_SPACING): vol.All(vol.Coerce(int), vol.Range(min=0, max=20)),
            vol.Optional(ATTR_ENTRY_ID): cv.string,
        }),
    )

    hass.services.async_register(
        DOMAIN, "manage_camera", handle_manage_camera,
        schema=vol.Schema({
            vol.Required("operation"): vol.In(["create", "update", "delete"]),
            vol.Required("name"): cv.string,
            vol.Optional("url"): cv.string,
            vol.Optional("fullscreen_url"): cv.string,
            vol.Optional(ATTR_ENTRY_ID): cv.string,
        }),
    )
    hass.services.async_register(
        DOMAIN, "test_camera", handle_test_camera,
        schema=vol.Schema({
            vol.Required("name"): cv.string,
            vol.Optional(ATTR_ENTRY_ID): cv.string,
        }),
    )
    hass.services.async_register(
        DOMAIN, "manage_panel", handle_manage_panel,
        schema=vol.Schema({
            vol.Required("operation"): vol.In(["create", "update", "delete"]),
            vol.Required("panel_id"): cv.string,
            vol.Optional("name"): cv.string,
            vol.Optional("layout"): cv.string,
            vol.Optional("viewports"): list,
            vol.Optional(ATTR_ENTRY_ID): cv.string,
        }),
    )
    _LOGGER.debug("Registered Viewpie control and camera/panel management services")
