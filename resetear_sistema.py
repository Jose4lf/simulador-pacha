"""
Script para eliminar TODAS las tablas viejas y dejar la BD limpia.
Luego, los modelos normalizados crearán las 35 tablas nuevas.

⚠️  ADVERTENCIA: Esto elimina TODOS los datos.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from infraestructura.database import inicializar_db, get_session


# Todas las tablas viejas + nuevas (por si acaso)
TABLAS_A_ELIMINAR = [
    # Viejas
    "reporte_marca_segmento",
    "reporte_marca_canal",
    "reporte_marca",
    "reportes",
    "decision_estudios",
    "decision_vendedores",
    "decision_marca",
    "decisiones",
    "proyecto_atributos",
    "proyectos_id",
    "atributos_fisicos",
    "escalas_semanticas",
    "posiciones_perceptuales",
    "fuerza_ventas",
    "marcas",
    "equipos",
    "industrias",
    "segmentos",
    "canales",
    "estudios_mercado",
    "compras_estudios",
    "estudio_awareness",
    "estudio_intencion_compra",
    "estudio_panel_consumidores",
    "estudio_panel_distribuidores",
    "estudio_escalas",
    "estudio_mapa_perceptual",
    "estudio_pronostico",
    "estudio_publicidad_competencia",
    "estudio_fuerza_ventas_competencia",
    "logs_actividad",
    "usuarios",
    "simuladores",
    "asignaciones_simulador",
    "configuracion",
]


def resetear():
    print("\n" + "=" * 60)
    print(" RESET DE BD - PACHA NORMALIZADA")
    print("=" * 60)
    print(f"\n⚠️  Se eliminarán {len(TABLAS_A_ELIMINAR)} tablas.")
    print("   (Los datos se perderán permanentemente)\n")

    confirmar = input("¿Continuar? (escribe 'SI'): ").strip()
    if confirmar != "SI":
        print("❌ Cancelado")
        return

    inicializar_db()
    session = get_session()

    try:
        print("\n🗑️  Eliminando tablas...")
        for tabla in TABLAS_A_ELIMINAR:
            try:
                session.execute(text(f"DROP TABLE IF EXISTS {tabla} CASCADE"))
                session.commit()
                print(f"   ✅ {tabla}")
            except Exception as e:
                session.rollback()
                print(f"   ⚠️  {tabla}: {e}")

        print("\n✅ RESET COMPLETADO")
        print("📌 Ahora ejecuta: python -c \"from infraestructura.database import inicializar_db; inicializar_db()\"")
        print("   Esto creará las 35 tablas nuevas.\n")

    finally:
        session.close()


if __name__ == "__main__":
    resetear()