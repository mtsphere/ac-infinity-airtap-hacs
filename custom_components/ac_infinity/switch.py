from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Optional

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import DEVICE_MODEL, DOMAIN, MANUFACTURER
from .coordinator import (ACInfinityDataUpdateCoordinator,
                          ActiveBluetoothCoordinatorEntity)
from .device import ACInfinityDevice
from .models import ACInfinityData


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: ACInfinityData = hass.data[DOMAIN][entry.entry_id]
    entities: list[ACInfinitySwitch] = [
        ACInfinitySwitch(data.coordinator,
                         data.device,
                         "Auto Mode High Temperature Trigger",
                         lambda d: None if d.auto_mode is None else d.auto_mode.high_temp_enabled,
                         ACInfinityDevice.async_set_auto_mode_high_temp_enabled),
        ACInfinitySwitch(data.coordinator,
                         data.device,
                         "Auto Mode Low Temperature Trigger",
                         lambda d: None if d.auto_mode is None else d.auto_mode.low_temp_enabled,
                         ACInfinityDevice.async_set_auto_mode_low_temp_enabled),
    ]

    async_add_entities(entities)


class ACInfinitySwitch(
    ActiveBluetoothCoordinatorEntity[ACInfinityDataUpdateCoordinator], SwitchEntity
):
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_entity_category = (
        EntityCategory.CONFIG
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ACInfinityDataUpdateCoordinator,
        device: ACInfinityDevice,
        name: str,
        get_is_on: Callable[[ACInfinityDevice], Optional[bool]],
        async_set_is_on: Callable[[ACInfinityDevice, bool], Awaitable[None]],
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_name = name
        self._attr_unique_id = f"{self._device.address}_switch_{slugify(name)}"
        self._attr_device_info = DeviceInfo(
            name=device.name,
            model=DEVICE_MODEL[device.state.type],
            manufacturer=MANUFACTURER,
            sw_version=device.state.version,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._get_is_on = get_is_on
        self._async_set_is_on = async_set_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on switch."""
        await self._async_set_is_on(self._device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off switch."""
        await self._async_set_is_on(self._device, False)

    @callback
    def _update_attrs(self) -> None:
        self._attr_is_on = self._get_is_on(self._device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()
