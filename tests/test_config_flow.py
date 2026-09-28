"""Pruebas del flujo de configuracion."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pyezvizapi.exceptions import EzvizAuthVerificationCode, PyEzvizError

from custom_components.ezviz_dl05.const import CONF_REGION, CONF_SERIAL, DOMAIN

from .conftest import SERIAL

ENTRADA = {
    CONF_USERNAME: "prueba@correo.com",
    CONF_PASSWORD: "secreta",
    CONF_SERIAL: SERIAL,
    CONF_REGION: "us",
}


async def test_muestra_formulario(hass: HomeAssistant, parchear_cliente) -> None:
    """El primer paso debe pintar el formulario, no reventar."""
    resultado = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert resultado["type"] is FlowResultType.FORM
    assert resultado["step_id"] == "user"
    assert resultado["errors"] == {}


async def test_alta_correcta(hass: HomeAssistant, parchear_cliente) -> None:
    """Con datos buenos se crea la entrada, titulada con el nombre del cerrojo."""
    resultado = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    resultado = await hass.config_entries.flow.async_configure(
        resultado["flow_id"], ENTRADA
    )
    assert resultado["type"] is FlowResultType.CREATE_ENTRY
    assert resultado["title"] == "DL05(BG0000000)"
    assert resultado["data"][CONF_SERIAL] == SERIAL
    # Se llama al validar y otra vez al arrancar la entrada recien creada.
    assert parchear_cliente.login.called


async def test_serial_en_minusculas_se_normaliza(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Escribir el serial en minusculas no debe romper el alta."""
    resultado = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    resultado = await hass.config_entries.flow.async_configure(
        resultado["flow_id"], {**ENTRADA, CONF_SERIAL: SERIAL.lower()}
    )
    assert resultado["type"] is FlowResultType.CREATE_ENTRY
    assert resultado["data"][CONF_SERIAL] == SERIAL


async def test_credenciales_malas(hass: HomeAssistant, parchear_cliente) -> None:
    """Un login rechazado debe volver al formulario con error, no crear entrada."""
    parchear_cliente.login.side_effect = PyEzvizError("Incorrect username or password")
    resultado = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    resultado = await hass.config_entries.flow.async_configure(
        resultado["flow_id"], ENTRADA
    )
    assert resultado["type"] is FlowResultType.FORM
    assert resultado["errors"] == {"base": "invalid_auth"}


async def test_cuenta_con_2fa(hass: HomeAssistant, parchear_cliente) -> None:
    """El 2FA debe dar un mensaje propio, no 'error desconocido'."""
    parchear_cliente.login.side_effect = EzvizAuthVerificationCode("mfa")
    resultado = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    resultado = await hass.config_entries.flow.async_configure(
        resultado["flow_id"], ENTRADA
    )
    assert resultado["type"] is FlowResultType.FORM
    assert resultado["errors"] == {"base": "mfa_required"}


async def test_serial_inexistente(hass: HomeAssistant, parchear_cliente) -> None:
    """Este es el fallo que la integracion del DL03 dejaba pasar en silencio."""
    resultado = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    resultado = await hass.config_entries.flow.async_configure(
        resultado["flow_id"], {**ENTRADA, CONF_SERIAL: "NOEXISTE9"}
    )
    assert resultado["type"] is FlowResultType.FORM
    assert resultado["errors"] == {CONF_SERIAL: "device_not_found"}


async def test_no_se_duplica(hass: HomeAssistant, parchear_cliente) -> None:
    """Dar de alta el mismo serial dos veces debe abortar."""
    for _ in range(2):
        resultado = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        resultado = await hass.config_entries.flow.async_configure(
            resultado["flow_id"], ENTRADA
        )
    assert resultado["type"] is FlowResultType.ABORT
    assert resultado["reason"] == "already_configured"
