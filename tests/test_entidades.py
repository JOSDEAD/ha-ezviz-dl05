"""Pruebas de las entidades y de la logica del coordinador."""

from __future__ import annotations

from homeassistant.const import (
    STATE_LOCKED,
    STATE_OFF,
    STATE_ON,
    STATE_UNLOCKED,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ezviz_dl05.const import (
    CONF_ENABLE_LOCK,
    CONF_REGION,
    CONF_SERIAL,
    DOMAIN,
)

from .conftest import SERIAL

DATOS_ENTRADA = {
    "username": "prueba@correo.com",
    "password": "secreta",
    CONF_SERIAL: SERIAL,
    CONF_REGION: "us",
}


async def _montar(hass: HomeAssistant, opciones: dict | None = None) -> MockConfigEntry:
    entrada = MockConfigEntry(
        domain=DOMAIN,
        data=DATOS_ENTRADA,
        options=opciones or {},
        unique_id=SERIAL,
    )
    entrada.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entrada.entry_id)
    await hass.async_block_till_done()
    return entrada



def _sin_estado_nativo(parchear_cliente) -> None:
    """Quita dlLock del JSON simulado para forzar la deduccion por eventos."""
    import copy

    from .conftest import DATOS_CERROJO

    datos = copy.deepcopy(DATOS_CERROJO)
    datos["STATUS"]["optionals"].pop("dlLock")
    parchear_cliente.get_device_infos.side_effect = lambda serial=None: (
        copy.deepcopy(datos) if serial == SERIAL else {SERIAL: copy.deepcopy(datos)}
    )


async def test_entidades_creadas(hass: HomeAssistant, parchear_cliente) -> None:
    """Las entidades deben aparecer con los valores del JSON simulado."""
    await _montar(hass)

    assert hass.states.get("binary_sensor.dl05_bg0000000_door").state == STATE_OFF
    assert hass.states.get("binary_sensor.dl05_bg0000000_bolt").state == STATE_OFF
    assert hass.states.get("binary_sensor.dl05_bg0000000_doorbell").state == STATE_OFF
    assert hass.states.get("sensor.dl05_bg0000000_battery").state == "85"
    assert hass.states.get("sensor.dl05_bg0000000_wi_fi_signal").state == "100"
    # El DL05 no publica TryErrLock: el sensor queda sin dato.
    assert hass.states.get("sensor.dl05_bg0000000_failed_attempts").state == "unknown"


async def test_dispositivo_bien_identificado(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Todas las entidades cuelgan de un unico dispositivo con modelo correcto."""
    entrada = await _montar(hass)
    registro = er.async_get(hass)
    entidades = er.async_entries_for_config_entry(registro, entrada.entry_id)
    assert len(entidades) == 11  # 3 binarios + 8 sensores, la cerradura va aparte

    from homeassistant.helpers import device_registry as dr

    reg_disp = dr.async_get(hass)
    dispositivo = reg_disp.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert dispositivo is not None
    assert dispositivo.manufacturer == "EZVIZ"
    assert dispositivo.model == "CS-DL05-R101-WBCP-GR"
    assert dispositivo.sw_version == "V1.2.3 build 240101"


async def test_puerta_no_disponible_si_falta_el_dato(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Si el DL05 no publica la puerta, la entidad se marca no disponible.

    Es preferible a mostrar 'cerrada' de forma inventada en un sensor de
    seguridad.
    """
    parchear_cliente.get_device_infos.side_effect = lambda serial=None: {
        "deviceInfos": {"name": "DL05(BG0000000)", "deviceType": "CS-DL05-R101-WBCP-GR"},
        "STATUS": {"optionals": {}},
    } if serial == SERIAL else {SERIAL: {}}

    await _montar(hass)
    assert hass.states.get("binary_sensor.dl05_bg0000000_door").state == "unavailable"


async def test_evento_real_abre_el_pestillo(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Evento real del DL05: alarmType 17029 con customerInfo en base64."""
    from .conftest import EVENTO_HUELLA

    _sin_estado_nativo(parchear_cliente)
    await _montar(hass)
    coordinador = hass.data[DOMAIN][list(hass.data[DOMAIN])[0]]

    parchear_cliente.get_alarminfo.return_value = {"alarms": [EVENTO_HUELLA]}
    await coordinador.async_revisar_eventos()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.dl05_bg0000000_bolt").state == STATE_ON
    # Lo importante: usuario y metodo salen del base64, no del texto.
    assert hass.states.get("sensor.dl05_bg0000000_last_user").state == "Ana"
    assert hass.states.get("sensor.dl05_bg0000000_unlock_method").state == "huella"
    assert coordinador.ultimo_tipo == 17029


async def test_evento_en_espanol_sin_tipo_conocido(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Si el alarmType no esta mapeado, se cae al texto. Debe servir en espanol."""
    _sin_estado_nativo(parchear_cliente)
    await _montar(hass)
    coordinador = hass.data[DOMAIN][list(hass.data[DOMAIN])[0]]

    parchear_cliente.get_alarminfo.return_value = {
        "alarms": [
            {
                "alarmId": "evt-es",
                "alarmType": 99999,  # desconocido a proposito
                "alarmMessage": "Desbloqueado por huella digital",
            }
        ]
    }
    await coordinador.async_revisar_eventos()
    await hass.async_block_till_done()

    assert hass.states.get("binary_sensor.dl05_bg0000000_bolt").state == STATE_ON
    assert (
        hass.states.get("binary_sensor.dl05_bg0000000_bolt").attributes["fuente"]
        == "eventos"
    )


async def test_pestillo_vuelve_a_cerrado_solo(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Sin evento de cierre, tras el plazo el pestillo se asume cerrado."""
    _sin_estado_nativo(parchear_cliente)
    await _montar(hass, {"relock_seconds": 25})
    coordinador = hass.data[DOMAIN][list(hass.data[DOMAIN])[0]]

    parchear_cliente.get_alarminfo.return_value = {
        "alarms": [{"alarmId": "evt-1", "alarmMessage": "Apertura remota"}]
    }
    await coordinador.async_revisar_eventos()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.dl05_bg0000000_bolt").state == STATE_ON

    # Se retrocede el reloj interno mas alla del plazo configurado.
    coordinador.momento_apertura -= 26
    await coordinador.async_revisar_eventos()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.dl05_bg0000000_bolt").state == STATE_OFF


async def test_estado_del_api_gana_sobre_los_eventos(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Con dlLock=3 (codigo real conocido) no se deduce nada del texto."""
    await _montar(hass)
    coordinador = hass.data[DOMAIN][list(hass.data[DOMAIN])[0]]
    assert coordinador.estado_nativo is True
    assert hass.states.get("binary_sensor.dl05_bg0000000_bolt").state == STATE_OFF

    # Un evento de apertura no debe pisar el valor que da el API.
    parchear_cliente.get_alarminfo.return_value = {
        "alarms": [{"alarmId": "evt-9", "alarmMessage": "unlocked the door"}]
    }
    await coordinador.async_revisar_eventos()
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.dl05_bg0000000_bolt").state == STATE_OFF
    assert (
        hass.states.get("binary_sensor.dl05_bg0000000_bolt").attributes["fuente"]
        == "api"
    )


async def test_codigo_desconocido_no_miente(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Un dlDoor sin mapear deja la entidad no disponible, no 'cerrada'.

    Es la regla mas importante de la integracion: en un sensor de puerta,
    admitir que no se sabe es mejor que inventar un estado seguro.
    """
    import copy

    from .conftest import DATOS_CERROJO

    datos = copy.deepcopy(DATOS_CERROJO)
    datos["STATUS"]["optionals"]["dlDoor"] = 77  # codigo nunca visto
    parchear_cliente.get_device_infos.side_effect = lambda serial=None: (
        copy.deepcopy(datos) if serial == SERIAL else {SERIAL: copy.deepcopy(datos)}
    )

    await _montar(hass)
    assert hass.states.get("binary_sensor.dl05_bg0000000_door").state == "unavailable"


async def test_cerradura_apagada_por_defecto(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Sin activarla en opciones no debe existir entidad de cerradura."""
    await _montar(hass)
    assert hass.states.get("lock.dl05_bg0000000_lock") is None


async def test_cerradura_abre(hass: HomeAssistant, parchear_cliente) -> None:
    """Activada, lock.unlock debe mandar remote_unlock con la ruta correcta."""
    await _montar(hass, {CONF_ENABLE_LOCK: True, "lock_no": 2})
    estado = hass.states.get("lock.dl05_bg0000000_lock")
    assert estado is not None

    await hass.services.async_call(
        Platform.LOCK, "unlock",
        {"entity_id": "lock.dl05_bg0000000_lock"}, blocking=True,
    )
    await hass.async_block_till_done()

    parchear_cliente.remote_unlock.assert_called_once()
    args, kwargs = parchear_cliente.remote_unlock.call_args
    assert args[0] == SERIAL
    assert args[2] == 2                       # lock_no de las opciones
    assert kwargs["resource_id"] == "0123456789abcdef0123456789abcdef"
    assert kwargs["local_index"] == "0"  # el DL05 usa 0, no 1

    # Con dlLock publicado, la entidad refleja lo que dice el cerrojo, no un
    # optimismo nuestro: sigue en "locked" porque el API sigue diciendo 3.
    assert hass.states.get("lock.dl05_bg0000000_lock").state == STATE_LOCKED


async def test_descarga_limpia(hass: HomeAssistant, parchear_cliente) -> None:
    """Descargar la entrada debe borrar el estado y cerrar la sesion."""
    entrada = await _montar(hass)
    assert await hass.config_entries.async_unload(entrada.entry_id)
    await hass.async_block_till_done()

    # Al descargar (no borrar) Home Assistant conserva la entidad en el
    # registro y la marca no disponible; lo que si debe desaparecer es el
    # estado interno de la integracion.
    assert (
        hass.states.get("binary_sensor.dl05_bg0000000_door").state == "unavailable"
    )
    assert DOMAIN not in hass.data
    parchear_cliente.close_session.assert_called_once()


async def test_cerradura_optimista_sin_estado_nativo(
    hass: HomeAssistant, parchear_cliente
) -> None:
    """Si el cerrojo no publica dlLock, la entidad si asume que abrio."""
    _sin_estado_nativo(parchear_cliente)
    await _montar(hass, {CONF_ENABLE_LOCK: True})

    await hass.services.async_call(
        Platform.LOCK, "unlock",
        {"entity_id": "lock.dl05_bg0000000_lock"}, blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get("lock.dl05_bg0000000_lock").state == STATE_UNLOCKED
