"""Shared entity plumbing for one guarded water supply."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class GuardEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, guard, key):
        self.guard = guard
        self.key = key
        self._attr_unique_id = f"{guard.entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, guard.entry.entry_id)},
            name=guard.entry.title,
            manufacturer="Water Guard",
            model="Water supply",
        )

    @property
    def suggested_object_id(self):
        # "<name>_<key>" in any UI language: "Hytta" -> binary_sensor.hytta_leak.
        return self.key

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.guard.listeners.add(self.async_write_ha_state)
        self.async_on_remove(lambda: self.guard.listeners.discard(self.async_write_ha_state))
