import os
from presentacion.web import create_app
from infraestructura.database import inicializar_db, get_db_actual

# Inicializar BD (con fallback automático)
inicializar_db()

app = create_app()

if __name__ == "__main__":
    db = get_db_actual()
    print(f"\n🚀 PACHA arrancando con motor: {db.upper()}\n")
    
    # Leer puerto desde variable de entorno (la nube lo asigna)
    port = int(os.environ.get("PORT", 5000))
    
    # Detectar si estamos en desarrollo local o en producción
    debug_mode = os.environ.get("FLASK_ENV", "development") == "development"
    
    app.run(host="0.0.0.0", port=port, debug=debug_mode)