"""Constantes y mapa de datos del cerrojo EZVIZ DL05.

Todo lo especifico del modelo vive aqui. Las rutas y codigos estan verificados
contra un volcado real de un CS-DL05-R101-WBCP-GR; lo que quede por confirmar
esta marcado con PENDIENTE.
"""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "ezviz_dl05"

CONF_SERIAL: Final = "serial_number"
CONF_REGION: Final = "region"
CONF_LOCK_NO: Final = "lock_no"
CONF_ENABLE_LOCK: Final = "enable_lock_entity"
CONF_EVENT_INTERVAL: Final = "event_interval"
CONF_RELOCK_SECONDS: Final = "relock_seconds"

DEFAULT_REGION: Final = "us"
DEFAULT_LOCK_NO: Final = 2          # 2 = cerrojo de puerta, 1 = porton
DEFAULT_EVENT_INTERVAL: Final = 3   # segundos entre lecturas del registro
DEFAULT_RELOCK_SECONDS: Final = 25  # coincide con el delayTime que manda EZVIZ
DEFAULT_SCAN_INTERVAL: Final = 30   # segundos entre lecturas de estado completo

PLATFORMS: Final = ["binary_sensor", "sensor", "lock"]

# --- Rutas dentro de get_device_infos(serial) -------------------------------
# Cada tupla es un camino de claves. La primera que exista y no sea None gana,
# asi la misma integracion sirve para varios modelos y firmwares.

RUTAS_PUERTA: Final = (
    ("STATUS", "optionals", "dlDoor"),      # DL05 y DL03: codigo, no booleano
    ("STATUS", "optionals", "doorStatus"),
)

RUTAS_CERROJO: Final = (
    ("STATUS", "optionals", "dlLock"),      # DL05: codigo, no booleano
    ("STATUS", "optionals", "lockStatus"),
)

RUTAS_BATERIA: Final = (
    ("STATUS", "optionals", "multiPower", 0, "Remaining"),  # DL05 verificado: 85
    ("STATUS", "optionals", "powerRemaining"),
)

RUTAS_SENAL_WIFI: Final = (
    ("WIFI", "signal"),                     # DL05 verificado: 100
    ("STATUS", "optionals", "dlSignal"),
)
RUTAS_SSID: Final = (("WIFI", "ssid"),)
RUTAS_IP: Final = (("WIFI", "address"),)

# En el DL05 este bloque no existe (solo lo publica el DL03 Pro). El sensor
# queda no disponible en vez de inventar un cero.
RUTAS_INTENTOS_FALLIDOS: Final = (
    ("FEATURE_INFO", "0", "DoorLock", "DoorLockMgr", "TryErrLock", "errCount"),
)

# --- Codigos de estado ------------------------------------------------------
# dlDoor y dlLock NO son booleanos: son codigos que EZVIZ no documenta. Se
# decodifican moviendo el cerrojo con `vigilar_estados.py`.
#
# Un codigo que no este en estos mapas deja la entidad NO DISPONIBLE y escribe
# un aviso en el registro con el valor exacto. Es deliberado: en un sensor de
# seguridad, "no se" es mejor que un "cerrado" inventado.
#
# PENDIENTE: confirmar el resto de codigos con vigilar_estados.py.
# Observado en reposo (puerta cerrada, con llave): dlDoor=4, dlLock=3.

# Nombres en vez de True/False sueltos, para que la tabla se lea sola.
ABIERTA: Final = True
CERRADA: Final = False
DESBLOQUEADO: Final = True
BLOQUEADO: Final = False

# dlDoor = la hoja de la puerta: esta pegada al marco o no.
CODIGOS_PUERTA: Final[dict[str, bool]] = {
    "4": CERRADA,   # reposo observado en un CS-DL05-R101-WBCP-GR
}

# dlLock = el seguro (pestillo o cerrojo, la misma pieza): la lengueta esta
# echada o retraida. Es independiente de la hoja: se puede tener la puerta
# cerrada y sin seguro, o el seguro retraido con la puerta todavia cerrada.
CODIGOS_CERROJO: Final[dict[str, bool]] = {
    "3": BLOQUEADO,   # reposo observado en un CS-DL05-R101-WBCP-GR
}

# --- Reconocimiento de eventos ---------------------------------------------
# El API manda `alarmType` numerico, que es independiente del idioma de la
# cuenta, y `customerInfo` en base64 con {"user":..., "openDoorWay":...}.
# Eso es lo que se usa. El texto solo se mira si el tipo es desconocido.

# alarmType -> ("abierto" | "cerrado" | "timbre")
TIPOS_ALARMA: Final[dict[int, str]] = {
    17029: "abierto",   # verificado: "{user} unlocked the door with fingerprint"
}

# Se usan raices, no palabras completas, para que sirvan igual en masculino,
# femenino y plural: "abiert" cubre abierto/abierta/abiertas.
#
# IMPORTANTE: para el estado del cerrojo, coordinator.py evalua ABIERTO antes
# que CERRADO, y ese orden resuelve los solapes del espanol: "desbloqueada"
# contiene "bloque", pero ABIERTO gana primero con "desbloque". Si agregas
# raices aqui, respeta ese orden. El timbre se evalua aparte y no compite.

PALABRAS_ABIERTO: Final = (
    "unlock", "opened", "open by", "opened by",
    "desbloque", "abiert", "apertura", "abrio", "abrió", "se abre",
)
PALABRAS_CERRADO: Final = (
    "locked", "lock ", "closed",
    "bloque", "cerrad", "cerro", "cerró", "cierre", "se cierra",
)
PALABRAS_TIMBRE: Final = (
    "rings", "ring", "bell", "calling", "doorbell",
    "timbre", "llamada", "llamando", "toco", "tocó",
)

# Traduccion de openDoorWay a algo legible en el panel.
METODOS_APERTURA: Final[dict[str, str]] = {
    "fingerprint": "huella",
    "password": "codigo",
    "card": "tarjeta",
    "face": "rostro",
    "key": "llave",
    "app": "app",
    "remote": "remoto",
    "bluetooth": "bluetooth",
    "temporaryPassword": "codigo temporal",
    "palmVein": "palma",
}
