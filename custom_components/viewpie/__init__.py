"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import aiohttp

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
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


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Register the bundled Lovelace layout editor as a static resource."""
    editor_path = Path(__file__).parent / "www" / "viewpie-layout-editor.js"
    if not editor_path.is_file():
        return True

    url_path = "/viewpie/viewpie-layout-editor.js"
    if hasattr(hass.http, "async_register_static_paths"):
        from homeassistant.components.http import StaticPathConfig

        await hass.http.async_register_static_paths(
            [
                StaticPathConfig(
                    url_path=url_path,
                    path=str(editor_path),
                    cache_headers=False,
                )
            ]
        )
    else:
        # Compatibility with Home Assistant versions before async static paths.
        hass.http.register_static_path(
            url_path, str(editor_path), cache_headers=False
        )
    return True
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
    runtime: ViewpieRuntimeData | None = None
    try:
        await client.async_init()
        coordinator = ViewpieCoordinator(hass, client, entry)
        await coordinator.async_config_entry_first_refresh()

        # Platforms read their coordinator from hass.data during setup.
        # Register runtime data BEFORE forwarding platforms; the old order
        # caused every platform setup to fail with KeyError and left the
        # configured device with no entities.
        runtime = ViewpieRuntimeData(client, coordinator)
        entry.runtime_data = runtime
        hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        _register_services(hass)
    except Exception:
        if runtime is not None:
            hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        await client.async_close()
        raise
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
            "manage_camera", "test_camera", "manage_panel", "apply_config",
        ):
            if hass.services.has_service(DOMAIN, service):
                hass.services.async_remove(DOMAIN, service)
    return unload_ok


def _iter_coordinators(hass: HomeAssistant, call: ServiceCall, *, management: bool = False):
    """Return selected coordinators; never fan out mutations across devices."""
    runtimes = list(hass.data.get(DOMAIN, {}).values())
    entry_id = call.data.get(ATTR_ENTRY_ID)
    if entry_id is not None:
        selected = [runtime.coordinator for runtime in runtimes if runtime.coordinator.entry.entry_id == entry_id]
        if not selected:
            raise HomeAssistantError(f"No loaded Viewpie config entry matches entry_id {entry_id!r}")
        return iter(selected)
    if management and len(runtimes) > 1:
        raise HomeAssistantError("entry_id is required for camera/panel management when multiple Viewpie devices are configured")
    return iter(runtime.coordinator for runtime in runtimes)


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

    async def handle_apply_config(call: ServiceCall) -> None:
        """Submit a complete YAML candidate to the authenticated Pi apply bridge."""
        bridge_url = call.data["bridge_url"].strip().rstrip("/")
        token = call.data["bridge_token"].strip()
        candidate = call.data["config_yaml"]
        parsed = urlparse(bridge_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.query or parsed.fragment:
            raise HomeAssistantError("bridge_url must be an absolute HTTP(S) base URL without query or fragment")
        hostname = (parsed.hostname or "").lower()
        is_loopback = hostname in ("localhost", "127.0.0.1", "::1")
        if parsed.scheme != "https" and not is_loopback:
            raise HomeAssistantError("HTTPS is required for a non-loopback apply bridge URL")
        if not token:
            raise HomeAssistantError("bridge_token must not be empty")
        if not candidate.strip():
            raise HomeAssistantError("config_yaml must not be empty")
        if len(candidate.encode("utf-8")) > 1024 * 1024:
            raise HomeAssistantError("config_yaml exceeds the 1 MiB limit")
        timeout = aiohttp.ClientTimeout(total=180)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    bridge_url + "/apply",
                    data=candidate.encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/yaml",
                    },
                ) as response:
                    payload = await response.json(content_type=None)
                    result = payload if isinstance(payload, dict) else {"output": str(payload)}
                    status = str(result.get("status", "ERROR"))
                    message = str(result.get("output") or result.get("message") or status)
                    if response.status == 200 and status == "OK":
                        _LOGGER.warning("Transactional Viewpie config apply succeeded; %s", message)
                        return
                    if status == "ROLLED_BACK":
                        raise HomeAssistantError(
                            "Viewpie rejected the new configuration and restored the previous YAML. " + message
                        )
                    raise HomeAssistantError(
                        f"Transactional Viewpie apply failed ({status}, HTTP {response.status}). {message}"
                    )
        except HomeAssistantError:
            raise
        except (aiohttp.ClientError, TimeoutError, ValueError) as err:
            raise HomeAssistantError(f"Could not reach the transactional apply bridge: {err}") from err

    async def handle_manage_camera(call: ServiceCall) -> None:
        operation = call.data["operation"]
        name = call.data["name"].strip()
        if not name:
            raise HomeAssistantError("Camera name must not be empty")
        if operation in ("create", "update"):
            url = call.data.get("url", "").strip()
            if not url:
                raise HomeAssistantError("url is required for camera create/update")
        else:
            url = ""
        fullscreen_url = call.data.get("fullscreen_url")
        for coordinator in _iter_coordinators(hass, call, management=True):
            client = coordinator.client
            if operation == "create":
                await client.create_camera(name, url, fullscreen_url)
            elif operation == "update":
                await client.update_camera(name, url, fullscreen_url)
            else:
                await client.delete_camera(name)
            await refresh(coordinator)

    async def handle_test_camera(call: ServiceCall) -> None:
        # Testing a camera is device-specific too; don't silently test the same
        # name on every configured Viewpie instance.
        for coordinator in _iter_coordinators(hass, call, management=True):
            result = await coordinator.client.test_camera(call.data["name"])
            _LOGGER.info(
                "RTSP test for camera %s: ok=%s latency_ms=%s error=%s",
                call.data["name"], result.get("ok"), result.get("latency_ms"),
                "<details omitted>" if result.get("error") else None,
            )
            await refresh(coordinator)

    async def handle_manage_panel(call: ServiceCall) -> None:
        operation = call.data["operation"]
        panel_id = call.data["panel_id"].strip()
        if not panel_id:
            raise HomeAssistantError("panel_id must not be empty")
        panel = {
            key: call.data[key]
            for key in ("name", "layout", "viewports")
            if key in call.data
        }
        if operation in ("create", "update"):
            missing = [key for key in ("name", "layout", "viewports") if key not in panel]
            if missing:
                raise HomeAssistantError(f"{operation} panel requires: " + ", ".join(missing))
            if not str(panel["name"]).strip() or not str(panel["layout"]).strip():
                raise HomeAssistantError("Panel name and layout must not be empty")
            if not isinstance(panel["viewports"], list):
                raise HomeAssistantError("viewports must be a list")
        for coordinator in _iter_coordinators(hass, call, management=True):
            client = coordinator.client
            if operation == "create":
                await client.create_panel(panel_id, panel)
            elif operation == "update":
                await client.update_panel(panel_id, panel)
            else:
                await client.delete_panel(panel_id)
            await refresh(coordinator)

    hass.services.async_register(
        DOMAIN, SERVICE_FULLSCREEN, handle_fullscreen,
        schema=vol.Schema({
            vol.Required(ATTR_CAMERA): cv.string,
            vol.Optional(ATTR_DURATION): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
            vol.Optional(ATTR_ENTRY_ID): cv.string,
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
        DOMAIN, "apply_config", handle_apply_config,
        schema=vol.Schema({
            vol.Required("bridge_url"): vol.All(cv.string, vol.Length(min=1, max=2048)),
            vol.Required("bridge_token"): vol.All(cv.string, vol.Length(min=1, max=512)),
            vol.Required("config_yaml"): vol.All(cv.string, vol.Length(min=1, max=1048576)),
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
