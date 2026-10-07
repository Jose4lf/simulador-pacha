"""
Carga los 15 estudios de mercado de MARKESTRAT.
Ejecutar UNA vez: python scripts/cargar_estudios_mercado.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infraestructura.database import inicializar_db, get_session
from core.models import EstudioMercado, Simulador


ESTUDIOS = [
    {
        "numero": 1,
        "nombre": "Encuesta a los Consumidores - SONITE",
        "descripcion": "Conocimiento de marca, intenciones de compra y hábitos de canal",
        "costo_base": 77600,
        "tipo_producto": "SONITE",
    },
    {
        "numero": 2,
        "nombre": "Panel de Consumidores - SONITE",
        "descripcion": "Porciones de mercado por segmento basadas en unidades vendidas",
        "costo_base": 129400,
        "tipo_producto": "SONITE",
    },
    {
        "numero": 3,
        "nombre": "Panel de Distribuidores - SONITE",
        "descripcion": "Porciones de mercado por canal basadas en unidades vendidas",
        "costo_base": 77600,
        "tipo_producto": "SONITE",
    },
    {
        "numero": 4,
        "nombre": "Escalas Semánticas - SONITE",
        "descripcion": "Escalas de Valor, Potencia y Diseño por marca y segmento",
        "costo_base": 12800,
        "tipo_producto": "SONITE",
    },
    {
        "numero": 5,
        "nombre": "Mapa Perceptual - SONITE",
        "descripcion": "Mapa multidimensional de similitud y preferencias",
        "costo_base": 45200,
        "tipo_producto": "SONITE",
    },
    {
        "numero": 6,
        "nombre": "Pronóstico de Mercado - SONITE",
        "descripcion": "Tamaño esperado del mercado por segmento",
        "costo_base": 25800,
        "tipo_producto": "SONITE",
    },
    {
        "numero": 7,
        "nombre": "Encuesta a los Consumidores - VODITE",
        "descripcion": "Conocimiento de marca, intenciones de compra y hábitos de canal (VODITE)",
        "costo_base": 51700,
        "tipo_producto": "VODITE",
    },
    {
        "numero": 8,
        "nombre": "Panel de Consumidores - VODITE",
        "descripcion": "Porciones de mercado por segmento (VODITE)",
        "costo_base": 90500,
        "tipo_producto": "VODITE",
    },
    {
        "numero": 9,
        "nombre": "Panel de Distribuidores - VODITE",
        "descripcion": "Porciones de mercado por canal (VODITE)",
        "costo_base": 64700,
        "tipo_producto": "VODITE",
    },
    {
        "numero": 10,
        "nombre": "Escalas Semánticas - VODITE",
        "descripcion": "Escalas de Frecuencia, Peso y Valor (VODITE)",
        "costo_base": 12800,
        "tipo_producto": "VODITE",
    },
    {
        "numero": 11,
        "nombre": "Pronóstico de Ventas - VODITE",
        "descripcion": "Tamaño esperado del mercado por segmento (VODITE)",
        "costo_base": 25800,
        "tipo_producto": "VODITE",
    },
    {
        "numero": 12,
        "nombre": "Publicidad Competitiva Estimada",
        "descripcion": "Estimación de gastos publicitarios de la competencia",
        "costo_base": 38800,
        "tipo_producto": "AMBOS",
    },
    {
        "numero": 13,
        "nombre": "Fuerza de Ventas Competitiva",
        "descripcion": "Estimación de vendedores por canal de la competencia",
        "costo_base": 19200,
        "tipo_producto": "AMBOS",
    },
    {
        "numero": 14,
        "nombre": "Test de Fuerza de Ventas",
        "descripcion": "Proyección si se aumenta +5 vendedores por canal",
        "costo_base": 30900,
        "tipo_producto": "AMBOS",
    },
    {
        "numero": 15,
        "nombre": "Test de Publicidad",
        "descripcion": "Proyección si se aumenta +10% el presupuesto publicitario",
        "costo_base": 45200,
        "tipo_producto": "AMBOS",
    },
]


def cargar():
    print("\n" + "=" * 60)
    print(" CARGANDO ESTUDIOS DE MERCADO - PACHA")
    print("=" * 60 + "\n")

    inicializar_db()
    session = get_session()

    try:
        creados = 0
        actualizados = 0

        for datos in ESTUDIOS:
            existente = session.query(EstudioMercado).filter_by(numero=datos["numero"]).first()

            if existente:
                existente.nombre = datos["nombre"]
                existente.descripcion = datos["descripcion"]
                existente.costo_base = datos["costo_base"]
                existente.tipo_producto = datos["tipo_producto"]
                actualizados += 1
            else:
                estudio = EstudioMercado(**datos)
                session.add(estudio)
                creados += 1

        session.commit()

        print(f"✅ Estudios de mercado cargados:")
        print(f"   - Creados: {creados}")
        print(f"   - Actualizados: {actualizados}")
        print(f"   - Total: {len(ESTUDIOS)}\n")

    except Exception as e:
        session.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    cargar()