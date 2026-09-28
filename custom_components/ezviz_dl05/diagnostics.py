"""Descarga de diagnostico desde la interfaz de Home Assistant.

Sirve para ver el JSON crudo del DL05 sin abrir una terminal: en el dispositivo,
boton "Descargar diagnostico". De ahi salen las claves para ajustar const.py.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import EzvizDl05Coordinator

A_OCULTAR = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "serial_number",
    "deviceSerial",
    "userName",
    "userId",
    "bindCode",
    "streamToken",
    "encryptKey",
    "secretKey",
    "devcode",
    "localIp",
    "netIp",
    "wanIp",
    "ssid",
    "mac",
    "macAddress",
    "address",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    coordinator: EzvizDl05Coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "opciones": dict(entry.options),
        "estado_derivado": {
            "cerrojo_abierto": coordinator.cerrojo_abierto,
            "estado_nativo": coordinator.estado_nativo,
            "ultimo_evento": coordinator.ultimo_evento,
            "ultimo_evento_hora": coordinator.ultimo_evento_hora,
            "lock_no": coordinator.lock_no,
        },
        "datos_dispositivo": async_redact_data(coordinator.data or {}, A_OCULTAR),
    }
