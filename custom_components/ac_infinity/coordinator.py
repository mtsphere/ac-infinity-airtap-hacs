from __future__ import annotations

import asyncio
import contextlib
import logging

import async_timeout
from ac_infinity_ble.const import MANUFACTURER_ID
from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    ActiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import CoreState, HomeAssistant, callback

DEVICE_STARTUP_TIMEOUT = 30


class ACInfinityDataUpdateCoordinator(ActiveBluetoothDataUpdateCoordinator[None]):

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        ble_device: BLEDevice,
        controller: ACInfinityController,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=logger,
            address=ble_device.address,
            needs_poll_method=self._needs_poll,
            poll_method=self._async_update,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=True,
        )
        self.ble_device = ble_device
        self.controller = controller
        self._device_ready = asyncio.Event()

    @callback
    def _needs_poll(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        seconds_since_last_poll: float | None,
    ) -> bool:
        return (
            self.hass.state == CoreState.running
            and (seconds_since_last_poll is None or seconds_since_last_poll > 30)
            and bool(
                bluetooth.async_ble_device_from_address(
                    self.hass, service_info.device.address, connectable=True
                )
            )
        )

    async def _async_update(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Poll the device."""
        await self.controller.update()
        self.logger.debug("%s (%s) state after poll: %s",
                          self.ble_device.name,
                          self.ble_device.address,
                          self.controller.state)

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        """Handle a Bluetooth event."""
        self.logger.debug("%s (%s) received: %s",
                          self.ble_device.name,
                          self.ble_device.address,
                          service_info.advertisement)
        if MANUFACTURER_ID not in service_info.advertisement.manufacturer_data:
            return
        self.ble_device = service_info.device
        self.controller.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement
        )
        if self.controller.name:
            self._device_ready.set()
        self.logger.debug("%s (%s) state after advertisement: %s",
                          self.ble_device.name,
                          self.ble_device.address,
                          self.controller.state)
        super()._async_handle_bluetooth_event(service_info, change)

    async def async_wait_ready(self) -> bool:
        """Wait for the device to be ready."""
        with contextlib.suppress(asyncio.TimeoutError):
            async with async_timeout.timeout(DEVICE_STARTUP_TIMEOUT):
                await self._device_ready.wait()
                return True
        return False
