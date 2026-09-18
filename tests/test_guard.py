"""A leak alert that latches, reaches people, and clears only on an override."""

from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from .conftest import broken_phone, override, phone, setup, valves

NOTIFICATIONS = "custom_components.water_guard.guard.persistent_notification"


def leak(hass):
    return hass.states.get("binary_sensor.water_leak")


async def test_leak_alerts_everyone_and_latches(hass, entry):
    kari = phone(hass, "person.kari", "Kari phone")
    ola = phone(hass, "person.ola", "Ola phone")
    events = []
    hass.bus.async_listen("water_guard_event", lambda event: events.append(event.data))
    with patch(NOTIFICATIONS) as notifications:
        await setup(hass, entry)
        assert leak(hass).state == "off"
        hass.states.async_set("binary_sensor.sink_leak", "on", {"friendly_name": "Sink"})
        await hass.async_block_till_done()
    assert leak(hass).state == "on"
    assert leak(hass).attributes["sensors"] == ["binary_sensor.sink_leak"]
    assert leak(hass).attributes["notified"] == {"person.kari": "sent", "person.ola": "sent"}
    notifications.async_create.assert_called_once()
    assert "Sink" in notifications.async_create.call_args.args[1]
    assert [len(kari), len(ola)] == [1, 1]
    assert kari[0]["title"] == "Water leak detected"
    assert kari[0]["data"]["tag"].startswith("water_guard_")
    assert kari[0]["data"]["priority"] == "high"
    assert [event["type"] for event in events] == ["leak"]
    # Drying out does not clear the alert.
    hass.states.async_set("binary_sensor.sink_leak", "off")
    await hass.async_block_till_done()
    assert leak(hass).state == "on"
    assert leak(hass).attributes["wet_sensors"] == []


async def test_a_second_sensor_updates_the_alert(hass, entry):
    kari = phone(hass, "person.kari", "Kari phone")
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on", {"friendly_name": "Sink"})
        await hass.async_block_till_done()
        hass.states.async_set("binary_sensor.sink_leak", "off", {"friendly_name": "Sink"})
        hass.states.async_set("binary_sensor.sink_leak", "on", {"friendly_name": "Sink"})
        await hass.async_block_till_done()
        assert len(kari) == 1, "the same sensor again is not a new alert"
        hass.states.async_set("binary_sensor.boiler_leak", "on", {"friendly_name": "Boiler"})
        await hass.async_block_till_done()
    assert len(kari) == 2
    assert "Sink" in kari[1]["message"] and "Boiler" in kari[1]["message"]
    assert kari[0]["data"]["tag"] == kari[1]["data"]["tag"], "replaces the earlier push"


async def test_who_could_not_be_reached_is_published(hass, entry):
    broken_phone(hass, "person.kari", "Kari phone")
    hass.states.async_set("person.ola", "home", {"device_trackers": ["device_tracker.router"]})
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
    assert leak(hass).attributes["notified"] == {"person.kari": "failed", "person.ola": "no_app"}


async def test_every_phone_of_a_person_is_alerted(hass, entry):
    first = phone(hass, "person.kari", "Kari phone")
    second = phone(hass, "person.kari", "Kari tablet")
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
    assert [len(first), len(second)] == [1, 1]


async def test_bokmal_alert(hass, entry):
    kari = phone(hass, "person.kari", "Kari phone")
    await hass.config.async_update(language="nb")
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on", {"friendly_name": "Vask"})
        await hass.async_block_till_done()
    assert kari[0]["title"] == "Vannlekkasje oppdaget"
    assert "Vask" in kari[0]["message"] and "Overstyr" in kari[0]["message"]


async def test_leak_during_downtime_latches_at_start_and_survives_reload(hass, entry):
    kari = phone(hass, "person.kari", "Kari phone")
    hass.states.async_set("binary_sensor.boiler_leak", "on")
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        assert leak(hass).state == "on"
        hass.states.async_set("binary_sensor.boiler_leak", "off")
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert leak(hass).state == "on"
    assert len(kari) == 1, "a reload does not alert again"


async def test_override_opens_the_water_and_clears_the_alert(hass, entry):
    calls = valves(hass)
    kari = phone(hass, "person.kari", "Kari phone")
    hass.states.async_set("valve.main", "closed")  # the KNX leak block shut it
    with patch(NOTIFICATIONS) as notifications:
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
        result = await override(hass)
    assert calls == [("valve.main", "open")]
    assert result["valves"]["status"] == "ok"
    assert result["released"]["sensors"] == ["binary_sensor.sink_leak"]
    assert result["still_wet"] == ["binary_sensor.sink_leak"], "override works while wet"
    assert leak(hass).state == "off"
    notifications.async_dismiss.assert_called_once()
    assert kari[-1] == {"message": "clear_notification", "data": {"tag": kari[0]["data"]["tag"]}}


async def test_failed_override_keeps_the_alert(hass, entry):
    valves(hass, broken={"valve.main"})
    hass.states.async_set("valve.main", "closed")
    with patch(NOTIFICATIONS) as notifications:
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
        with pytest.raises(HomeAssistantError):
            await override(hass)
    assert leak(hass).state == "on"
    assert leak(hass).attributes["last_result"]["valves"] == {"valve.main": "failed"}
    notifications.async_dismiss.assert_not_called()


async def test_override_button_without_valves_just_clears_the_alert(hass, entry):
    hass.config_entries.async_update_entry(entry, options=dict(entry.options) | {"valves": []})
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.water_override_open_water"}, blocking=True
        )
        await hass.async_block_till_done()
    assert leak(hass).state == "off"


async def test_optional_shut_off_closes_and_reports(hass, entry):
    calls = valves(hass)
    kari = phone(hass, "person.kari", "Kari phone")
    hass.config_entries.async_update_entry(
        entry, options=dict(entry.options) | {"close_on_leak": True}
    )
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
    assert calls == [("valve.main", "closed")]
    assert hass.states.get("valve.main").state == "closed"
    assert "The water is shut off" in kari[0]["message"]


async def test_failed_shut_off_says_so(hass, entry):
    valves(hass, broken={"valve.main"})
    kari = phone(hass, "person.kari", "Kari phone")
    hass.config_entries.async_update_entry(
        entry, options=dict(entry.options) | {"close_on_leak": True}
    )
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
    assert "could not be shut off" in kari[0]["message"]
    assert "Main valve" in kari[0]["message"]


async def test_no_shut_off_by_default(hass, entry):
    calls = valves(hass)
    with patch(NOTIFICATIONS):
        await setup(hass, entry)
        hass.states.async_set("binary_sensor.sink_leak", "on")
        await hass.async_block_till_done()
    assert not calls


async def test_unavailable_sensors_are_visible(hass, entry):
    hass.states.async_set("binary_sensor.boiler_leak", "unavailable")
    await setup(hass, entry)
    assert leak(hass).attributes["unavailable_sensors"] == ["binary_sensor.boiler_leak"]
    assert leak(hass).state == "off"
