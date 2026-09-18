"""Override: force the water open and clear the leak alert."""

from homeassistant.components.button import ButtonEntity

from .entity import GuardEntity


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([OverrideButton(entry.runtime_data)])


class OverrideButton(GuardEntity, ButtonEntity):
    _attr_icon = "mdi:water-alert"

    def __init__(self, guard):
        super().__init__(guard, "override")

    async def async_press(self):
        await self.guard.override()
