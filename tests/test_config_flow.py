"""Setup and settings run through Home Assistant's real flow manager."""

from homeassistant import data_entry_flow

from .conftest import OPTIONS, setup


async def test_setup_creates_an_entry(hass):
    flow = await hass.config_entries.flow.async_init("water_guard", context={"source": "user"})
    assert flow["type"] == data_entry_flow.FlowResultType.FORM
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {"name": "Cabin", "leak_sensors": ["binary_sensor.sink_leak"], "people": ["person.kari"]},
    )
    assert flow["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert flow["title"] == "Cabin"
    assert flow["options"] == {
        "leak_sensors": ["binary_sensor.sink_leak"],
        "people": ["person.kari"],
        "valves": [],
        "close_on_leak": False,
    }


async def test_setup_validation(hass):
    flow = await hass.config_entries.flow.async_init("water_guard", context={"source": "user"})
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"], {"name": "Water", "leak_sensors": []}
    )
    assert flow["errors"] == {"leak_sensors": "no_sensors"}
    flow = await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        {"name": "Water", "leak_sensors": ["binary_sensor.sink_leak"], "close_on_leak": True},
    )
    assert flow["errors"] == {"close_on_leak": "close_without_valves"}


async def test_settings_change_only_on_submit(hass, entry):
    await setup(hass, entry)
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    assert flow["step_id"] == "init"
    hass.config_entries.options.async_abort(flow["flow_id"])
    assert dict(entry.options) == OPTIONS
    flow = await hass.config_entries.options.async_init(entry.entry_id)
    flow = await hass.config_entries.options.async_configure(
        flow["flow_id"],
        {
            "leak_sensors": ["binary_sensor.boiler_leak"],
            "people": [],
            "valves": ["switch.water_relay"],
            "close_on_leak": True,
        },
    )
    assert flow["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["valves"] == ["switch.water_relay"]
    assert entry.options["close_on_leak"] is True
    assert hass.states.get("binary_sensor.water_leak") is not None


async def test_action_descriptions_load(hass, entry):
    from homeassistant.helpers.service import async_get_all_descriptions

    await setup(hass, entry)
    descriptions = await async_get_all_descriptions(hass)
    assert set(descriptions["water_guard"]) == {"override"}
