import psycopg2

# URL Externa de tu base de datos en Render
DB_URL = "postgresql://pacha_user:9q7RjTeGtqzYW2FADQFWAFp8z5K3DZbX@dpg-db2que67bikc73alsie0-a.oregon-postgres.render.com/pacha"

def arreglar():
    print("Conectando a la base de datos de Render...")
    try:
        conn = psycopg2.connect(DB_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        print("Ejecutando comandos SQL...")
        
        comandos = [
            "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO pacha_user;",
            "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO pacha_user;",
            "ALTER TABLE reportes ADD COLUMN IF NOT EXISTS investigacion_total FLOAT DEFAULT 0;",
            "ALTER TABLE reportes ADD COLUMN IF NOT EXISTS fuerza_ventas_total FLOAT DEFAULT 0;",
            "ALTER TABLE reportes ADD COLUMN IF NOT EXISTS investigacion_mercado FLOAT DEFAULT 0;",
            "ALTER TABLE reportes ADD COLUMN IF NOT EXISTS costo_util_excepcional FLOAT DEFAULT 0;"
        ]
        
        for cmd in comandos:
            cursor.execute(cmd)
            print(f"✅ Ejecutado: {cmd[:50]}...")
            
        cursor.close()
        conn.close()
        print("\n🎉 ¡Base de datos de Render arreglada con éxito!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    arreglar()