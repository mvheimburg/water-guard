"""Operate a device and wait for it to report the result; a service call is not proof."""

import asyncio
import logging

from homeassistant.core import callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)
# How long a device may take to report its new state after accepting a command.
VERIFY_TIMEOUT = 30
UNKNOWN = {"unknown", "unavailable"}


async def actuate(hass, entity, service, target, failures=()):
    """Call `domain.service` on an entity and wait until it reports `target`.

    Returns `target` once reached, a reported failure state (e.g. `jammed`),
    or `unavailable`, `failed` (the call was refused) or `unverified`.
    """
    state = hass.states.get(entity)
    if state is None or state.state in UNKNOWN:
        return "unavailable"
    if state.state == target:
        return target
    done = asyncio.Event()

    @callback
    def changed(event):
        new = event.data["new_state"]
        if new is None or new.state in {target, *failures} | UNKNOWN:
            done.set()

    unsub = async_track_state_change_event(hass, [entity], changed)
    try:
        try:
            await hass.services.async_call(
                entity.split(".", 1)[0], service, {"entity_id": entity}, blocking=True
            )
        except Exception:
            _LOGGER.warning("Could not %s %s", service, entity, exc_info=True)
            return "failed"
        if (state := hass.states.get(entity)) is None or state.state != target:
            try:
                async with asyncio.timeout(VERIFY_TIMEOUT):
                    await done.wait()
            except TimeoutError:
                return "unverified"
    finally:
        unsub()
    state = hass.states.get(entity)
    if state is None or state.state in UNKNOWN:
        return "unavailable"
    return state.state if state.state in {target, *failures} else "unverified"
