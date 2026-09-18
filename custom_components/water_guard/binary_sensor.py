"""The latched leak alert, and the override action cards call on it."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .entity import GuardEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([LeakSensor(entry.runtime_data)])


class LeakSensor(GuardEntity, BinarySensorEntity):
    """On from a detected leak until someone overrides it, not only while a sensor is wet."""

    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(self, guard):
        super().__init__(guard, "leak")

    @property
    def is_on(self):
        return self.guard.leak is not None

    @property
    def extra_state_attributes(self):
        return self.guard.attributes

    async def async_override(self):
        return await self.guard.override()
