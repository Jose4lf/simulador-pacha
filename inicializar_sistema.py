"""
Inicializa el sistema PACHA:
1. Crea todas las tablas.
2. Crea el usuario Administrador con contraseña temporal aleatoria.
3. Carga los simuladores base (Markestrated).
4. Carga los 15 Estudios de Mercado.
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infraestructura.database import inicializar_db, get_session, get_db_actual
from infraestructura.seguridad import generar_password_temporal, hashear_password
from core.models import Usuario, Simulador, EstudioMercado

# Catálogo de los 15 Estudios
ESTUDIOS = [
    {"numero": 1, "nombre": "Encuesta Consumidores SONITE", "descripcion": "Conocimiento de marca e intenciones de compra SONITE.", "tipo": "SONITE"},
    {"numero": 2, "nombre": "Panel Consumidores SONITE", "descripcion": "Porciones de mercado por segmento SONITE.", "tipo": "SONITE"},
    {"numero": 3, "nombre": "Panel Distribuidores SONITE", "descripcion": "Porciones de mercado por canal SONITE.", "tipo": "SONITE"},
    {"numero": 4, "nombre": "Escalas Semánticas SONITE", "descripcion": "Percepción de marcas SONITE (Escala 1 al 7).", "tipo": "SONITE"},
    {"numero": 5, "nombre": "Mapa Perceptual SONITE", "descripcion": "Mapa de similitudes y preferencias SONITE.", "tipo": "SONITE"},
    {"numero": 6, "nombre": "Pronóstico Mercado SONITE", "descripcion": "Tamaño esperado del mercado SONITE.", "tipo": "SONITE"},
    {"numero": 7, "nombre": "Encuesta Consumidores VODITE", "descripcion": "Conocimiento de marca e intenciones de compra VODITE.", "tipo": "VODITE"},
    {"numero": 8, "nombre": "Panel Consumidores VODITE", "descripcion": "Porciones de mercado por segmento VODITE.", "tipo": "VODITE"},
    {"numero": 9, "nombre": "Panel Distribuidores VODITE", "descripcion": "Porciones de mercado por canal VODITE.", "tipo": "VODITE"},
    {"numero": 10, "nombre": "Escalas Semánticas VODITE", "descripcion": "Percepción de marcas VODITE (Escala 1 al 7).", "tipo": "VODITE"},
    {"numero": 11, "nombre": "Pronóstico Mercado VODITE", "descripcion": "Tamaño esperado del mercado VODITE.", "tipo": "VODITE"},
    {"numero": 12, "nombre": "Publicidad Competencia", "descripcion": "Estimación de gastos publicitarios de la competencia.", "tipo": "SONITE"},
    {"numero": 13, "nombre": "Fuerza de Ventas Competencia", "descripcion": "Estimación de vendedores de la competencia por canal.", "tipo": "SONITE"},
    {"numero": 14, "nombre": "Experimento Fuerza de Ventas", "descripcion": "Resultados esperados al aumentar vendedores.", "tipo": "SONITE"},
    {"numero": 15, "nombre": "Experimento Publicidad", "descripcion": "Resultados esperados al aumentar presupuesto publicitario.", "tipo": "SONITE"},
]


def inicializar():
    print("\n" + "=" * 60)
    print(" INICIALIZACIÓN COMPLETA DEL SISTEMA PACHA")
    print("=" * 60)

    inicializar_db()
    db_actual = get_db_actual()
    print(f"📊 Motor de BD en uso: {db_actual.upper()}\n")

    session = get_session()

    try:
        # 1. ADMIN
        admin_existente = session.query(Usuario).filter_by(username="Admin", rol="decano").first()
        if not admin_existente:
            password_temporal = generar_password_temporal()
            admin = Usuario(
                username="Admin",
                password_hash=hashear_password(password_temporal),
                debe_cambiar_password=True,
                password_actualizada=datetime.now(),
                rol="decano",
                nombre="Administrador General",
                activo=True
            )
            session.add(admin)
            session.commit()
            print("✅ Usuario Admin creado.")
            print(f"   Contraseña temporal: {password_temporal}")
            print("   Debe cambiarla en el primer inicio de sesión.")
        else:
            print("ℹ️  El usuario Admin ya existe.")

        # 2. SIMULADOR
        markestrated = session.query(Simulador).filter_by(codigo="markestrated").first()
        if not markestrated:
            session.add(Simulador(
                codigo="markestrated",
                nombre="Markestrated - Estrategia de Marketing",
                descripcion="Simulador de marketing estratégico con 5 segmentos y 3 canales.",
                estado="activo",
                orden=1
            ))
            session.commit()
            print("✅ Simulador 'Markestrated' cargado.")
        else:
            print("ℹ️  El simulador 'Markestrated' ya existe.")

        # 3. ESTUDIOS DE MERCADO
        print("\n📚 Cargando catálogo de 15 Estudios de Mercado...")
        estudios_creados = 0
        for est in ESTUDIOS:
            if not session.query(EstudioMercado).filter_by(numero=est["numero"]).first():
                session.add(EstudioMercado(
                    numero=est["numero"],
                    nombre=est["nombre"],
                    descripcion=est["descripcion"],
                    costo_base=10000, # Luego se puede ajustar por inflación
                    tipo_producto=est["tipo"]
                ))
                estudios_creados += 1
        session.commit()
        
        if estudios_creados > 0:
            print(f"✅ {estudios_creados} estudios cargados exitosamente.")
        else:
            print("ℹ️  Los estudios ya estaban cargados.")

        print("\n" + "=" * 60)
        print(" ✅ INICIALIZACIÓN FINALIZADA CON ÉXITO")
        print("=" * 60 + "\n")

    except Exception as e:
        session.rollback()
        print(f"\n❌ ERROR: {e}\n")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    inicializar()