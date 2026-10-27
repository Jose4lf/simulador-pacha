import sys
import os
from sqlalchemy import inspect, text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from infraestructura.database import get_session

def ver_contenido_tabla():
    print("\n" + "=" * 60)
    print(" VISOR DE DATOS Y CONTEO POR TABLA")
    print("=" * 60 + "\n")

    session = get_session()
    
    try:
        engine = session.get_bind()
        inspector = inspect(engine)
        tablas = inspector.get_table_names()
        
        if not tablas:
            print("🔍 La base de datos está vacía.")
            return

        print("📊 Tablas disponibles (con su número de registros):\n")
        
        tablas_info = []
        # Primero contamos cuántos registros tiene cada una
        for tabla in sorted(tablas):
            try:
                count = session.execute(text(f"SELECT COUNT(*) FROM {tabla}")).scalar()
                tablas_info.append({"nombre": tabla, "count": count})
            except:
                tablas_info.append({"nombre": tabla, "count": "?"})

        # Mostramos el listado en columnas (3 por fila para que quepa bien)
        for i in range(0, len(tablas_info), 3):
            fila = tablas_info[i:i+3]
            texto_fila = ""
            for item in fila:
                # Formateamos para que se vea alineado: Nombre + (Cantidad)
                texto_fila += f"{item['nombre']:<25} [{item['count']:>4}]    "
            print(texto_fila)

        print("\n" + "-" * 60)
        tabla_elegida = input("👉 Escribe el nombre exacto de la tabla a ver (o 'salir'): ").strip()

        if tabla_elegida.lower() == 'salir' or not tabla_elegida:
            return

        if tabla_elegida not in tablas:
            print(f"❌ Error: La tabla '{tabla_elegida}' no existe.")
            return

        # Consultamos los datos (límite de 20 para no saturar la consola)
        print(f"\n📊 Mostrando los primeros 20 registros de '{tabla_elegida}':\n")
        
        result = session.execute(text(f"SELECT * FROM {tabla_elegida} LIMIT 20"))
        columnas = result.keys()
        filas = result.fetchall()

        if not filas:
            print("  ⚪ La tabla está vacía (0 registros).")
            return

        # Imprimir encabezados
        header = " | ".join(f"{col:<15}" for col in columnas)
        print("-" * len(header))
        print(header)
        print("-" * len(header))

        # Imprimir filas
        for fila in filas:
            valores = []
            for val in fila:
                str_val = str(val)
                if len(str_val) > 15:
                    str_val = str_val[:12] + "..."
                valores.append(f"{str_val:<15}")
            print(" | ".join(valores))

        print("-" * len(header))
        print(f"Total mostrados: {len(filas)} (Límite: 20)\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    ver_contenido_tabla()