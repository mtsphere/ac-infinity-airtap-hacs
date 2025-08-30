from __future__ import annotations

import logging

from ac_infinity_ble import ACInfinityController, DeviceInfo

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ADDRESS,
    CONF_SERVICE_DATA,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ACInfinityDataUpdateCoordinator
from .models import ACInfinityData

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.FAN]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(hass, address.upper(), True)
    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find AC Infinity device with address {address}"
        )

    device_info: DeviceInfo | dict = entry.data[CONF_SERVICE_DATA]
    if type(device_info) is dict:
        device_info = DeviceInfo(**entry.data[CONF_SERVICE_DATA])
    controller = ACInfinityController(ble_device, device_info)
    coordinator = ACInfinityDataUpdateCoordinator(hass, _LOGGER, ble_device, controller)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ACInfinityData(
        entry.title, controller, coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(coordinator.async_start())

    return True
