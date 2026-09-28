"""Flujo de configuracion de la integracion EZVIZ DL05."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import callback
from pyezvizapi import EzvizClient
from pyezvizapi.exceptions import (
    EzvizAuthVerificationCode,
    InvalidHost,
    InvalidURL,
    PyEzvizError,
)

from .const import (
    CONF_ENABLE_LOCK,
    CONF_EVENT_INTERVAL,
    CONF_LOCK_NO,
    CONF_REGION,
    CONF_RELOCK_SECONDS,
    CONF_SERIAL,
    DEFAULT_EVENT_INTERVAL,
    DEFAULT_LOCK_NO,
    DEFAULT_REGION,
    DEFAULT_RELOCK_SECONDS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

ESQUEMA_USUARIO = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERIAL): str,
        vol.Optional(CONF_REGION, default=DEFAULT_REGION): str,
    }
)


class EzvizDl05ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pide credenciales y comprueba que el cerrojo existe antes de crear la entrada."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errores: dict[str, str] = {}

        if user_input is not None:
            serial = user_input[CONF_SERIAL].strip().upper()
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured()

            def validar() -> dict[str, Any]:
                cliente = EzvizClient(
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                    user_input.get(CONF_REGION, DEFAULT_REGION),
                )
                cliente.login()
                try:
                    return cliente.get_device_infos()
                finally:
                    cliente.close_session()

            try:
                dispositivos = await self.hass.async_add_executor_job(validar)
            except EzvizAuthVerificationCode:
                errores["base"] = "mfa_required"
            except (InvalidURL, InvalidHost):
                errores[CONF_REGION] = "cannot_connect"
            except PyEzvizError as err:
                _LOGGER.debug("Fallo de validacion EZVIZ: %s", err)
                errores["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Error inesperado validando la cuenta EZVIZ")
                errores["base"] = "unknown"
            else:
                if serial not in dispositivos:
                    errores[CONF_SERIAL] = "device_not_found"
                    _LOGGER.warning(
                        "Serial %s no encontrado. Disponibles: %s",
                        serial,
                        ", ".join(dispositivos) or "ninguno",
                    )
                else:
                    cabecera = dispositivos[serial].get("deviceInfos", {})
                    nombre = cabecera.get("name") or f"DL05 {serial}"
                    return self.async_create_entry(
                        title=nombre,
                        data={**user_input, CONF_SERIAL: serial},
                    )

        return self.async_show_form(
            step_id="user",
            data_schema=ESQUEMA_USUARIO,
            errors=errores,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EzvizDl05OptionsFlow(config_entry)


class EzvizDl05OptionsFlow(OptionsFlow):
    """Ajustes que se pueden cambiar sin volver a escribir la contrasena."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opciones = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_ENABLE_LOCK,
                        default=opciones.get(CONF_ENABLE_LOCK, False),
                    ): bool,
                    vol.Optional(
                        CONF_LOCK_NO,
                        default=opciones.get(CONF_LOCK_NO, DEFAULT_LOCK_NO),
                    ): vol.All(int, vol.Range(min=1, max=8)),
                    vol.Optional(
                        CONF_EVENT_INTERVAL,
                        default=opciones.get(
                            CONF_EVENT_INTERVAL, DEFAULT_EVENT_INTERVAL
                        ),
                    ): vol.All(int, vol.Range(min=2, max=60)),
                    vol.Optional(
                        CONF_RELOCK_SECONDS,
                        default=opciones.get(
                            CONF_RELOCK_SECONDS, DEFAULT_RELOCK_SECONDS
                        ),
                    ): vol.All(int, vol.Range(min=5, max=300)),
                }
            ),
        )
