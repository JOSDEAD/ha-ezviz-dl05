#!/usr/bin/env python3
"""Decodifica que significan dlDoor y dlLock en TU cerrojo.

Los valores que devuelve el DL05 (dlDoor=4, dlLock=3) son codigos, no
booleanos, y EZVIZ no los documenta. La unica forma de saber que significan es
mover el cerrojo a mano y ver que numero aparece con cada estado.

Este script consulta el estado cada 2 segundos y solo escribe cuando algo
cambia. No manda ningun comando al cerrojo: solo lee.

Uso:
    python3 vigilar_estados.py --usuario correo@ejemplo.com --serial TU_SERIAL

Con el script corriendo, hace esto sin prisa y anota en voz alta lo que haces:

    1. Deja la puerta cerrada y con llave           (estado de reposo)
    2. Abri con huella, pero NO abras la puerta     (cambia dlLock)
    3. Abri la puerta fisicamente                   (cambia dlDoor)
    4. Deja la puerta abierta unos 15 segundos
    5. Cerra la puerta                              (dlDoor vuelve)
    6. Espera a que el cerrojo eche llave solo      (dlLock vuelve)

Ctrl+C para terminar. Al final imprime la tabla de valores vistos.
"""

from __future__ import annotations

import argparse
import getpass
import sys
import time
from collections import defaultdict
from datetime import datetime

try:
    from pyezvizapi import EzvizClient
except ImportError:
    sys.exit("Falta la libreria. Ejecuta:  pip install pyezvizapi")

VIGILADAS = ("dlDoor", "dlLock", "superState", "OnlineStatus")


def leer_estado(cliente, serial: str) -> dict[str, str]:
    """Devuelve todas las claves simples de STATUS.optionals.

    Se vigilan todas, no solo las de VIGILADAS: si dlDoor/dlLock no cambian,
    puede que el estado real viva en otra clave.
    """
    respuesta = cliente.get_devices_status(serial)
    infos = respuesta.get("statusInfos") or {}
    optionals = (infos.get(serial) or {}).get("optionals") or {}
    return {
        k: str(v) for k, v in optionals.items()
        if not isinstance(v, (dict, list))
    }


def leer_eventos(cliente, serial: str) -> list[dict]:
    """Ultimos eventos del registro, del mas viejo al mas nuevo."""
    respuesta = cliente.get_alarminfo(serial, limit=5)
    return list(reversed(respuesta.get("alarms") or []))


def main() -> int:
    parser = argparse.ArgumentParser(description="Vigila los estados del DL05")
    parser.add_argument("--usuario", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--region", default="us")
    parser.add_argument("--intervalo", type=float, default=2.0)
    args = parser.parse_args()

    password = getpass.getpass("Contrasena EZVIZ: ")
    serial = args.serial.strip()

    cliente = EzvizClient(args.usuario, password, args.region)
    print(f"\nIniciando sesion en {args.region} ...")
    cliente.login()
    print("Sesion iniciada. Vigilando. Ctrl+C para terminar.\n")
    print(__doc__.split("Con el script corriendo,")[1].split("Ctrl+C")[0].strip())
    print("\n" + "-" * 60)

    anterior: dict[str, str] = {}
    vistos: dict[str, set[str]] = defaultdict(set)
    historial: list[tuple[str, str, str, str]] = []
    eventos_vistos: set[str] = set()
    primera_vuelta = True

    try:
        while True:
            try:
                actual = leer_estado(cliente, serial)
                eventos = leer_eventos(cliente, serial)
            except Exception as err:  # noqa: BLE001
                print(f"  (fallo de lectura: {type(err).__name__}: {err})")
                time.sleep(5)
                continue

            marca = datetime.now().strftime("%H:%M:%S")
            for clave, valor in actual.items():
                vistos[clave].add(valor)
                if not anterior:
                    if clave in VIGILADAS:
                        print(f"{marca}  inicial   {clave} = {valor}")
                elif anterior.get(clave) != valor:
                    viejo = anterior.get(clave, "(no estaba)")
                    print(f"{marca}  CAMBIO    {clave}: {viejo} -> {valor}")
                    historial.append((marca, clave, viejo, valor))
            anterior = actual

            for evento in eventos:
                ident = evento.get("alarmId") or str(evento.get("alarmStartTime"))
                if ident in eventos_vistos:
                    continue
                eventos_vistos.add(ident)
                if primera_vuelta:
                    continue
                texto = (
                    f"alarmType={evento.get('alarmType')}  "
                    f"{evento.get('alarmStartTimeStr')}  "
                    f"{evento.get('alarmMessage') or evento.get('sampleName')}"
                )
                print(f"{marca}  EVENTO    {texto}")
                historial.append((marca, "EVENTO", "", texto))
            primera_vuelta = False
            time.sleep(args.intervalo)

    except KeyboardInterrupt:
        print("\n" + "-" * 60)
        print("\nValores distintos observados:")
        for clave in VIGILADAS:
            if vistos.get(clave):
                orden = sorted(vistos[clave], key=lambda v: (len(v), v))
                print(f"  {clave}: {', '.join(orden)}")
        if historial:
            print("\nSecuencia de cambios (comparala con lo que hiciste):")
            for marca, clave, viejo, nuevo in historial:
                if clave == "EVENTO":
                    print(f"  {marca}  EVENTO {nuevo}")
                else:
                    print(f"  {marca}  {clave}: {viejo} -> {nuevo}")
        else:
            print("\nNo hubo ningun cambio. Si moviste el cerrojo, puede que el")
            print("estado tarde en subir a la nube: intenta de nuevo mas despacio.")
        try:
            cliente.close_session()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
