from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from ac_infinity_ble import ACInfinityController, DeviceInfo
from ac_infinity_ble.const import CallbackType
from ac_infinity_ble.util import get_bit
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

WORK_TYPE_OFF = 1
WORK_TYPE_ON = 2
WORK_TYPE_AUTO = 3

_LOGGER = logging.getLogger(ACInfinityController.__module__)
_MIN_SECONDS_BETWEEN_POLLS = 30


@dataclass
class DeviceInfoEx(DeviceInfo):
    @staticmethod
    def create(device_info: DeviceInfo) -> DeviceInfoEx:
        return DeviceInfoEx(**device_info.__dict__)

    auto_mode: Optional[AutoModeConfig] = None


@dataclass
class AutoModeConfig:
    high_temp_enabled: bool
    high_temp: int
    low_temp_enabled: bool
    low_temp: int
    high_humidity_enabled: bool
    high_humidity: int
    low_humidity_enabled: bool
    low_humidity: int


class ACInfinityDevice(ACInfinityController):
    _config_changed_since_last_update = False

    def __init__(
        self,
        ble_device: BLEDevice,
        state: DeviceInfoEx | None = None,
        advertisement_data: AdvertisementData | None = None,
    ):
        super().__init__(
            ble_device=ble_device,
            state=state,
            advertisement_data=advertisement_data,
        )

        if self._state is DeviceInfo:
            self._state = DeviceInfoEx(**self._state.__dict__)

    @property
    def auto_mode(self) -> Optional[AutoModeConfig]:
        return self._state.auto_mode

    @property
    def state(self) -> DeviceInfoEx:
        return self._state

    def update_needed(self, seconds_since_last_update: Optional[float | int]) -> bool:
        return (self._config_changed_since_last_update or
                seconds_since_last_update is None or seconds_since_last_update > _MIN_SECONDS_BETWEEN_POLLS)

    async def update(self) -> None:
        """Poll the device to update state date, including data not present in BLE advertisements."""
        await self._ensure_connected()
        try:
            _LOGGER.debug("%s: Updating model data", self.name)
            command = self._protocol.get_model_data(self.state.type, 0, self.sequence)
            if data := await self._send_command(command):
                if len(data) < 28:
                    _LOGGER.debug(
                        "%s: Skipping update; data too short (%s): %s",
                        self.name,
                        len(data),
                        data.hex()
                    )
                else:
                    self.state.work_type = data[12]
                    self.state.level_off = data[15]
                    self.state.level_on = data[18]

                    self.state.auto_mode = AutoModeConfig(
                        high_temp_enabled=not get_bit(data[21], 4),
                        low_temp_enabled=not get_bit(data[21], 5),
                        high_humidity_enabled=not get_bit(data[21], 6),
                        low_humidity_enabled=not get_bit(data[21], 7),
                        high_temp=data[23],
                        low_temp=data[25],
                        high_humidity=data[26],
                        low_humidity=data[27],
                    )

                    if self.state.work_type == WORK_TYPE_OFF:
                        self.state.fan = self.state.level_off
                    if self.state.work_type == WORK_TYPE_ON:
                        self.state.fan = self.state.level_on

                    self._config_changed_since_last_update = False
                    self._fire_callbacks(CallbackType.UPDATE_RESPONSE)
        finally:
            await self._execute_disconnect()

    async def set_mode_auto(self) -> None:
        """Set the device's mode to automatic."""
        await self._ensure_connected()
        _LOGGER.debug("%s: Setting mode to auto", self.name)

        command = [16, 1, WORK_TYPE_AUTO]
        if self.state.type in [7, 9, 11, 12]:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)
        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.work_type = WORK_TYPE_AUTO
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()
