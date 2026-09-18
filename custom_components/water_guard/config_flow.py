"""Set up a guarded water supply: leak sensors, who is alerted, and the valves."""

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_CLOSE_ON_LEAK, CONF_LEAK_SENSORS, CONF_PEOPLE, CONF_VALVES, DOMAIN


def entities(**config):
    return selector.EntitySelector(selector.EntitySelectorConfig(multiple=True, **config))


def schema(values, name=None):
    fields = {}
    if name is not None:
        fields[vol.Required("name", default=name)] = selector.TextSelector()
    # Any binary sensor: many leak sensors (KNX among them) carry no moisture class.
    fields[vol.Required(CONF_LEAK_SENSORS, default=values.get(CONF_LEAK_SENSORS, []))] = entities(
        domain="binary_sensor"
    )
    fields[vol.Optional(CONF_PEOPLE, default=values.get(CONF_PEOPLE, []))] = entities(
        domain="person"
    )
    fields[vol.Optional(CONF_VALVES, default=values.get(CONF_VALVES, []))] = entities(
        domain=["valve", "switch"]
    )
    fields[vol.Optional(CONF_CLOSE_ON_LEAK, default=values.get(CONF_CLOSE_ON_LEAK, False))] = (
        selector.BooleanSelector()
    )
    return vol.Schema(fields)


def validate(user_input):
    """Return (options, errors) for everything but the name."""
    sensors = list(user_input.get(CONF_LEAK_SENSORS) or [])
    people = list(user_input.get(CONF_PEOPLE) or [])
    valves = list(user_input.get(CONF_VALVES) or [])
    close = bool(user_input.get(CONF_CLOSE_ON_LEAK))
    if not sensors:
        return None, {CONF_LEAK_SENSORS: "no_sensors"}
    if any(not entity.startswith("binary_sensor.") for entity in sensors):
        return None, {CONF_LEAK_SENSORS: "not_a_sensor"}
    if any(not entity.startswith("person.") for entity in people):
        return None, {CONF_PEOPLE: "not_a_person"}
    if any(entity.split(".", 1)[0] not in {"valve", "switch"} for entity in valves):
        return None, {CONF_VALVES: "not_a_valve"}
    if close and not valves:
        return None, {CONF_CLOSE_ON_LEAK: "close_without_valves"}
    return {
        CONF_LEAK_SENSORS: sensors,
        CONF_PEOPLE: people,
        CONF_VALVES: valves,
        CONF_CLOSE_ON_LEAK: close,
    }, {}


class WaterGuardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            options, errors = validate(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input["name"].strip() or "Water", data={}, options=options
                )
        values = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=schema(values, values.get("name", "Water")),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return WaterGuardOptionsFlow()


class WaterGuardOptionsFlow(config_entries.OptionsFlow):
    """Nothing changes until Submit; closing the dialog keeps the saved settings."""

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            options, errors = validate(user_input)
            if not errors:
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="init",
            data_schema=schema(user_input or dict(self.config_entry.options)),
            errors=errors,
        )
