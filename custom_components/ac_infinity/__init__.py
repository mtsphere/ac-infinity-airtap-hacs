from __future__ import annotations

import logging

from ac_infinity_ble import DeviceInfo
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_SERVICE_DATA, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN
from .coordinator import ACInfinityDataUpdateCoordinator
from .device import ACInfinityDevice, DeviceInfoEx
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

    service_data = entry.data[CONF_SERVICE_DATA]
    if type(service_data) is dict:
        device_info = DeviceInfoEx(**service_data)
    elif type(service_data) is DeviceInfoEx:
        device_info = service_data
    elif type(service_data) is DeviceInfo:
        device_info = DeviceInfoEx.create(service_data)
    else:
        raise ValueError(
            f"Unexpected config entry service data type: {type(service_data)}"
        )

    device = ACInfinityDevice(ble_device, device_info)
    coordinator = ACInfinityDataUpdateCoordinator(hass, _LOGGER, ble_device, device)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = ACInfinityData(
        entry.title, device, coordinator
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(coordinator.async_start())

    return True
