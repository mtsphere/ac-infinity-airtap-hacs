from __future__ import annotations

import math
from typing import Any

from ac_infinity_ble import ACInfinityController

from homeassistant.components.fan import FanEntity, FanEntityFeature

from homeassistant.components.bluetooth.passive_update_coordinator import (
    PassiveBluetoothCoordinatorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    int_states_in_range,
    ranged_value_to_percentage,
    percentage_to_ranged_value,
)

from .const import DEVICE_MODEL, DOMAIN, MANUFACTURER
from .coordinator import ACInfinityDataUpdateCoordinator
from .models import ACInfinityData

AUTO_MODE_WORK_TYPE = 3
SPEED_RANGE = (1, 10)

PRESET_AUTO_MODE = "Auto"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data: ACInfinityData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ACInfinityFan(data.coordinator, data.device, entry.title)])


class ACInfinityFan(
    PassiveBluetoothCoordinatorEntity[ACInfinityDataUpdateCoordinator], FanEntity
):

    _attr_speed_count = int_states_in_range(SPEED_RANGE)
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.PRESET_MODE
    )
    _attr_preset_modes = [PRESET_AUTO_MODE]

    def __init__(
        self,
        coordinator: ACInfinityDataUpdateCoordinator,
        device: ACInfinityController,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._device = device
        self._attr_name = f"{name} Fan"
        self._attr_unique_id = f"{self._device.address}_fan"
        self._attr_device_info = DeviceInfo(
            name=device.name,
            model=DEVICE_MODEL[device.state.type],
            manufacturer=MANUFACTURER,
            sw_version=device.state.version,
            connections={(dr.CONNECTION_BLUETOOTH, device.address)},
        )
        self._async_update_attrs()

    async def async_set_percentage(self, percentage: int) -> None:
        """Set the speed of the fan, as a percentage."""
        speed = 0
        if percentage > 0:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))

        await self._device.set_speed(speed)

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        if preset_mode is not None:
            await self.async_set_preset_mode(preset_mode)
            return
        speed = None
        if percentage is not None:
            speed = math.ceil(percentage_to_ranged_value(SPEED_RANGE, percentage))
        self._attr_preset_mode = None
        await self._device.turn_on(speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._device.turn_off()

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self._device._ensure_connected()
        if preset_mode == PRESET_AUTO_MODE:
            self._attr_preset_mode = PRESET_AUTO_MODE
            self._device.state.work_type = AUTO_MODE_WORK_TYPE

            # NOTE(HACK): Should fold this into the ac-infinity-ble library
            command = [16, 1, AUTO_MODE_WORK_TYPE]
            if type in [7, 9, 11, 12]:
                command += [255, 0]
            command = self._device._protocol._add_head(command, 3, self._device.sequence)
            await self._device._send_command(command)
            await self._device._execute_disconnect()

    @callback
    def _async_update_attrs(self) -> None:
        """Handle updating _attr values."""
        self._attr_is_on = self._device.is_on
        self._attr_percentage = ranged_value_to_percentage(
            SPEED_RANGE, self._device.state.fan
        )
        self._attr_preset_mode = PRESET_AUTO_MODE if \
            self._device.state.work_type == AUTO_MODE_WORK_TYPE else None

    @callback
    def _handle_coordinator_update(self, *args: Any) -> None:
        """Handle data update."""
        self._async_update_attrs()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            self._device.register_callback(self._handle_coordinator_update)
        )
        return await super().async_added_to_hass()
