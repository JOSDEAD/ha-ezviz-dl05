"""Base comun de las entidades del DL05."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EzvizDl05Coordinator


class EzvizDl05Entity(CoordinatorEntity[EzvizDl05Coordinator]):
    """Agrupa todas las entidades bajo un unico dispositivo en Home Assistant."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: EzvizDl05Coordinator, clave: str) -> None:
        super().__init__(coordinator)
        self.serial = coordinator.serial
        self._attr_unique_id = f"{coordinator.serial}_{clave}"

        cabecera = (coordinator.data or {}).get("deviceInfos", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.serial)},
            name=cabecera.get("name") or f"DL05 {coordinator.serial}",
            manufacturer="EZVIZ",
            model=cabecera.get("deviceType") or "DL05",
            sw_version=cabecera.get("version"),
            serial_number=coordinator.serial,
        )
