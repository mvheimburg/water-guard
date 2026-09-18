"""Water Guard: a latched leak alert that reaches people, and a water override."""

from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_platform_entity_service

from .const import DOMAIN, PLATFORMS
from .guard import Guard

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass, config):
    async_register_platform_entity_service(
        hass,
        DOMAIN,
        "override",
        entity_domain="binary_sensor",
        schema={},
        func="async_override",
        supports_response=SupportsResponse.OPTIONAL,
    )
    return True


async def async_setup_entry(hass, entry):
    guard = Guard(hass, entry)
    await guard.load()
    entry.runtime_data = guard
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    guard.start()
    entry.async_on_unload(entry.add_update_listener(update_options))
    return True


async def update_options(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        entry.runtime_data.stop()
        return True
    return False
