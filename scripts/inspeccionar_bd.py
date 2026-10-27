import sys
import os
from sqlalchemy import inspect, text

# Esto le dice a Python que suba un nivel desde 'scripts/' hasta la raíz del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infraestructura.database import get_session

def inspeccionar_y_limpiar():
    print("\n" + "=" * 60)
    print(" INSPECCIÓN DE LA BASE DE DATOS")
    print("=" * 60 + "\n")

    session = get_session()
    
    try:
        engine = session.get_bind()
        inspector = inspect(engine)
        tablas = inspector.get_table_names()
        
        if not tablas:
            print("🔍 La base de datos está TOTALMENTE VACÍA (no hay tablas).")
            print("👉 Ejecuta 'python inicializar_sistema.py' para crearlas.")
            return

        print(f"📊 Se encontraron {len(tablas)} tablas en la base de datos:\n")
        
        tablas_con_datos = []
        tablas_vacias = []

        for tabla in tablas:
            try:
                resultado = session.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
                if resultado > 0:
                    tablas_con_datos.append((tabla, resultado))
                else:
                    tablas_vacias.append(tabla)
            except Exception as e:
                print(f"  ⚠️ Error al leer la tabla {tabla}: {e}")

        if tablas_con_datos:
            print("✅ Tablas CON datos:")
            for t, count in tablas_con_datos:
                print(f"   - {t}: {count} registros")
        else:
            print("✅ Tablas CON datos: Ninguna")

        print("\n⚪ Tablas VACÍAS:")
        if tablas_vacias:
            for t in tablas_vacias:
                print(f"   - {t}")
        else:
            print("   - Ninguna")

        print("\n" + "-" * 60)
        confirmacion = input("⚠️ ¿Deseas ELIMINAR TODAS LAS TABLAS y dejarla vacía? (escribe 'SI' para borrar): ")

        if confirmacion.strip().upper() == "SI":
            print("\n🗑️ Eliminando todas las tablas (usando CASCADE)...")
            
            # 👇 CORREGIDO: Quitamos la desactivación de llaves foráneas y usamos CASCADE directo
            for tabla in tablas:
                session.execute(text(f"DROP TABLE IF EXISTS {tabla} CASCADE;"))
                print(f"   ✅ Eliminada: {tabla}")
            
            session.commit()
            
            print("\n🎉 ¡Base de datos vaciada completamente!")
            print("👉 Ahora debes ejecutar: python inicializar_sistema.py")
        else:
            print("\n❌ Operación cancelada. No se borró nada.")

    except Exception as e:
        session.rollback()
        print(f"\n❌ Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    inspeccionar_y_limpiar()