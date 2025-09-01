from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Optional

from homeassistant.components.number import NumberDeviceClass, NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
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
    entities: list[ACInfinityNumber] = [
        TemperatureNumber(data.coordinator,
                          data.device,
                          "Auto Mode High Temperature",
                          lambda d: None if d.auto_mode is None else d.auto_mode.high_temp,
                          ACInfinityDevice.async_set_auto_high_temp),
        TemperatureNumber(data.coordinator,
                          data.device,
                          "Auto Mode Low Temperature",
                          lambda d: None if d.auto_mode is None else d.auto_mode.low_temp,
                          ACInfinityDevice.async_set_auto_low_temp),
    ]

    async_add_entities(entities)


class ACInfinityNumber(
    ActiveBluetoothCoordinatorEntity[ACInfinityDataUpdateCoordinator], NumberEntity
):
    _attr_entity_category = (
        EntityCategory.CONFIG
    )
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ACInfinityDataUpdateCoordinator,
        device: ACInfinityDevice,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_name = name
        self._attr_unique_id = f"{self._device.address}_number_{slugify(name)}"
        self._attr_device_info = DeviceInfo(
            name=device.name,
            model=DEVICE_MODEL[device.state.type],
            manufacturer=MANUFACTURER,
            sw_version=device.state.version,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )

    @callback
    def _update_attrs(self) -> None:
        raise NotImplementedError("Not yet implemented.")

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attrs()
        super()._handle_coordinator_update()


class TemperatureNumber(ACInfinityNumber):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_min_value = 0.0
    _attr_native_max_value = 90.0
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: ACInfinityDataUpdateCoordinator,
        device: ACInfinityDevice,
        name: str,
        get_value: Callable[[ACInfinityDevice], Optional[float]],
        async_set_value: Callable[[ACInfinityDevice, float], Awaitable[None]],
    ) -> None:
        self._get_value = get_value
        self._async_set_value = async_set_value
        super().__init__(coordinator, device, name)

    @callback
    def _update_attrs(self) -> None:
        self._attr_native_value = self._get_value(self._device)

    async def async_set_native_value(self, value: float) -> None:
        await self._async_set_value(self._device, value)
