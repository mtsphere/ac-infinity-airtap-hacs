from __future__ import annotations

from dataclasses import dataclass

from ac_infinity_ble import ACInfinityController

from .coordinator import ACInfinityDataUpdateCoordinator


@dataclass
class ACInfinityData:
    title: str
    device: ACInfinityController
    coordinator: ACInfinityDataUpdateCoordinator
