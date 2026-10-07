"""
Repara industrias existentes creando reportes del Año 0 que falten.
Ejecutar: python scripts/reparar_reportes_anio0.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infraestructura.database import inicializar_db, get_session
from core.models import Industria, Equipo, Marca, Reporte, ReporteMarca


def reparar():
    print("\n" + "=" * 60)
    print(" REPARANDO REPORTES DEL AÑO 0")
    print("=" * 60 + "\n")

    inicializar_db()
    session = get_session()

    try:
        industrias = session.query(Industria).all()
        total_creados = 0

        for ind in industrias:
            print(f"\n📊 Industria: {ind.nombre}")
            equipos = session.query(Equipo).filter_by(industria_id=ind.id).all()

            for eq in equipos:
                existe = session.query(Reporte).filter_by(
                    equipo_id=eq.id, anio=0
                ).first()

                if existe:
                    print(f"   ℹ️  Equipo {eq.numero}: ya tiene reporte del Año 0")
                    continue

                # Crear reporte del Año 0
                rep = Reporte(
                    equipo_id=eq.id,
                    anio=0,
                    mercado_total=1300000,
                    contribucion_bruta_total=0,
                    contribucion_neta_total=0,
                    presupuesto_proximo_periodo=10000,
                    inflacion_aplicada=ind.inflacion_anual,
                    crecimiento_pnb=ind.crecimiento_pib,
                    tipo_cambio=ind.tipo_cambio_usd,
                )
                session.add(rep)
                session.commit()
                session.refresh(rep)

                # Crear reporte_marca por cada marca
                marcas = session.query(Marca).filter_by(equipo_id=eq.id, activa=True).all()
                for marca in marcas:
                    rm = ReporteMarca(
                        reporte_id=rep.id,
                        marca_nombre=marca.nombre,
                        produccion=0,
                        unidades_vendidas=0,
                        inventario=0,
                        precio_final=marca.precio_actual,
                        precio_promedio=marca.precio_actual,
                        costo_transferencia=marca.precio_actual * 0.55,
                        ingresos=0,
                        costo_productos_vendidos=0,
                        costo_inventario=0,
                        publicidad=0,
                        contribucion_bruta_marketing=0,
                        porcion_mercado=0,
                    )
                    session.add(rm)
                session.commit()

                print(f"   ✅ Equipo {eq.numero}: reporte del Año 0 creado")
                total_creados += 1

        print(f"\n{'=' * 60}")
        print(f"✅ Total de reportes creados: {total_creados}")
        print("=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}\n")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    reparar()