from __future__ import annotations

from dataclasses import dataclass

from .device import ACInfinityDevice
from .coordinator import ACInfinityDataUpdateCoordinator


@dataclass
class ACInfinityData:
    title: str
    device: ACInfinityDevice
    coordinator: ACInfinityDataUpdateCoordinator
