"""Entidad de cerradura del DL05.

Desactivada por defecto: la apertura remota abre la puerta de la casa, y en
varios modelos DL05 la nube rechaza el comando o el cerrojo se cierra solo por
motor. Se habilita en Configuracion -> Integraciones -> EZVIZ DL05 -> Opciones.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pyezvizapi.exceptions import PyEzvizError

from .const import CONF_ENABLE_LOCK, DOMAIN
from .coordinator import EzvizDl05Coordinator
from .entity import EzvizDl05Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    if not entry.options.get(CONF_ENABLE_LOCK, False):
        _LOGGER.debug("Entidad de cerradura desactivada en las opciones")
        return
    coordinator: EzvizDl05Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([CerraduraDl05(coordinator)])


class CerraduraDl05(EzvizDl05Entity, LockEntity):
    """Permite abrir el cerrojo desde Home Assistant."""

    _attr_translation_key = "lock"

    def __init__(self, coordinator: EzvizDl05Coordinator) -> None:
        super().__init__(coordinator, "lock")

    @property
    def is_locked(self) -> bool:
        return not self.coordinator.cerrojo_abierto

    async def async_unlock(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.async_abrir()
        except PyEzvizError as err:
            raise HomeAssistantError(f"EZVIZ rechazo la apertura: {err}") from err

    async def async_lock(self, **kwargs: Any) -> None:
        try:
            await self.coordinator.async_cerrar()
        except PyEzvizError as err:
            raise HomeAssistantError(
                f"EZVIZ rechazo el cierre remoto (muchos DL05 solo cierran por "
                f"motor y no aceptan este comando): {err}"
            ) from err
