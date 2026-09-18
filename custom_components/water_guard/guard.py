"""The guard: a latched leak alert, the people it reaches, and the override.

A leak sensor turning on latches an alert: a Home Assistant notification and a
push to each chosen person's phone. The water shut-off itself is usually done
elsewhere (a KNX leak block), so closing the valves here is optional. The
override opens the valves, waits for each to confirm, and clears the alert.
"""

import asyncio
import logging
from copy import deepcopy

from homeassistant.components import persistent_notification
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util
from homeassistant.util import slugify

from .const import CONF_CLOSE_ON_LEAK, CONF_LEAK_SENSORS, CONF_PEOPLE, CONF_VALVES, DOMAIN
from .devices import UNKNOWN, actuate
from .text import text

_LOGGER = logging.getLogger(__name__)
# Water wanted -> (service, reported state) per valve domain.
COMMANDS = {
    "valve": {"open": ("open_valve", "open"), "closed": ("close_valve", "closed")},
    "switch": {"open": ("turn_on", "on"), "closed": ("turn_off", "off")},
}


class Guard:
    def __init__(self, hass, entry):
        self.hass, self.entry = hass, entry
        options = entry.options
        self.sensors = list(options.get(CONF_LEAK_SENSORS, []))
        self.people = list(options.get(CONF_PEOPLE, []))
        self.valves = list(options.get(CONF_VALVES, []))
        self.close_on_leak = bool(options.get(CONF_CLOSE_ON_LEAK, False))
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.leak = None
        self.result = None
        self.lock = asyncio.Lock()
        self.listeners = set()
        self.unsubs = []
        self.stopped = False

    # -- persistence and publication -------------------------------------------

    async def load(self):
        data = await self.store.async_load() or {}
        leak, result = data.get("leak"), data.get("result")
        self.leak = leak if isinstance(leak, dict) and leak.get("sensors") else None
        self.result = result if isinstance(result, dict) else None

    async def save(self):
        await self.store.async_save({"leak": self.leak, "result": self.result})

    async def persist(self):
        try:
            await self.save()
        except Exception:
            _LOGGER.warning("Water Guard could not store its state", exc_info=True)

    @callback
    def notify(self):
        for listener in tuple(self.listeners):
            listener()

    def event(self, kind, **data):
        self.hass.bus.async_fire(
            f"{DOMAIN}_event", {"entry_id": self.entry.entry_id, "type": kind, **data}
        )

    # -- sensors ---------------------------------------------------------------

    def wet(self):
        return [
            entity
            for entity in self.sensors
            if (state := self.hass.states.get(entity)) and state.state == "on"
        ]

    def unavailable_sensors(self):
        return [
            entity
            for entity in self.sensors
            if (state := self.hass.states.get(entity)) is None or state.state in UNKNOWN
        ]

    def names(self, entities):
        return [
            state.name if (state := self.hass.states.get(entity)) else entity for entity in entities
        ]

    # -- lifecycle -------------------------------------------------------------

    def start(self):
        if self.sensors:
            self.unsubs.append(
                async_track_state_change_event(self.hass, self.sensors, self.on_sensor)
            )
        if wet := self.wet():
            # A leak that began while Home Assistant was stopped.
            self.latch(wet)

    def stop(self):
        self.stopped = True
        for unsub in self.unsubs:
            unsub()
        self.unsubs.clear()

    @callback
    def on_sensor(self, event):
        new = event.data["new_state"]
        if new is not None and new.state == "on":
            self.latch([event.data["entity_id"]])
        self.notify()

    # -- the alert -------------------------------------------------------------

    @callback
    def latch(self, sensors):
        if self.stopped:
            return
        known = (self.leak or {}).get("sensors", [])
        if self.leak and set(sensors) <= set(known):
            return
        self.leak = {
            "since": (self.leak or {}).get("since") or dt_util.utcnow().isoformat(),
            "sensors": [*known, *(entity for entity in sensors if entity not in known)],
            "notified": (self.leak or {}).get("notified", {}),
        }
        _LOGGER.warning("Water Guard detected a leak at %s", sensors)
        self.event("leak", since=self.leak["since"], sensors=self.leak["sensors"])
        self.notify()
        self.hass.async_create_task(self.alert())

    async def alert(self):
        """Tell the household, and shut the water if this guard is asked to."""
        if self.stopped or not self.leak:
            return
        result = await self.move("closed", "leak") if self.close_on_leak and self.valves else None
        if not self.leak:
            return  # overridden while the valves were closing
        sensors = ", ".join(self.names(self.leak["sensors"]))
        if result is None:
            key, valves = "leak_alert", ""
        elif result["status"] == "ok":
            key, valves = "leak_closed", ""
        else:
            key = "leak_not_closed"
            valves = ", ".join(self.names(e for e, s in result["valves"].items() if s != "closed"))
        title = text(self.hass, "leak_title")
        message = text(self.hass, key, sensors=sensors, valves=valves)
        persistent_notification.async_create(
            self.hass, message, title=title, notification_id=self.tag
        )
        self.leak["notified"] = await self.push(title, message)
        await self.persist()
        self.notify()

    @property
    def tag(self):
        return f"{DOMAIN}_{self.entry.entry_id}_leak"

    def phones(self, person):
        """The Home Assistant app notify services for a person's tracked phones."""
        state = self.hass.states.get(person)
        registry = er.async_get(self.hass)
        services = []
        for tracker in state.attributes.get("device_trackers", []) if state else []:
            entry = registry.async_get(tracker)
            config_entry = (
                self.hass.config_entries.async_get_entry(entry.config_entry_id)
                if entry and entry.config_entry_id
                else None
            )
            if config_entry is None or config_entry.domain != "mobile_app":
                continue
            service = f"mobile_app_{slugify(config_entry.data.get('device_name', ''))}"
            if self.hass.services.has_service("notify", service) and service not in services:
                services.append(service)
        return services

    async def push(self, title, message):
        """Send the alert to every chosen person's phones; report who was reached."""
        reached = {}
        data = {
            "tag": self.tag,
            # Android: deliver now and wake the phone. iOS: break through focus modes.
            "ttl": 0,
            "priority": "high",
            "push": {"interruption-level": "time-sensitive"},
        }
        for person in self.people:
            phones = self.phones(person)
            if not phones:
                reached[person] = "no_app"
                _LOGGER.warning("Water Guard cannot alert %s: no Home Assistant app", person)
                continue
            sent = 0
            for service in phones:
                try:
                    await self.hass.services.async_call(
                        "notify",
                        service,
                        {"title": title, "message": message, "data": data},
                        blocking=True,
                    )
                    sent += 1
                except Exception:
                    _LOGGER.warning("Water Guard could not alert %s", service, exc_info=True)
            reached[person] = "sent" if sent else "failed"
        return reached

    async def clear_pushes(self):
        for person in self.people:
            for service in self.phones(person):
                try:
                    await self.hass.services.async_call(
                        "notify",
                        service,
                        {"message": "clear_notification", "data": {"tag": self.tag}},
                        blocking=True,
                    )
                except Exception:
                    _LOGGER.debug("Could not clear the alert on %s", service, exc_info=True)

    # -- the valves ------------------------------------------------------------

    async def move(self, target, reason):
        """Move every valve to `target` and report what each one reached."""
        async with self.lock:
            self.result = {
                "target": target,
                "reason": reason,
                "status": "running",
                "valves": {},
                "updated": dt_util.utcnow().isoformat(),
            }
            self.notify()
            for entity in self.valves:
                service, reported = COMMANDS[entity.split(".", 1)[0]][target]
                reached = await actuate(self.hass, entity, service, reported)
                self.result["valves"][entity] = target if reached == reported else reached
            failed = any(status != target for status in self.result["valves"].values())
            self.result["status"] = "failed" if failed else "ok"
            self.result["updated"] = dt_util.utcnow().isoformat()
            await self.persist()
            self.notify()
            self.event("valves", **self.result)
            if failed:
                _LOGGER.warning("Water Guard could not turn the water %s: %s", target, self.result)
            return deepcopy(self.result)

    async def override(self):
        """Force the water open and clear the alert, even while a sensor is wet."""
        wet = self.wet()
        result = await self.move("open", "override") if self.valves else None
        if result and result["status"] != "ok":
            # The alert stays: the water is not back and someone should know.
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="valves_failed",
                translation_placeholders={
                    "valves": ", ".join(
                        f"{entity}: {status}"
                        for entity, status in result["valves"].items()
                        if status != "open"
                    )
                },
            )
        released, self.leak = self.leak, None
        await self.persist()
        persistent_notification.async_dismiss(self.hass, self.tag)
        self.notify()
        self.event(
            "override",
            sensors=(released or {}).get("sensors", []),
            still_wet=wet,
        )
        if released:
            await self.clear_pushes()
        return {"released": released, "still_wet": wet, "valves": result}

    @property
    def attributes(self):
        # The configured lists let a card show valves and people before any leak.
        return {
            "leak_sensors": list(self.sensors),
            "valves": list(self.valves),
            "people": list(self.people),
            "since": (self.leak or {}).get("since"),
            "sensors": (self.leak or {}).get("sensors", []),
            "notified": (self.leak or {}).get("notified", {}),
            "wet_sensors": self.wet(),
            "unavailable_sensors": self.unavailable_sensors(),
            "last_result": deepcopy(self.result),
        }
