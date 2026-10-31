"""Full-stack test: config flow, setup, entities and services in real HA."""

from unittest.mock import AsyncMock, patch

import pytest
import pytest_socket
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.viewpie.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
)

MOCK_CONFIG = {CONF_HOST: "viewpi", CONF_PORT: 8080, CONF_API_KEY: ""}

E2E_CONFIG = {CONF_HOST: "127.0.0.1", CONF_PORT: 18099, CONF_API_KEY: "testkey"}


async def _add_entry(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    return result["entry"] if "entry" in result else result["result"]


async def test_config_flow_success(hass: HomeAssistant, mock_client):
    entry = await _add_entry(hass)
    assert entry.title == "Viewpie (viewpi)"
    assert entry.data[CONF_HOST] == "viewpi"
    # Coordinator did a first refresh and platforms were set up
    mock_client.get_status.assert_awaited()
    states = {s.entity_id for s in hass.states.async_all()}
    assert f"switch.{DOMAIN}_viewpi_pause" in states, states


async def test_config_flow_cannot_connect(hass: HomeAssistant, mock_client):
    from custom_components.viewpie.api_client import ViewpieConnectionError

    mock_client.get_status = AsyncMock(side_effect=ViewpieConnectionError("boom"))
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_entities_states(hass: HomeAssistant, mock_client):
    await _add_entry(hass)
    states = {s.entity_id: s for s in hass.states.async_all()}

    sw = states[f"switch.{DOMAIN}_viewpi_pause"]
    assert sw.state == "off"
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": sw.entity_id}, blocking=True
    )
    mock_client.pause.assert_awaited()
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": sw.entity_id}, blocking=True
    )
    mock_client.resume.assert_awaited()

    sel = states[f"select.{DOMAIN}_viewpi_panel"]
    assert "inside" in sel.attributes["options"]
    assert sel.attributes["current_option"] == "outside"
    assert sel.state == "outside"
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": sel.entity_id, "option": "night"}, blocking=True,
    )
    mock_client.activate_panel.assert_awaited_with("night")

    fs = states[f"select.{DOMAIN}_viewpi_fullscreen_camera"]
    assert fs.attributes["options"][0] == "Grid"
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": fs.entity_id, "option": "pool"}, blocking=True,
    )
    mock_client.fullscreen.assert_awaited_with("pool", None)

    num = states[f"number.{DOMAIN}_viewpi_camera_spacing"]
    assert float(num.state) == 1.0
    await hass.services.async_call(
        "number", "set_value",
        {"entity_id": num.entity_id, "value": 7}, blocking=True,
    )
    mock_client.update_settings.assert_awaited_with(spacing=7)

    btn = states[f"button.{DOMAIN}_viewpi_return_to_grid"]
    await hass.services.async_call(
        "button", "press", {"entity_id": btn.entity_id}, blocking=True
    )
    mock_client.grid.assert_awaited()

    reload_btn = states[f"button.{DOMAIN}_viewpi_reload_config"]
    await hass.services.async_call(
        "button", "press", {"entity_id": reload_btn.entity_id}, blocking=True
    )
    mock_client.reload_config.assert_awaited()

    sensor = states[f"sensor.{DOMAIN}_viewpi_cpu_temperature"]
    assert sensor.state == "54.3"
    bs = states[f"binary_sensor.{DOMAIN}_viewpi_paused"]
    assert bs.state == "off"
    bfs = states[f"binary_sensor.{DOMAIN}_viewpi_fullscreen_mode"]
    assert bfs.state == "off"


async def test_services_and_unload(hass: HomeAssistant, mock_client):
    entry = await _add_entry(hass)

    await hass.services.async_call(
        DOMAIN, "fullscreen", {"camera": "pool", "duration": 30}, blocking=True
    )
    mock_client.fullscreen.assert_awaited_with("pool", 30)
    await hass.services.async_call(
        DOMAIN, "switch_panel", {"panel": "night"}, blocking=True
    )
    mock_client.activate_panel.assert_awaited_with("night")
    await hass.services.async_call(
        DOMAIN, "set_spacing", {"spacing": 5}, blocking=True
    )
    mock_client.update_settings.assert_awaited_with(spacing=5)

    # Unload cleanly closes the client session
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_client.async_close.assert_awaited()


async def test_config_flow_e2e_with_real_server(hass: HomeAssistant):
    """End-to-end: config flow + setup against a real aiohttp fake device."""
    # This test spins up a *local* fake viewpie device over loopback TCP, so
    # temporarily allow sockets (pytest-socket blocks them by default).
    pytest_socket.enable_socket()
    try:
        await _run_e2e(hass)
    finally:
        pytest_socket.disable_socket()


async def _run_e2e(hass: HomeAssistant):
    import asyncio
    from aiohttp import web

    seen_auth = []

    async def status(req):
        seen_auth.append(req.headers.get("Authorization"))
        return web.json_response({"paused": False})

    app = web.Application()
    app.router.add_get("/api/status", status)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 18099)
    await site.start()
    try:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=E2E_CONFIG
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        entry = hass.config_entries.async_entries(DOMAIN)[0]
        await hass.async_block_till_done()
        states = {s.entity_id for s in hass.states.async_all()}
        assert "switch.viewpie_127_0_0_1_vykliuchenie_ekrana" in states, states
        # Bearer token was sent
        assert seen_auth and seen_auth[0] == "Bearer testkey"
        # Unload closes the session cleanly (no unclosed-session errors)
        assert await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()
    finally:
        await asyncio.sleep(0.1)
        await runner.cleanup()
