"""
This file was generated with assistance from Qwen AI.

Related project: https://github.com/snoack/viewpie
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

# Imported via the package ``__init__`` so that patching the module-level
# attribute ``custom_components.viewpie.ViewpieApiClient`` takes effect for
# the config flow as well (single lookup point for the whole integration).
from . import ViewpieApiClient
from .const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_PORT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_API_KEY, default=""): str,
    }
)


async def validate_input(
    host: str, port: int, api_key: str | None
) -> dict[str, Any]:
    """Validate the user input by connecting to the device.

    The client is looked up through the module attribute at call time so
    that tests (and other integrations) can patch
    ``custom_components.viewpie.ViewpieApiClient`` and have the config
    flow use the patched class as well.

    Raises :class:`ViewpieConnectionError` when the device is unreachable.
    """
    # Resolve through the package attribute at call time so patches apply.
    import custom_components.viewpie as vp

    client = vp.ViewpieApiClient(host, port, api_key or None)
    await client.async_init()
    try:
        status = await client.get_status()
        return status if isinstance(status, dict) else {}
    finally:
        await client.async_close()


class ViewpieConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Viewpie."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step: host / port / API key."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input.get(CONF_PORT, DEFAULT_PORT)
            api_key = user_input.get(CONF_API_KEY) or None

            # Enforce uniqueness per host:port.
            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                await validate_input(host, port, api_key)
            except Exception:  # noqa: BLE001 - map any failure to UI error
                _LOGGER.exception(
                    "Could not connect to viewpie at %s:%s", host, port
                )
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Viewpie ({host})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_API_KEY: api_key or "",
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
