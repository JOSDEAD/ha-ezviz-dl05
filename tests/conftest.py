"""Configuracion comun de las pruebas.

Las pruebas NO tocan la nube de EZVIZ. Se sustituye `EzvizClient` por un doble
que devuelve un JSON fijo, con la forma que tiene un cerrojo EZVIZ real.
"""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import pytest

# JSON de un cerrojo tal como lo devuelve get_device_infos(serial).
# Si tu volcado real del DL05 tiene otra forma, cambia esto y las pruebas te
# diran exactamente que entidades dejan de funcionar.
DATOS_CERROJO = {
    "deviceInfos": {
        "name": "DL05(BG0000000)",
        "deviceSerial": "BG0000000",
        "deviceType": "CS-DL05-R101-WBCP-GR",
        "deviceCategory": "DoorLock",
        "version": "V1.2.3 build 240101",
    },
    "STATUS": {
        "optionals": {
            "OnlineStatus": 1,
            "dlDoor": 4,        # reposo real: puerta cerrada
            "dlLock": 3,        # reposo real: con llave
            "dlSignal": 100,
            "doorBellTone": 2,
            "multiPower": [
                {
                    "SubSerial": "",
                    "Type": 0,
                    "Des": "",
                    "Remaining": 85,
                    "Status": 0,
                    "Name": "VideoLock",
                    "Value": "0/0",
                }
            ],
            "superState": 0,
            "timeZone": "UTC-06:00",
        }
    },
    "WIFI": {
        "netName": "wlan0",
        "netType": "wireless",
        "address": "192.168.1.50",
        "mask": "255.255.255.0",
        "gateway": "192.168.1.1",
        "signal": 100,
        "ssid": "RedDePrueba",
    },
    # El DL05 no publica TryErrLock, a diferencia del DL03 Pro.
    "FEATURE_INFO": {"0": {"DoorLock": {"DoorLockMgr": {}}}},
    "resourceInfos": [
        {
            "resourceId": "0123456789abcdef0123456789abcdef",
            "resourceName": "DL05(BG0000000)",
            "deviceSerial": "BG0000000",
            "localIndex": "0",
            "resourceCategory": "DoorLock",
        }
    ],
}

# Evento real del DL05. customerInfo es base64 de
# {"user":"Ana","openDoorWay":"fingerprint"}.
EVENTO_HUELLA = {
    "alarmId": "MTIDSSB7D51_2ESSMM600_BG0000000_0",
    "deviceSerial": "BG0000000",
    "channelNo": 0,
    "alarmType": 17029,
    "alarmStartTime": 1788249867091,
    "alarmStartTimeStr": "2026-09-01 08:04:27",
    "sampleName": "{user}unlocked the door with fingerprint",
    "customerInfo": "eyJ1c2VyIjogIkFuYSIsICJvcGVuRG9vcldheSI6ICJmaW5nZXJwcmludCJ9",
    "alarmMessage": "Ana unlocked the door with fingerprint",
    "delayTime": 25,
}

SERIAL = "BG0000000"


@pytest.fixture(autouse=True)
def _permitir_integraciones_custom(enable_custom_integrations):
    """Sin esto Home Assistant no carga custom_components en pruebas."""
    yield


@pytest.fixture
def cliente_falso():
    """Doble de EzvizClient con las respuestas del API simuladas."""
    cliente = MagicMock()
    cliente.login.return_value = {"session_id": "x"}
    cliente._token = {"username": "prueba@correo.com"}
    cliente.get_device_infos.side_effect = lambda serial=None: (
        copy.deepcopy(DATOS_CERROJO) if serial == SERIAL
        else {SERIAL: copy.deepcopy(DATOS_CERROJO)} if serial is None
        else {}
    )
    cliente.get_alarminfo.return_value = {"alarms": []}
    cliente.remote_unlock.return_value = True
    cliente.remote_lock.return_value = True
    return cliente


@pytest.fixture
def parchear_cliente(cliente_falso):
    """Sustituye EzvizClient en los dos sitios donde se construye."""
    with (
        patch(
            "custom_components.ezviz_dl05.EzvizClient", return_value=cliente_falso
        ),
        patch(
            "custom_components.ezviz_dl05.config_flow.EzvizClient",
            return_value=cliente_falso,
        ),
    ):
        yield cliente_falso
