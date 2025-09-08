from __future__ import annotations

import dataclasses
import logging
from dataclasses import dataclass
from typing import Optional

from ac_infinity_ble import ACInfinityController, DeviceInfo
from ac_infinity_ble.const import CallbackType, MANUFACTURER_ID
from ac_infinity_ble.protocol import parse_manufacturer_data
from ac_infinity_ble.util import get_bit
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData

from .const import FAMILY_E_MODELS

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

    def set_ble_device_and_advertisement_data(
        self, ble_device: BLEDevice, advertisement_data: AdvertisementData
    ) -> None:
        self._ble_device = ble_device
        self._advertisement_data = advertisement_data
        info = parse_manufacturer_data(
            advertisement_data.manufacturer_data[MANUFACTURER_ID]
        )
        self._state = dataclasses.replace(
            self._state, **{k: v for k, v in dataclasses.asdict(info).items() if v is not None}
        )
        self._fire_callbacks(CallbackType.ADVERTISEMENT)

    @property
    def speed(self) -> Optional[int]:
        """Get the speed of the device."""
        return self._state.fan

    @property
    def temperature(self) -> Optional[float]:
        """Get the temperature of the device."""
        return self._state.tmp

    @property
    def humidity(self) -> Optional[float]:
        """Get the humidity of the device."""
        return self._state.hum

    @property
    def vpd(self) -> Optional[float]:
        """Get the vpd of the device."""
        return self._state.vpd

    @property
    def auto_mode(self) -> Optional[AutoModeConfig]:
        return self._state.auto_mode

    @property
    def min_speed(self) -> Optional[int]:
        return self._state.level_off

    @property
    def max_speed(self) -> Optional[int]:
        return self._state.level_on

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

                    self._config_changed_since_last_update = False
                    self._fire_callbacks(CallbackType.UPDATE_RESPONSE)
        finally:
            await self._execute_disconnect()

    async def set_mode_auto(self) -> None:
        """Set the device's mode to automatic."""
        await self._ensure_connected()
        _LOGGER.debug("%s: Setting mode to auto", self.name)

        command = [16, 1, WORK_TYPE_AUTO]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)
        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.work_type = WORK_TYPE_AUTO
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()

    async def async_set_auto_high_temp(self, value: float) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, high_temp=round(value))
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_low_temp(self, value: float) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, low_temp=round(value))
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_mode_high_temp_enabled(self, enabled: bool) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, high_temp_enabled=enabled)
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_mode_low_temp_enabled(self, enabled: bool) -> None:
        if self.auto_mode is None:
            raise ValueError("Auto mode configuration is not loaded; cannot change configuration values")

        new_config = dataclasses.replace(self.auto_mode, low_temp_enabled=enabled)
        await self.async_set_auto_mode_config(new_config)

    async def async_set_auto_mode_config(self, config: AutoModeConfig) -> None:
        if config is None:
            raise ValueError("config cannot be None")
        _LOGGER.debug("%s: Setting auto mode config to %s", self.name, config)

        def byte_for_temp_hum_enabled_switches(config: AutoModeConfig) -> int:
            b = 8 if config.high_temp_enabled else 0
            if config.low_temp_enabled:
                b |= 4
            if config.high_humidity_enabled:
                b |= 2
            if config.low_humidity_enabled:
                b |= 1
            return b

        def c_to_f(celsius: float) -> float:
            return round((celsius * 9.0 / 5.0) + 32.0, 2)

        temp_hum_enabled_switches = byte_for_temp_hum_enabled_switches(config)
        # Note: Logic does not differ based on value of is_degree, as that is a display flag only.
        # The protocol has both Celsius and Fahrenheit values; our data model uses Celsius only.
        high_temp_f = round(c_to_f(config.high_temp))
        high_temp_c = config.high_temp
        low_temp_f = round(c_to_f(config.low_temp))
        low_temp_c = config.low_temp

        command = [19, 7,
                   temp_hum_enabled_switches,
                   high_temp_f, high_temp_c,
                   low_temp_f, low_temp_c,
                   config.high_humidity,
                   config.low_humidity]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)

        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.auto_mode = config
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()

    async def async_set_min_speed(self, value: int) -> None:
        """Set the minimum fan speed for auto and other dynamic modes."""
        if value not in range(0, 11):
            raise ValueError("value must be between 0 and 10")

        _LOGGER.debug("%s: Setting min speed to %s", self.name, value)

        command = [17, 1, value]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)

        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.level_off = value
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()

    async def async_set_max_speed(self, value: int) -> None:
        """Set the maximum fan speed for auto and other dynamic modes."""
        if value not in range(0, 11):
            raise ValueError("value must be between 0 and 10")

        _LOGGER.debug("%s: Setting max speed to %s", self.name, value)

        command = [18, 1, value]
        if self.state.type in FAMILY_E_MODELS:
            command += [255, 0]
        command = self._protocol._add_head(command, 3, self.sequence)

        await self._ensure_connected()
        try:
            await self._send_command(command)

            self.state.level_off = value
            self._config_changed_since_last_update = True
        finally:
            await self._execute_disconnect()
