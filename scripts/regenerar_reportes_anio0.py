"""
Regenera los reportes de Año 0 con unidades coherentes (Etapa 4).

Uso:
    # Simulación (no escribe nada):
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/regenerar_reportes_anio0.py

    # Aplicar cambios (escribe un respaldo JSON antes de borrar nada):
    PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/regenerar_reportes_anio0.py --aplicar

El script nunca toca reportes de años > 0, decisiones, compras ni marcas. Solo
reemplaza el reporte de Año 0 de cada equipo, que es la foto de diagnóstico
inicial. Antes de borrar, guarda una copia JSON de todos los reportes de Año 0.
"""
import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config
from infraestructura.database import get_db_info, get_session, inicializar_db
from core.models import Equipo, Industria, Reporte
from core.reportes_anio0 import generar_reporte_anio0


def _ruta_respaldo():
    candidatos = [
        os.path.join(os.path.dirname(Config.BASE_DIR), "PACHA_SIMULADOR_BACKUPS"),
        os.path.join(Config.BASE_DIR, "instance", "backups"),
    ]
    for carpeta in candidatos:
        if os.path.isdir(carpeta):
            return os.path.join(
                carpeta,
                f"reportes_anio0_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )
    carpeta = candidatos[-1]
    os.makedirs(carpeta, exist_ok=True)
    return os.path.join(
        carpeta, f"reportes_anio0_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )


def _serializar_reporte(rep):
    return {
        "equipo_id": rep.equipo_id,
        "anio": rep.anio,
        "mercado_total": rep.mercado_total,
        "contribucion_bruta_total": rep.contribucion_bruta_total,
        "contribucion_neta_total": rep.contribucion_neta_total,
        "presupuesto_proximo_periodo": rep.presupuesto_proximo_periodo,
        "investigacion_total": rep.investigacion_total,
        "fuerza_ventas_total": rep.fuerza_ventas_total,
        "investigacion_mercado": rep.investigacion_mercado,
        "costo_util_excepcional": rep.costo_util_excepcional,
        "marcas": [{
            "marca": rm.marca_nombre,
            "produccion": rm.produccion,
            "unidades_vendidas": rm.unidades_vendidas,
            "inventario": rm.inventario,
            "precio_final": rm.precio_final,
            "precio_promedio": rm.precio_promedio,
            "costo_transferencia": rm.costo_transferencia,
            "ingresos": rm.ingresos,
            "costo_productos_vendidos": rm.costo_productos_vendidos,
            "costo_inventario": rm.costo_inventario,
            "publicidad": rm.publicidad,
            "contribucion_bruta_marketing": rm.contribucion_bruta_marketing,
            "porcion_mercado": rm.porcion_mercado,
            "canales": [{
                "canal_id": c.canal_id,
                "vendedores": c.vendedores,
                "detallistas": c.detallistas,
                "ventas_unidades": c.ventas_unidades,
            } for c in rm.canales],
            "segmentos": [{
                "segmento_id": s.segmento_id,
                "ventas_unidades": s.ventas_unidades,
                "porcion_mercado": s.porcion_mercado,
            } for s in rm.segmentos],
        } for rm in rep.marcas],
    }


def _resumen(rep):
    return {
        "equipo_id": rep.equipo_id,
        "marcas": len(rep.marcas),
        "bruta": round(float(rep.contribucion_bruta_total or 0), 2),
        "neta": round(float(rep.contribucion_neta_total or 0), 2),
        "presupuesto": round(float(rep.presupuesto_proximo_periodo or 0), 2),
        "ventas_miles": round(
            sum(float(m.unidades_vendidas or 0) for m in rep.marcas), 2
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Regenera el reporte de Año 0 con unidades coherentes."
    )
    parser.add_argument(
        "--aplicar", action="store_true",
        help="Escribe los cambios. Sin esta bandera solo simula.",
    )
    parser.add_argument(
        "--respaldo", default=None,
        help="Ruta del JSON de respaldo (por defecto, carpeta de respaldos).",
    )
    args = parser.parse_args()

    inicializar_db()
    info = get_db_info()
    print("=" * 68)
    print(" REGENERACIÓN DE REPORTES DE AÑO 0")
    print("=" * 68)
    print(f" Motor: {info.get('motor', '?').upper()}")
    print(f" URL:   {info.get('url', '?')}")
    print(f" Modo:  {'APLICAR' if args.aplicar else 'SIMULACIÓN (sin cambios)'}")
    print("-" * 68)

    session = get_session()
    try:
        industrias = session.query(Industria).order_by(Industria.id).all()
        if not industrias:
            print("No hay industrias registradas.")
            return 0

        respaldo = []
        plan = []
        for industria in industrias:
            equipos = session.query(Equipo).filter_by(
                industria_id=industria.id
            ).order_by(Equipo.numero).all()
            print(f"\nIndustria {industria.id}: {industria.nombre} "
                  f"({len(equipos)} equipos, año actual {industria.anio_actual})")
            for equipo in equipos:
                anterior = session.query(Reporte).filter_by(
                    equipo_id=equipo.id, anio=0
                ).first()
                if anterior:
                    respaldo.append(_serializar_reporte(anterior))
                nuevo = generar_reporte_anio0(session, equipo, industria)
                plan.append((equipo, anterior, nuevo))
                antes = _resumen(anterior) if anterior else None
                despues = _resumen(nuevo)
                print(f"  Equipo {equipo.numero}:")
                print(f"    antes:  {antes}")
                print(f"    después:{despues}")

        if not plan:
            print("\nNada que regenerar.")
            return 0

        if not args.aplicar:
            print("\n" + "-" * 68)
            print("Simulación completada. Vuelve a ejecutar con --aplicar para escribir.")
            return 0

        ruta = args.respaldo or _ruta_respaldo()
        os.makedirs(os.path.dirname(os.path.abspath(ruta)), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as archivo:
            json.dump(respaldo, archivo, ensure_ascii=False, indent=2, default=str)
        print(f"\nRespaldo escrito: {ruta}")

        for equipo, anterior, nuevo in plan:
            if anterior is not None:
                session.delete(anterior)
                session.flush()
            session.add(nuevo)
        session.commit()

        # Verificación de unidades coherentes.
        errores = 0
        for equipo, _, _ in plan:
            rep = session.query(Reporte).filter_by(
                equipo_id=equipo.id, anio=0
            ).first()
            if not rep:
                print(f"  ERROR: equipo {equipo.numero} quedó sin reporte de Año 0")
                errores += 1
                continue
            for rm in rep.marcas:
                if abs(float(rm.ingresos or 0)
                       - float(rm.precio_final or 0) * float(rm.unidades_vendidas or 0)) > 1:
                    print(f"  ERROR: ingresos incoherentes en {rm.marca_nombre}")
                    errores += 1
                if float(rm.unidades_vendidas or 0) > float(rm.produccion or 0) + 0.5:
                    print(f"  ERROR: ventas > producción en {rm.marca_nombre}")
                    errores += 1

        print("-" * 68)
        print(f"Reportes regenerados: {len(plan)}. Errores de verificación: {errores}.")
        return 1 if errores else 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
