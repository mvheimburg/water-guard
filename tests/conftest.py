"""Fixtures running against real Home Assistant."""

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.water_guard.const import DOMAIN  # noqa: F401

OPTIONS = {
    "leak_sensors": ["binary_sensor.sink_leak", "binary_sensor.boiler_leak"],
    "people": ["person.kari", "person.ola"],
    "valves": ["valve.main"],
    "close_on_leak": False,
}


@pytest.fixture(autouse=True)
def enable(enable_custom_integrations):
    yield


@pytest.fixture
def entry(hass):
    entry = MockConfigEntry(domain="water_guard", title="Water", data={}, options=dict(OPTIONS))
    entry.add_to_hass(hass)
    hass.states.async_set("binary_sensor.sink_leak", "off", {"friendly_name": "Sink"})
    hass.states.async_set("binary_sensor.boiler_leak", "off", {"friendly_name": "Boiler"})
    hass.states.async_set("valve.main", "open", {"friendly_name": "Main valve"})
    return entry


def phone(hass, person, device_name):
    """A person tracked by a phone running the Home Assistant app; returns its pushes."""
    app = MockConfigEntry(domain="mobile_app", data={"device_name": device_name})
    app.add_to_hass(hass)
    tracker = er.async_get(hass).async_get_or_create(
        "device_tracker", "mobile_app", device_name, config_entry=app
    )
    trackers = (
        hass.states.get(person).attributes["device_trackers"] if hass.states.get(person) else []
    )
    hass.states.async_set(person, "home", {"device_trackers": [*trackers, tracker.entity_id]})
    pushes = []
    service = "mobile_app_" + device_name.lower().replace(" ", "_")

    async def push(call):
        pushes.append(dict(call.data))

    hass.services.async_register("notify", service, push)
    return pushes


def broken_phone(hass, person, device_name):
    phone(hass, person, device_name)
    service = "mobile_app_" + device_name.lower().replace(" ", "_")

    async def fail(call):
        raise HomeAssistantError("push service down")

    hass.services.async_register("notify", service, fail)


def valves(hass, broken=()):
    """Valve services that move the entity, except those listed as broken."""
    calls = []

    def service(state):
        async def handle(call):
            entity = call.data["entity_id"]
            calls.append((entity, state))
            if entity in broken:
                raise HomeAssistantError("valve offline")
            hass.states.async_set(entity, state)

        return handle

    for name, state in (("open_valve", "open"), ("close_valve", "closed")):
        hass.services.async_register("valve", name, service(state))
    for name, state in (("turn_on", "on"), ("turn_off", "off")):
        hass.services.async_register("switch", name, service(state))
    return calls


async def setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def override(hass):
    response = await hass.services.async_call(
        "water_guard",
        "override",
        {"entity_id": "binary_sensor.water_leak"},
        blocking=True,
        return_response=True,
    )
    await hass.async_block_till_done()
    return response["binary_sensor.water_leak"]
