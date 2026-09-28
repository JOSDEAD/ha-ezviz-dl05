#!/usr/bin/env python3
"""Volcado de diagnostico del cerrojo EZVIZ DL05.

Este script NO toca Home Assistant. Se conecta a la nube de EZVIZ con tu cuenta,
descarga todo lo que la API sabe de tu cerrojo y lo guarda en archivos JSON.
Con esos JSON se sabe exactamente que claves expone el DL05, que es lo unico
que hace falta para adaptar la integracion.

Uso:
    pip install pyezvizapi
    python3 descubrir_dl05.py --usuario correo@ejemplo.com --serial ABC123456

La contrasena se pide por teclado (no queda en el historial del shell).
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from pyezvizapi import EzvizClient
except ImportError:
    sys.exit("Falta la libreria. Ejecuta:  pip install pyezvizapi")

# Claves cuyo valor se enmascara antes de escribir a disco.
SENSIBLES = {
    "password", "passwd", "token", "sessionId", "rfSessionId", "cookie",
    "encryptKey", "secretKey", "devcode", "bindCode", "streamToken",
    "verifyCode", "validateCode", "accessToken", "userName", "username",
    "phone", "email", "mobile", "userId", "localIp", "netIp", "wanIp",
    "ssid", "mac", "macAddress",
}


def censurar(objeto: Any) -> Any:
    """Recorre la estructura y enmascara credenciales y datos personales."""
    if isinstance(objeto, dict):
        salida = {}
        for clave, valor in objeto.items():
            if clave in SENSIBLES and valor not in (None, "", 0):
                salida[clave] = f"<oculto:{type(valor).__name__}>"
            else:
                salida[clave] = censurar(valor)
        return salida
    if isinstance(objeto, list):
        return [censurar(item) for item in objeto]
    return objeto


def guardar(destino: Path, nombre: str, datos: Any, *, censurado: bool) -> None:
    ruta = destino / nombre
    payload = censurar(datos) if censurado else datos
    ruta.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    print(f"  escrito  {ruta}")


def intentar(destino: Path, nombre: str, funcion, *, censurado: bool) -> Any:
    """Ejecuta una llamada del API y guarda el resultado o el error."""
    try:
        datos = funcion()
    except Exception as err:  # noqa: BLE001 - queremos ver cualquier fallo
        print(f"  FALLO    {nombre}: {type(err).__name__}: {err}")
        guardar(destino, nombre, {"error": f"{type(err).__name__}: {err}"}, censurado=False)
        return None
    guardar(destino, nombre, datos, censurado=censurado)
    return datos


def resumir_optionals(info: dict[str, Any]) -> None:
    """Imprime STATUS.optionals, que es donde vive el estado util del cerrojo."""
    optionals = (info or {}).get("STATUS", {}).get("optionals")
    print("\n--- STATUS.optionals (aqui estan puerta / bateria / cerrojo) ---")
    if not isinstance(optionals, dict) or not optionals:
        print("  vacio: este modelo no publica optionals, habra que")
        print("  deducir el estado desde el registro de eventos (alarminfo).")
        return
    for clave, valor in sorted(optionals.items()):
        texto = json.dumps(valor, ensure_ascii=False, default=str)
        if len(texto) > 160:
            texto = texto[:157] + "..."
        print(f"  {clave} = {texto}")


def resumir_alarmas(alarmas: dict[str, Any]) -> None:
    """Imprime los eventos recientes: de aqui salen los textos a reconocer."""
    lista = (alarmas or {}).get("alarms") or []
    print(f"\n--- Ultimos {len(lista)} eventos (alarmMessage / alarmType) ---")
    for evento in lista:
        if not isinstance(evento, dict):
            continue
        print(
            f"  [{evento.get('alarmStartTime', '?')}] "
            f"tipo={evento.get('alarmType')} "
            f"msg={evento.get('alarmMessage')!r}"
        )
    if not lista:
        print("  ninguno: abre y cierra el cerrojo a mano y vuelve a correr el script.")


def resumir_rutas(info: dict[str, Any]) -> None:
    """Imprime resourceId / localIndex, necesarios para el comando de apertura."""
    print("\n--- resourceInfos (ruta para remote_unlock) ---")
    for recurso in (info or {}).get("resourceInfos") or []:
        if not isinstance(recurso, dict):
            continue
        print(
            f"  resourceId={recurso.get('resourceId')!r} "
            f"localIndex={recurso.get('localIndex')!r} "
            f"type={recurso.get('type')!r} "
            f"category={recurso.get('resourceCategory')!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnostico EZVIZ DL05")
    parser.add_argument("--usuario", required=True, help="Correo de la cuenta EZVIZ")
    parser.add_argument("--serial", required=True, help="Numero de serie del cerrojo")
    parser.add_argument("--region", default="us",
                        help="Codigo corto de region (us, eu, sgp...) o el host completo. "
                             "El codigo corto se expande a apii<codigo>.ezvizlife.com. "
                             "Para Costa Rica normalmente es 'us'.")
    parser.add_argument("--salida", default="volcado_dl05", help="Carpeta de salida")
    parser.add_argument("--sin-censura", action="store_true",
                        help="Guarda el JSON crudo. No compartas esos archivos.")
    args = parser.parse_args()

    censurado = not args.sin_censura
    password = getpass.getpass("Contrasena EZVIZ: ")
    serial = args.serial.strip()

    destino = Path(args.salida) / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    destino.mkdir(parents=True, exist_ok=True)

    cliente = EzvizClient(args.usuario, password, args.region)
    print(f"\nIniciando sesion en {args.region} ...")
    try:
        cliente.login()
    except Exception as err:  # noqa: BLE001
        print(f"Login fallido: {type(err).__name__}: {err}")
        print("Si dice 'Incorrect Username or Password' con credenciales buenas,")
        print("casi siempre es la region equivocada: prueba otro host con --region.")
        return 1
    print("Sesion iniciada.\n")

    print("Descargando datos...")
    todos = intentar(destino, "01_todos_los_dispositivos.json",
                     cliente.get_device_infos, censurado=censurado)

    if isinstance(todos, dict):
        print("\n--- Dispositivos en la cuenta ---")
        for numero_serie, datos in todos.items():
            cabecera = (datos or {}).get("deviceInfos", {})
            marca = " <== el tuyo" if numero_serie == serial else ""
            print(
                f"  {numero_serie}  modelo={cabecera.get('deviceType')!r} "
                f"categoria={cabecera.get('deviceCategory')!r} "
                f"nombre={cabecera.get('name')!r}{marca}"
            )
        if serial not in todos:
            print(f"\nOJO: el serial {serial} no aparece. Copia uno de la lista de arriba.")

    info = intentar(destino, "02_cerrojo.json",
                    lambda: cliente.get_device_infos(serial), censurado=censurado)
    alarmas = intentar(destino, "03_eventos.json",
                       lambda: cliente.get_alarminfo(serial, limit=20), censurado=censurado)
    intentar(destino, "04_mensajes.json",
             lambda: cliente.get_device_messages_list(serial), censurado=censurado)
    intentar(destino, "05_usuarios_cerrojo.json",
             lambda: cliente.get_door_lock_users(serial), censurado=censurado)
    intentar(destino, "06_estado.json",
             lambda: cliente.get_devices_status(serial), censurado=censurado)

    if isinstance(info, dict):
        resumir_optionals(info)
        resumir_rutas(info)
    if isinstance(alarmas, dict):
        resumir_alarmas(alarmas)

    print(f"\nListo. Archivos en: {destino.resolve()}")
    print("Revisa 02_cerrojo.json y 03_eventos.json: de ahi salen las rutas")
    print("que hay que poner en const.py de la integracion.")

    try:
        cliente.close_session()
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
