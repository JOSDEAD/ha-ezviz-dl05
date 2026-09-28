"""Sensores informativos del DL05."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    RUTAS_BATERIA,
    RUTAS_INTENTOS_FALLIDOS,
    RUTAS_IP,
    RUTAS_SENAL_WIFI,
    RUTAS_SSID,
)
from .coordinator import EzvizDl05Coordinator, primer_valor
from .entity import EzvizDl05Entity


@dataclass(frozen=True, kw_only=True)
class DescripcionSensorDl05(SensorEntityDescription):
    """Une una descripcion de sensor con la forma de sacar su valor."""

    valor: Callable[[EzvizDl05Coordinator], Any]


SENSORES: tuple[DescripcionSensorDl05, ...] = (
    DescripcionSensorDl05(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        valor=lambda c: primer_valor(c.data, RUTAS_BATERIA),
    ),
    DescripcionSensorDl05(
        key="last_event",
        translation_key="last_event",
        icon="mdi:history",
        valor=lambda c: c.ultimo_evento,
    ),
    DescripcionSensorDl05(
        key="last_user",
        translation_key="last_user",
        icon="mdi:account-check",
        valor=lambda c: c.ultimo_usuario,
    ),
    DescripcionSensorDl05(
        key="last_method",
        translation_key="last_method",
        icon="mdi:fingerprint",
        valor=lambda c: c.ultimo_metodo,
    ),
    DescripcionSensorDl05(
        key="wifi_signal",
        translation_key="wifi_signal",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        valor=lambda c: primer_valor(c.data, RUTAS_SENAL_WIFI),
    ),
    DescripcionSensorDl05(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        icon="mdi:wifi-cog",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        valor=lambda c: primer_valor(c.data, RUTAS_SSID),
    ),
    DescripcionSensorDl05(
        key="ip_address",
        translation_key="ip_address",
        icon="mdi:ip-network",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        valor=lambda c: primer_valor(c.data, RUTAS_IP),
    ),
    DescripcionSensorDl05(
        key="error_count",
        translation_key="error_count",
        icon="mdi:lock-alert",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
        valor=lambda c: primer_valor(c.data, RUTAS_INTENTOS_FALLIDOS),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: EzvizDl05Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(SensorDl05(coordinator, desc) for desc in SENSORES)


class SensorDl05(EzvizDl05Entity, SensorEntity):
    """Sensor generico que lee su valor de la descripcion."""

    entity_description: DescripcionSensorDl05

    def __init__(
        self, coordinator: EzvizDl05Coordinator, descripcion: DescripcionSensorDl05
    ) -> None:
        super().__init__(coordinator, descripcion.key)
        self.entity_description = descripcion

    @property
    def native_value(self) -> Any:
        return self.entity_description.valor(self.coordinator)
