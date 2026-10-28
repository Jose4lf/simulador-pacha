"""
Auditoría de integridad de PACHA — SOLO LECTURA.

Uso:
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/auditar_integridad.py
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/auditar_integridad.py --json

No modifica datos ni esquema. Devuelve código 1 si hay hallazgos FAIL.
"""
import argparse
import contextlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infraestructura.auditoria import auditar_integridad
from infraestructura.database import inicializar_db


def main():
    parser = argparse.ArgumentParser(description="Auditoría de integridad de PACHA (solo lectura)")
    parser.add_argument("--json", action="store_true", help="Salida en JSON")
    args = parser.parse_args()

    if args.json:
        # Mantener stdout limpio: los mensajes de arranque van a stderr.
        with contextlib.redirect_stdout(sys.stderr):
            inicializar_db()
    else:
        inicializar_db()
    resultado = auditar_integridad()

    if args.json:
        print(json.dumps(resultado, ensure_ascii=False, indent=2))
    else:
        db = resultado["db"]
        print("\n" + "=" * 68)
        print(" AUDITORÍA DE INTEGRIDAD — SOLO LECTURA")
        print("=" * 68)
        print(f" Motor: {db['motor']}" + ("  (RESPALDO SQLITE)" if db["es_fallback"] else ""))
        print(f" URL:   {db['url']}")
        print("-" * 68)

        for h in resultado["hallazgos"]:
            print(f"[{h['nivel']:<4}] {h['codigo']}: {h['mensaje']}")

        r = resultado["resumen"]
        print("-" * 68)
        print(f" Resumen: {r.get('OK', 0)} OK | {r.get('WARN', 0)} advertencias | {r.get('FAIL', 0)} fallos")
        print("=" * 68 + "\n")

    return 1 if resultado["resumen"].get("FAIL", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
