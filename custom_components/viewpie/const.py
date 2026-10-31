"""
Viewpie Home Assistant integration constants.
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "viewpie"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_API_KEY = "api_key"
DEFAULT_PORT = 8080
DEFAULT_NAME = "Viewpie"

API_STATUS = "/api/status"
API_PAUSE = "/api/pause"
API_RESUME = "/api/resume"
API_GRID = "/api/grid"
API_FULLSCREEN = "/api/fullscreen"
API_SETTINGS = "/api/settings"
API_PANELS = "/api/panels"
API_PANELS_ACTIVATE = "/api/panels/{panel_id}/activate"
API_CAMERAS = "/api/cameras"
API_RELOAD = "/api/reload"

PLATFORMS: list[str] = [
    "switch",
    "select",
    "number",
    "button",
    "sensor",
    "binary_sensor",
]

UPDATE_INTERVAL = timedelta(seconds=10)
REQUEST_TIMEOUT_SECONDS = 10

SERVICE_FULLSCREEN = "fullscreen"
SERVICE_SWITCH_PANEL = "switch_panel"
SERVICE_SET_SPACING = "set_spacing"

ATTR_CAMERA = "camera"
ATTR_DURATION = "duration"
ATTR_PANEL = "panel"
ATTR_SPACING = "spacing"
ATTR_ENTRY_ID = "entry_id"

OPTION_GRID = "Grid"
