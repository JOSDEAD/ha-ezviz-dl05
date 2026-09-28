"""Sensores binarios del DL05: puerta, cerrojo y timbre."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RUTAS_CERROJO, RUTAS_PUERTA
from .coordinator import EzvizDl05Coordinator, primer_valor
from .entity import EzvizDl05Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EzvizDl05Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            SensorPuerta(coordinator),
            SensorCerrojo(coordinator),
            SensorTimbre(coordinator),
        ]
    )


class SensorPuerta(EzvizDl05Entity, BinarySensorEntity):
    """Hoja de la puerta abierta o cerrada, segun lo reporte el API."""

    _attr_translation_key = "door"
    _attr_device_class = BinarySensorDeviceClass.DOOR

    def __init__(self, coordinator: EzvizDl05Coordinator) -> None:
        super().__init__(coordinator, "door")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.puerta_abierta

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        # El codigo tal cual lo manda EZVIZ. Si la entidad sale "no disponible",
        # este es el numero que hay que agregar a CODIGOS_PUERTA en const.py.
        return {"codigo_dldoor": primer_valor(self.coordinator.data, RUTAS_PUERTA)}

    @property
    def available(self) -> bool:
        # dlDoor es un codigo sin documentar; si no sabemos leerlo, la entidad
        # se marca no disponible en vez de mentir con "cerrada".
        return super().available and self.coordinator.puerta_abierta is not None


class SensorCerrojo(EzvizDl05Entity, BinarySensorEntity):
    """Estado del pestillo. `on` = abierto."""

    _attr_translation_key = "bolt"
    _attr_device_class = BinarySensorDeviceClass.LOCK

    def __init__(self, coordinator: EzvizDl05Coordinator) -> None:
        super().__init__(coordinator, "bolt")

    @property
    def is_on(self) -> bool:
        return self.coordinator.cerrojo_abierto

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        # Deja ver de un vistazo si el dato viene del API o esta deducido del
        # registro de eventos, que es lo primero que se pregunta al depurar.
        return {
            "fuente": "api" if self.coordinator.estado_nativo else "eventos",
            "ultimo_evento": self.coordinator.ultimo_evento,
            "ultimo_usuario": self.coordinator.ultimo_usuario,
            "ultimo_metodo": self.coordinator.ultimo_metodo,
            "codigo_dllock": primer_valor(self.coordinator.data, RUTAS_CERROJO),
        }


class SensorTimbre(EzvizDl05Entity, BinarySensorEntity):
    """Se activa unos segundos cuando alguien toca el timbre."""

    _attr_translation_key = "doorbell"
    _attr_device_class = BinarySensorDeviceClass.SOUND

    def __init__(self, coordinator: EzvizDl05Coordinator) -> None:
        super().__init__(coordinator, "doorbell")

    @property
    def is_on(self) -> bool:
        return self.coordinator.timbre_sonando
