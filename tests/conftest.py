"""Test fixtures for the viewpie integration tests."""

import pytest


pytest_plugins = ["pytest_homeassistant_custom_component"]


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable loading of custom integrations in all tests."""
    yield


@pytest.fixture(name="mock_client")
def mock_client_fixture():
    """Patch ViewpieApiClient with an async mock (no real sessions created)."""
    from unittest.mock import AsyncMock, patch

    def _factory(host, port, api_key=None, session=None):
        """Return a shared mock for every configured host."""
        return inst

    with patch("custom_components.viewpie.ViewpieApiClient", side_effect=_factory) as cls:
        inst = cls.return_value
        inst.async_init = AsyncMock()
        inst.async_close = AsyncMock()
        inst.get_status = AsyncMock(return_value=dict(_STATUS))
        inst.get_panels = AsyncMock(
            return_value=[
                {"id": "inside"},
                {"id": "outside"},
                {"id": "night"},
            ]
        )
        inst.get_cameras = AsyncMock(
            return_value=[{"name": "pool"}, {"name": "yard"}]
        )
        inst.pause = AsyncMock(return_value={})
        inst.resume = AsyncMock(return_value={})
        inst.grid = AsyncMock(return_value={})
        inst.fullscreen = AsyncMock(return_value={})
        inst.activate_panel = AsyncMock(return_value={})
        inst.update_settings = AsyncMock(return_value={})
        inst.reload_config = AsyncMock(return_value={})
        yield inst


_STATUS = {
    "paused": False,
    "pause_off_screen": True,
    "active_panel": "outside",
    "active_panel_name": "Outside",
    "fullscreen_camera": None,
    "screen_off": False,
    "spacing": 1,
    "rotation_interval": 20,
    "fullscreen_timeout": 600,
    "cpu_temp_c": 54.3,
    "active_streams": 6,
    "uptime_seconds": 12345,
}
