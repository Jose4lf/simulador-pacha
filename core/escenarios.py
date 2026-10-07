"""
Escenarios de simulación - PACHA
Cada escenario es un PRESET con los datos iniciales del mercado.
Son IGUALES para todos los equipos de una misma industria.
"""

ESCENARIO_MARKESTRATED = {
    "nombre": "Markestrated - Refrescos Bolivia",
    "version": "1.0",
    "descripcion": "Simulador de estrategia de marketing con 3 segmentos de mercado",
    
    "configuracion": {
        # Mercado
        "mercado_total": 1_000_000,
        "crecimiento_anual": 0.03,
        "inflacion": 0.045,
        
        # Segmentos
        "segmentos": {
            "popular": {"peso": 0.55, "precio_max": 7.0},
            "medio":   {"peso": 0.30, "precio_max": 12.0},
            "premium": {"peso": 0.15, "precio_max": 25.0},
        },
        
        # Costos
        "costos": {
            "fijo": 50_000,
            "variable": 3.5,
        },
        
        # Sensibilidades (elasticidades)
        "sensibilidades": {
            "precio": 1.5,
            "publicidad": 0.4,
            "investigacion": 0.3,
        },
        
        # Periodos
        "periodos_totales": 10,
        
        # Atributos iniciales (IGUALES para todas las marcas)
        "atributos_iniciales": {
            "precio": 8.50,
            "publicidad": 12000,
            "investigacion": 5000,
            "produccion": 100000,
            "calidad": 50,
        },
        
        # Marcas por equipo
        "marcas_por_equipo": 2,
        
        # Canales de distribución
        "canales": ["Tiendas", "Supermercados", "Mayoristas"],
        
        # Vendedores por canal (inicial)
        "vendedores_iniciales": [18, 22, 18],
        
        # Estudios de mercado disponibles
        "estudios_totales": 15,
        
        "parametros_bolivia": {
                "inflacion_anual": 0.0570,          # 5.70% - INE Sept 2026
                "inflacion_acumulada": 0.0388,      # 3.88% - INE Sept 2026
                "tipo_cambio_usd": 11.90,           # Bs/USD - BCB Oct 2026
                "crecimiento_pib": 0.005,           # 0.5% - CEPAL 2026
                "tasa_desempleo": 0.045,            # 4.5% estimado
                "fecha_actualizacion": "2026-10-05",
                "fuente": "INE Bolivia / BCB"
            },
    }
}


# Catálogo de escenarios
ESCENARIOS = {
    "markestrated": ESCENARIO_MARKESTRATED,
}


def obtener_escenario(codigo):
    """Devuelve la configuración de un escenario o None."""
    return ESCENARIOS.get(codigo)


def listar_escenarios():
    """Devuelve todos los escenarios disponibles."""
    return [
        {
            "codigo": k,
            "nombre": v["nombre"],
            "version": v["version"],
            "descripcion": v["descripcion"],
        }
        for k, v in ESCENARIOS.items()
    ]


def crear_industria_aleatoria(profesor_id, nombre_industria, num_equipos, codigo_escenario="markestrated"):
    """
    Genera una estructura completa de industria con datos aleatorios.
    Devuelve un dict listo para persistir.
    """
    import random
    
    escenario = obtener_escenario(codigo_escenario)
    if not escenario:
        return None
    
    config = escenario["configuracion"]
    atributos = config["atributos_iniciales"]
    
    equipos = []
    for i in range(num_equipos):
        marcas = []
        for j in range(config["marcas_por_equipo"]):
            # Cada marca tiene los MISMOS valores iniciales
            # (por eso todos parten del mismo escenario)
            marcas.append({
                "nombre": f"MARCA_{i+1}_{j+1}",
                "precio": atributos["precio"],
                "publicidad": atributos["publicidad"],
                "investigacion": atributos["investigacion"],
                "produccion": atributos["produccion"],
                "calidad": atributos["calidad"],
            })
        
        equipos.append({
            "numero": i + 1,
            "nombre_empresa": f"Empresa {i+1}",
            "marcas": marcas,
        })
    
    return {
        "nombre": nombre_industria,
        "simulador_codigo": codigo_escenario,
        "profesor_id": profesor_id,
        "config": config,
        "anio_actual": 0,
        "anio_maximo": config["periodos_totales"],
        "estado": "inicializada",
        "permitir_envio": True,
        "equipos": equipos,
    }