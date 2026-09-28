"""Integracion no oficial para el cerrojo EZVIZ DL05."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from pyezvizapi import EzvizClient
from pyezvizapi.exceptions import (
    EzvizAuthVerificationCode,
    InvalidHost,
    InvalidURL,
    PyEzvizError,
)

from .const import (
    CONF_EVENT_INTERVAL,
    CONF_LOCK_NO,
    CONF_REGION,
    CONF_RELOCK_SECONDS,
    CONF_SERIAL,
    DEFAULT_EVENT_INTERVAL,
    DEFAULT_LOCK_NO,
    DEFAULT_REGION,
    DEFAULT_RELOCK_SECONDS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import EzvizDl05Coordinator

_LOGGER = logging.getLogger(__name__)

# Cuanto se mantiene el binary_sensor del timbre en "detectado".
DURACION_TIMBRE = 7


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Arranca una entrada de configuracion."""
    opciones = entry.options
    cliente = EzvizClient(
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_REGION, DEFAULT_REGION),
    )

    try:
        await hass.async_add_executor_job(cliente.login)
    except EzvizAuthVerificationCode as err:
        raise ConfigEntryAuthFailed(
            "La cuenta EZVIZ pide codigo de verificacion (2FA)"
        ) from err
    except (InvalidURL, InvalidHost) as err:
        raise ConfigEntryNotReady(f"No se pudo contactar EZVIZ: {err}") from err
    except PyEzvizError as err:
        raise ConfigEntryAuthFailed(f"Login EZVIZ rechazado: {err}") from err

    coordinator = EzvizDl05Coordinator(
        hass,
        cliente,
        entry.data[CONF_SERIAL],
        scan_interval=DEFAULT_SCAN_INTERVAL,
        relock_seconds=opciones.get(CONF_RELOCK_SECONDS, DEFAULT_RELOCK_SECONDS),
        lock_no=opciones.get(CONF_LOCK_NO, DEFAULT_LOCK_NO),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    intervalo = opciones.get(CONF_EVENT_INTERVAL, DEFAULT_EVENT_INTERVAL)

    async def vigilante_de_eventos() -> None:
        """Sondea el registro de eventos mas rapido que el refresco completo.

        EZVIZ no manda push al cerrojo, asi que la unica forma de enterarse de
        una apertura en pocos segundos es preguntar seguido por el ultimo
        evento. Es una llamada barata comparada con get_device_infos.
        """
        fallos = 0
        while True:
            try:
                await coordinator.async_revisar_eventos()
                fallos = 0
                if coordinator.timbre_sonando:
                    await asyncio.sleep(DURACION_TIMBRE)
                    coordinator.apagar_timbre()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # noqa: BLE001
                fallos += 1
                # Solo se registra el primer fallo de una racha, para no llenar
                # el log cuando se cae internet.
                if fallos == 1:
                    _LOGGER.warning("Fallo leyendo eventos del DL05: %s", err)
            # Al fallar se espera mas, hasta 60 s, para no castigar el API.
            await asyncio.sleep(min(intervalo * max(fallos, 1), 60))

    entry.async_create_background_task(
        hass, vigilante_de_eventos(), f"{DOMAIN}-eventos"
    )
    entry.async_on_unload(entry.add_update_listener(_async_recargar))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Descarga la entrada y cierra la sesion HTTP."""
    descargado = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if descargado:
        coordinator: EzvizDl05Coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        try:
            await hass.async_add_executor_job(coordinator.client.close_session)
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("No se pudo cerrar la sesion EZVIZ: %s", err)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return descargado


async def _async_recargar(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Recarga la entrada cuando cambian las opciones."""
    await hass.config_entries.async_reload(entry.entry_id)
