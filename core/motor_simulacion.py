"""
Motor de simulación MARKESTRAT - PACHA
Implementa el modelo de 5 segmentos y 3 canales de LABSAG.
"""


class MotorSimulacion:
    """Motor que simula el mercado de refrescos MARKESTRAT."""

    # Constantes del modelo
    COSTO_FIJO_POR_MARCA = 500  # en miles de $
    COSTO_VARIABLE_UNITARIO = 50  # costo unitario base
    COSTO_ALMACENAJE_PORC = 0.115  # 11.5% del costo de transferencia
    COSTO_VENDEDOR = 30.600  # costo de cada vendedor (miles de $)
    PRESUPUESTO_INICIAL = 10000  # $10,000 miles

    def __init__(self, config):
        """
        config: dict con parámetros de la industria
        """
        self.config = config or {}
        self.mercado_base = self.config.get("mercado_total", 1300000)  # 1.3M unidades
        self.inflacion_anual = self.config.get("inflacion_anual", 0.09)
        self.crecimiento_pib = self.config.get("crecimiento_pib", 0.04)

    def simular_ronda(self, marcas_data, segmentos, canales, anio, industria_config=None):
        """
        Simula una ronda completa.
        
        Args:
            marcas_data: lista de dicts {nombre, equipo_id, precio, publicidad, 
                                          investigacion, produccion, tipo,
                                          vendedores_canal1, vendedores_canal2, vendedores_canal3}
            segmentos: lista de dicts {id, numero, peso, valor_ideal_x, valor_ideal_y}
            canales: lista de dicts {id, numero, total_distribuidores, margen_promedio}
            anio: año actual (0 = año 1)
        
        Returns:
            dict {resultados: [...], mercado_total: X}
        """
        # 1. Calcular mercado total del año
        mercado_total = self._calcular_mercado(anio)
        
        # 2. Calcular atractivo de cada marca
        marcas_con_atractivo = []
        for marca in marcas_data:
            atractivo = self._calcular_atractivo(marca, marcas_data)
            marcas_con_atractivo.append({**marca, "atractivo": atractivo})
        
        # 3. Repartir mercado por segmento
        resultados = []
        for marca in marcas_con_atractivo:
            ventas_totales = 0
            porcion_total = 0
            
            for seg in segmentos:
                mercado_seg = mercado_total * seg["peso"]
                atractivo_total = sum(m["atractivo"] for m in marcas_con_atractivo)
                
                if atractivo_total > 0:
                    porcion = marca["atractivo"] / atractivo_total
                    ventas_seg = min(mercado_seg * porcion, marca["produccion"] / len(segmentos))
                    ventas_totales += ventas_seg
            
            # Limitar por producción
            ventas_totales = min(ventas_totales, marca["produccion"])
            inventario = max(0, marca["produccion"] - ventas_totales)
            porcion_total = (ventas_totales / mercado_total * 100) if mercado_total > 0 else 0
            
            # Calcular contribución bruta de marketing
            costo_transferencia = marca["precio"] * 0.55  # 55% del precio es costo
            ingresos = marca["precio"] * ventas_totales
            costo_productos = marca["precio"] * 0.55 * ventas_totales
            costo_inventario = costo_transferencia * inventario * self.COSTO_ALMACENAJE_PORC
            costo_publicidad = marca["publicidad"]
            
            contribucion_bruta = ingresos - costo_productos - costo_inventario - costo_publicidad
            
            resultados.append({
                "marca": marca["nombre"],
                "equipo_id": marca.get("equipo_id"),
                "tipo": marca.get("tipo", "SONITE"),
                "precio_final": marca["precio"],
                "publicidad": marca["publicidad"],
                "investigacion": marca["investigacion"],
                "produccion": marca["produccion"],
                "unidades_vendidas": round(ventas_totales, 0),
                "inventario": round(inventario, 0),
                "porcion_mercado": round(porcion_total, 2),
                "ingresos": round(ingresos, 0),
                "costo_productos_vendidos": round(costo_productos, 0),
                "costo_inventario": round(costo_inventario, 0),
                "contribucion_bruta_marketing": round(contribucion_bruta, 0),
            })
        
        return {
            "resultados": resultados,
            "mercado_total": mercado_total,
            "anio": anio,
        }

    def _calcular_mercado(self, anio):
        """Calcula el tamaño del mercado según el año."""
        # Crecimiento del 35% en los últimos 3 años → ~11% anual
        # + efecto del PIB
        factor_crecimiento = (1.11) ** anio
        factor_pib = (1 + self.crecimiento_pib) ** anio
        return self.mercado_base * factor_crecimiento

    def _calcular_atractivo(self, marca, todas_las_marcas):
        """
        Calcula el atractivo de una marca basado en:
        - Precio (menor = más atractivo)
        - Publicidad (mayor = más atractivo)
        - I+D (mayor = más atractivo)
        - Cantidad de vendedores
        - Cantidad de detallistas
        """
        # Precios promedio
        precios = [m["precio"] for m in todas_las_marcas]
        precio_prom = sum(precios) / len(precios) if precios else 300
        
        # Publicidades promedio
        publicidades = [m["publicidad"] for m in todas_las_marcas]
        pub_prom = sum(publicidades) / len(publicidades) if publicidades else 2500
        
        # I+D promedio
        ids = [m["investigacion"] for m in todas_las_marcas]
        id_prom = sum(ids) / len(ids) if ids else 0
        
        # Factor precio (menor precio = mayor atractivo, exponente 1.5)
        f_precio = (precio_prom / max(marca["precio"], 1)) ** 1.5
        
        # Factor publicidad (más publicidad = más atractivo, exponente 0.4)
        f_publicidad = (marca["publicidad"] / max(pub_prom, 1)) ** 0.4
        f_publicidad = max(0.3, min(3.0, f_publicidad))
        
        # Factor I+D
        if id_prom > 0:
            f_id = (marca["investigacion"] / id_prom) ** 0.3
            f_id = max(0.5, min(2.0, f_id))
        else:
            f_id = 1.0
        
        # Factor vendedores (más vendedores = más atractivo)
        total_vendedores = (marca.get("vendedores_canal1", 0) + 
                           marca.get("vendedores_canal2", 0) + 
                           marca.get("vendedores_canal3", 0))
        f_vendedores = 1 + (total_vendedores / 100) * 0.1
        
        # Factor detallistas
        total_detallistas = marca.get("detallistas_canal1", 0) + marca.get("detallistas_canal2", 0)
        f_detallistas = 1 + (total_detallistas / 1000) * 0.05
        
        return f_precio * f_publicidad * f_id * f_vendedores * f_detallistas


def generar_eventos(anio):
    """Genera eventos económicos del año."""
    eventos = {}
    eventos_fijos = {
        2: {"carnaval": True},
        5: {"crisis": True},
        8: {"navidad": True},
    }
    eventos.update(eventos_fijos.get(anio, {}))
    return eventos
    """Genera eventos económicos del año."""
    eventos = {}
    
    eventos_fijos = {
        2: {"carnaval": True},
        5: {"crisis": True},
        8: {"navidad": True},
    }
    eventos.update(eventos_fijos.get(anio, {}))
    
    if random.random() < 0.2:
        eventos[random.choice(["bloqueos", "navidad", "carnaval"])] = True
    
    return eventos