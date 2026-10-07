"""
Carga los 3 simuladores base en el sistema.
- Markestrated: En desarrollo (asignable)
- Adstrat: Próximamente (no asignable)
- Macroajustes: Próximamente (no asignable)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infraestructura.database import inicializar_db, get_session
from core.models import Simulador


SIMULADORES = [
    {
        "codigo": "markestrated",
        "nombre": "Markestrated",
        "descripcion": "Estrategia de Marketing",
        "estado": "en_desarrollo",
        "orden": 1,
    },
    {
        "codigo": "adstrat",
        "nombre": "Adstrat",
        "descripcion": "Estrategia Publicitaria",
        "estado": "proximamente",
        "orden": 2,
    },
    {
        "codigo": "macroajustes",
        "nombre": "Macroajustes",
        "descripcion": "Macroeconomía",
        "estado": "proximamente",
        "orden": 3,
    },
]


def cargar():
    print("\n" + "=" * 60)
    print(" CARGANDO SIMULADORES - PACHA")
    print("=" * 60 + "\n")

    inicializar_db()
    session = get_session()

    try:
        creados = 0
        actualizados = 0

        for datos in SIMULADORES:
            sim = session.query(Simulador).filter_by(codigo=datos["codigo"]).first()
            if sim:
                sim.nombre = datos["nombre"]
                sim.descripcion = datos["descripcion"]
                sim.estado = datos["estado"]
                sim.orden = datos["orden"]
                actualizados += 1
            else:
                sim = Simulador(**datos)
                session.add(sim)
                creados += 1

        session.commit()

        print(f"✅ Simuladores cargados:")
        print(f"   - Creados: {creados}")
        print(f"   - Actualizados: {actualizados}")
        print(f"\n   📊 Listado:")
        for sim in SIMULADORES:
            icono = "🟢" if sim["estado"] == "en_desarrollo" else "🔒"
            etiqueta = "En desarrollo" if sim["estado"] == "en_desarrollo" else "Próximamente"
            print(f"   {icono} {sim['nombre']} ({etiqueta})")

        print("\n" + "=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}\n")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    cargar()