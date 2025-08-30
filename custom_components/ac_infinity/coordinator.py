from __future__ import annotations

import logging

from ac_infinity_ble import ACInfinityController
from ac_infinity_ble.const import MANUFACTURER_ID
from bleak.backends.device import BLEDevice

from homeassistant.components import bluetooth
from homeassistant.components.bluetooth.active_update_coordinator import (
    PassiveBluetoothDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant, callback


class ACInfinityDataUpdateCoordinator(
    PassiveBluetoothDataUpdateCoordinator
):

    def __init__(
        self,
        hass: HomeAssistant,
        logger: logging.Logger,
        device: BLEDevice,
        controller: ACInfinityController,
    ) -> None:
        super().__init__(
            hass=hass,
            logger=logger,
            address=device.address,
            mode=bluetooth.BluetoothScanningMode.ACTIVE,
            connectable=False,
        )
        self.device = device
        self.controller = controller

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        if MANUFACTURER_ID not in service_info.advertisement.manufacturer_data:
            return None

        self.device = service_info.device
        self.controller.set_ble_device_and_advertisement_data(
            service_info.device, service_info.advertisement)

        self.logger.debug("%s: AC Infinity data: %s",
                          self.device.address,
                          self.controller.state)
        super()._async_handle_bluetooth_event(service_info, change)
