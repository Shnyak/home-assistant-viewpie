"""Full-stack test: config flow, setup, entities and services in real HA."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.helpers import entity_registry as er
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError

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
    registry = er.async_get(hass)
    screen_entity_id = registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_pause"
    )
    assert screen_entity_id is not None
    assert hass.states.get(screen_entity_id) is not None


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
    entry = await _add_entry(hass)
    states = {s.entity_id: s for s in hass.states.async_all()}
    registry = er.async_get(hass)
    screen_entity_id = registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_pause"
    )
    assert screen_entity_id is not None

    sw = states[screen_entity_id]
    # The switch represents the physical screen: on = screen on,
    # off = screen off (paused in the Viewpie API).
    assert sw.state == "on"
    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": sw.entity_id}, blocking=True
    )
    mock_client.pause.assert_awaited()
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": sw.entity_id}, blocking=True
    )
    mock_client.resume.assert_awaited()

    panel_entity_id = registry.async_get_entity_id(
        "select", DOMAIN, f"{entry.entry_id}_panel"
    )
    assert panel_entity_id is not None
    sel = hass.states.get(panel_entity_id)
    assert sel is not None
    assert "inside" in sel.attributes["options"]
    assert sel.attributes["current_option"] == "outside"
    assert sel.state == "outside"
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": sel.entity_id, "option": "night"}, blocking=True,
    )
    mock_client.activate_panel.assert_awaited_with("night")

    fullscreen_entity_id = registry.async_get_entity_id(
        "select", DOMAIN, f"{entry.entry_id}_fullscreen"
    )
    assert fullscreen_entity_id is not None
    fs = hass.states.get(fullscreen_entity_id)
    assert fs is not None
    assert fs.attributes["options"][0] == "Grid"
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": fs.entity_id, "option": "pool"}, blocking=True,
    )
    mock_client.fullscreen.assert_awaited_with("pool", None)

    spacing_entity_id = registry.async_get_entity_id(
        "number", DOMAIN, f"{entry.entry_id}_spacing"
    )
    assert spacing_entity_id is not None
    num = hass.states.get(spacing_entity_id)
    assert num is not None
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
    assert sensor.attributes["viewpie_entry_id"] == entry.entry_id
    bs = states[f"binary_sensor.{DOMAIN}_viewpi_paused"]
    assert bs.attributes["viewpie_entry_id"] == entry.entry_id
    assert bs.state == "off"
    bfs = states[f"binary_sensor.{DOMAIN}_viewpi_fullscreen_mode"]
    assert bfs.state == "off"



async def test_panel_and_camera_entities_are_exclusive_when_controlled_directly(hass: HomeAssistant, mock_client):
    entry = await _add_entry(hass)
    registry = er.async_get(hass)
    panel_entity_id = registry.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_panel")
    fullscreen_entity_id = registry.async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_fullscreen")
    assert panel_entity_id and fullscreen_entity_id

    # Simulate the Viewpie API reporting the fullscreen camera after selection.
    status = mock_client.get_status.return_value
    status["fullscreen_camera"] = "pool"
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": fullscreen_entity_id, "option": "pool"}, blocking=True,
    )
    assert hass.states.get(fullscreen_entity_id).state == "pool"
    assert hass.states.get(panel_entity_id).state == "unknown"

    # Selecting a panel must leave fullscreen mode first, then activate that panel.
    status["fullscreen_camera"] = None
    status["active_panel"] = "night"
    mock_client.grid.reset_mock()
    mock_client.activate_panel.reset_mock()
    await hass.services.async_call(
        "select", "select_option",
        {"entity_id": panel_entity_id, "option": "night"}, blocking=True,
    )
    mock_client.grid.assert_awaited_once()
    mock_client.activate_panel.assert_awaited_once_with("night")
    assert hass.states.get(panel_entity_id).state == "night"
    assert hass.states.get(fullscreen_entity_id).state == "Grid"


async def test_panel_management_reloads_config_after_successful_write(hass: HomeAssistant, mock_client):
    await _add_entry(hass)
    from unittest.mock import AsyncMock
    mock_client.create_panel = AsyncMock(return_value={})
    await hass.services.async_call(
        DOMAIN, "manage_panel",
        {
            "operation": "create",
            "panel_id": "new_panel",
            "name": "New panel",
            "layout": "a",
            "viewports": [{"slot": "a", "feeds": ["pool"]}],
        },
        blocking=True,
    )
    mock_client.create_panel.assert_awaited_once_with(
        "new_panel",
        {"name": "New panel", "layout": "a", "viewports": [{"slot": "a", "feeds": ["pool"]}]},
    )
    mock_client.reload_config.assert_awaited_once()


async def test_camera_delete_clears_panel_cells_without_duplicate_reload(hass: HomeAssistant, mock_client):
    await _add_entry(hass)
    mock_client.get_panels.return_value = [{"id": "yard"}]
    from unittest.mock import AsyncMock
    mock_client.get_panel = AsyncMock(return_value={
        "id": "yard",
        "panel": {
            "name": "Yard",
            "layout": "a b\nc d",
            "viewports": [
                {"slot": "a", "feeds": ["pool"]},
                {"slot": "b", "feeds": ["yard"]},
            ],
        },
    })
    mock_client.update_panel = AsyncMock(return_value={})
    mock_client.delete_camera = AsyncMock(return_value={})
    await hass.services.async_call(
        DOMAIN, "manage_camera",
        {"operation": "delete", "name": "pool"},
        blocking=True,
    )
    updated = mock_client.update_panel.await_args.args[1]
    assert updated["layout"] == ". b\nc d"
    assert updated["viewports"] == [{"slot": "b", "feeds": ["yard"]}]
    mock_client.delete_camera.assert_awaited_once_with("pool")
    # The Viewpie camera DELETE endpoint already reloads its native renderer.
    # The HA integration must not issue a second reload.
    mock_client.reload_config.assert_not_awaited()


async def test_manage_camera_passes_decoder_preference(hass: HomeAssistant, mock_client):
    await _add_entry(hass)
    from unittest.mock import AsyncMock
    mock_client.create_camera = AsyncMock(return_value={})
    await hass.services.async_call(
        DOMAIN,
        "manage_camera",
        {
            "operation": "create",
            "name": "priority_cam",
            "url": "rtsp://camera/stream",
            "decoder": "hardware",
        },
        blocking=True,
    )
    mock_client.create_camera.assert_awaited_once_with(
        "priority_cam", "rtsp://camera/stream", None, "hardware"
    )


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



async def test_options_flow_opens_and_saves_restart_token(hass: HomeAssistant, mock_client):
    entry = await _add_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={"restart_token": "test-restart-token"}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert entry.options["restart_token"] == "test-restart-token"


async def test_legacy_updater_button_is_blocked_with_bootstrap_instructions(
    hass: HomeAssistant, mock_client
):
    mock_client.check_update.return_value = {
        "installed_version": "0.2.25-fork",
        "latest_version": "0.2.27-fork",
        "update_available": True,
        "can_install": True,
        "package_available": True,
        "checksum_available": True,
    }
    entry = await _add_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator
    await coordinator.async_check_update()
    hass.config_entries.async_update_entry(entry, options={"restart_token": "test-token"})

    from custom_components.viewpie.button import ViewpieInstallUpdateButton

    button = ViewpieInstallUpdateButton(coordinator)
    assert not button.available
    with pytest.raises(HomeAssistantError, match="первого перехода"):
        await button.async_press()
    mock_client.install_update.assert_not_awaited()


async def test_config_flow_e2e_with_mocked_device(hass: HomeAssistant, mock_client):
    """Exercise config flow, setup and entity creation without background sockets."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=E2E_CONFIG
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    screen_entity_id = registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_pause"
    )
    assert screen_entity_id is not None
    assert hass.states.get(screen_entity_id) is not None
    mock_client.get_status.assert_awaited()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    mock_client.async_close.assert_awaited()


async def test_viewpie_update_check_and_install_buttons(hass: HomeAssistant, mock_client):
    # This test exercises the normal post-bootstrap update path.
    mock_client.check_update.return_value = {
        "installed_version": "0.2.27-fork",
        "latest_version": "0.2.28-fork",
        "update_available": True,
        "can_install": True,
        "package_available": True,
        "checksum_available": True,
    }
    entry = await _add_entry(hass)
    coordinator = hass.data[DOMAIN][entry.entry_id].coordinator

    await coordinator.async_check_update()
    mock_client.check_update.assert_awaited_once()
    assert coordinator.data["latest_version"] == "0.2.28-fork"
    assert coordinator.data["can_install"] is True

    hass.config_entries.async_update_entry(entry, options={"restart_token": "test-restart-token"})
    await coordinator.async_request_refresh()
    registry = er.async_get(hass)
    install_entity_id = registry.async_get_entity_id(
        "button", DOMAIN, f"{entry.entry_id}_install_update"
    )
    assert install_entity_id is not None
    entity = hass.data[DOMAIN][entry.entry_id].coordinator
    from custom_components.viewpie.button import ViewpieInstallUpdateButton
    install_button = ViewpieInstallUpdateButton(entity)
    assert install_button.available

    await install_button.async_press()
    mock_client.install_update.assert_awaited_once_with("test-restart-token")
