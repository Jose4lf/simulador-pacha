"""
Generador de datos para los estudios de mercado.
Simula los resultados que el sistema produciría.
"""
import random


class GeneradorEstudios:
    """Genera datos realistas para cada estudio de mercado."""

    def __init__(self, marcas_data, segmentos_data, canales_data, anio):
        """
        marcas_data: lista de {nombre, equipo_id, precio, publicidad, produccion, 
                                posicion_x, posicion_y, escala_valor, escala_potencia, escala_diseno}
        segmentos_data: lista de {id, numero, peso, valor_ideal_x, valor_ideal_y}
        canales_data: lista de {id, numero, nombre, total_distribuidores}
        """
        self.marcas = marcas_data
        self.segmentos = segmentos_data
        self.canales = canales_data
        self.anio = anio

    def generar_estudio(self, numero_estudio):
        """Devuelve dict con los datos del estudio solicitado."""
        metodos = {
            1: self._estudio_1_awareness,
            2: self._estudio_2_panel_consumidores,
            3: self._estudio_3_panel_distribuidores,
            4: self._estudio_4_escalas,
            5: self._estudio_5_mapa_perceptual,
            6: self._estudio_6_pronostico,
            7: self._estudio_1_awareness,  # VODITE (reutiliza)
            8: self._estudio_2_panel_consumidores,
            9: self._estudio_3_panel_distribuidores,
            10: self._estudio_4_escalas,
            11: self._estudio_6_pronostico,
            12: self._estudio_12_publicidad_competencia,
            13: self._estudio_13_fuerza_ventas_competencia,
            14: self._estudio_14_test_fuerza_ventas,
            15: self._estudio_15_test_publicidad,
        }
        metodo = metodos.get(numero_estudio)
        if not metodo:
            return {}
        return metodo()

    # --- ESTUDIO 1: Encuesta consumidores ---
    def _estudio_1_awareness(self):
        awareness = []
        intenciones = []
        habitos = []

        for marca in self.marcas:
            aw = round(random.uniform(0.15, 0.45), 3)
            awareness.append({
                "marca": marca["nombre"],
                "awareness": aw,
            })

            for seg in self.segmentos:
                intencion = round(random.uniform(0.01, 0.20), 3)
                intenciones.append({
                    "marca": marca["nombre"],
                    "segmento": seg["numero"],
                    "intencion": intencion,
                })

        for seg in self.segmentos:
            for can in self.canales:
                porcentaje = round(random.uniform(0.05, 0.95), 2)
                habitos.append({
                    "segmento": seg["numero"],
                    "canal": can["numero"],
                    "porcentaje": porcentaje,
                })

        return {"awareness": awareness, "intenciones": intenciones, "habitos": habitos}

    # --- ESTUDIO 2: Panel de consumidores ---
    def _estudio_2_panel_consumidores(self):
        resultado = []
        for marca in self.marcas:
            for seg in self.segmentos:
                porcion = round(random.uniform(0.01, 0.25), 3)
                resultado.append({
                    "marca": marca["nombre"],
                    "segmento": seg["numero"],
                    "porcion_mercado": porcion,
                    "ventas_unidades": round(random.uniform(50, 500), 0),
                })
        return {"panel": resultado}

    # --- ESTUDIO 3: Panel de distribuidores ---
    def _estudio_3_panel_distribuidores(self):
        resultado = []
        for marca in self.marcas:
            for can in self.canales:
                porcion = round(random.uniform(0.02, 0.30), 3)
                resultado.append({
                    "marca": marca["nombre"],
                    "canal": can["numero"],
                    "porcion_mercado": porcion,
                    "ventas_unidades": round(random.uniform(50, 300), 0),
                })
        return {"panel": resultado}

    # --- ESTUDIO 4: Escalas semánticas ---
    def _estudio_4_escalas(self):
        escalas = []
        for marca in self.marcas:
            escalas.append({
                "marca": marca["nombre"],
                "valor": round(random.uniform(2, 6), 2),
                "potencia": round(random.uniform(2, 6), 2),
                "diseno": round(random.uniform(2, 6), 2),
            })

        ideales = []
        for seg in self.segmentos:
            ideales.append({
                "segmento": seg["numero"],
                "valor": round(random.uniform(3, 5.5), 2),
                "potencia": round(random.uniform(3, 5.5), 2),
                "diseno": round(random.uniform(3, 5.5), 2),
            })

        return {"escalas": escalas, "ideales": ideales}

    # --- ESTUDIO 5: Mapa perceptual ---
    def _estudio_5_mapa_perceptual(self):
        marcas_mapa = []
        for marca in self.marcas:
            x = marca.get("posicion_x", 0) or round(random.uniform(-15, 15), 1)
            y = marca.get("posicion_y", 0) or round(random.uniform(-15, 15), 1)
            marcas_mapa.append({
                "marca": marca["nombre"],
                "posicion_x": x,
                "posicion_y": y,
            })

        segmentos_mapa = []
        for seg in self.segmentos:
            segmentos_mapa.append({
                "segmento": seg["numero"],
                "posicion_x": seg["valor_ideal_x"],
                "posicion_y": seg["valor_ideal_y"],
            })

        return {"marcas": marcas_mapa, "segmentos": segmentos_mapa}

    # --- ESTUDIO 6: Pronóstico de mercado ---
    def _estudio_6_pronostico(self):
        pronosticos = []
        for seg in self.segmentos:
            pronosticos.append({
                "segmento": seg["numero"],
                "unidades_esperadas": round(random.uniform(100, 500), 0),
            })
        return {"pronosticos": pronosticos}

    # --- ESTUDIO 12: Publicidad competitiva ---
    def _estudio_12_publicidad_competencia(self):
        resultado = []
        for marca in self.marcas:
            resultado.append({
                "marca": marca["nombre"],
                "publicidad_estimada": round(random.uniform(500, 5000), 0),
            })
        return {"publicidad": resultado}

    # --- ESTUDIO 13: Fuerza de ventas competitiva ---
    def _estudio_13_fuerza_ventas_competencia(self):
        resultado = []
        for marca in self.marcas:
            for can in self.canales:
                resultado.append({
                    "marca": marca["nombre"],
                    "canal": can["numero"],
                    "vendedores_estimados": random.randint(5, 50),
                })
        return {"fuerza_ventas": resultado}

    # --- ESTUDIO 14: Test de fuerza de ventas ---
    def _estudio_14_test_fuerza_ventas(self):
        resultado = []
        for marca in self.marcas:
            for can in self.canales:
                resultado.append({
                    "marca": marca["nombre"],
                    "canal": can["numero"],
                    "detallistas_estimados": random.randint(1000, 8000),
                    "porcion_mercado": round(random.uniform(0.02, 0.15), 3),
                })
        return {"test": resultado}

    # --- ESTUDIO 15: Test de publicidad ---
    def _estudio_15_test_publicidad(self):
        resultado = []
        for marca in self.marcas:
            resultado.append({
                "marca": marca["nombre"],
                "nuevo_awareness": round(random.uniform(0.20, 0.60), 3),
                "nueva_porcion": round(random.uniform(0.02, 0.15), 3),
            })
        return {"test": resultado}