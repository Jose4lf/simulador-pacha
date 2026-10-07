"""
Generador de nombres de marcas estilo LABSAG.
Formato: S + [A/E/I/O/U según equipo] + 2 letras libres

Equipo 1 → A (SAKA, SATO, SAMA, SAKE, SAKO)
Equipo 2 → E (SEKA, SETO, SEMA, SEKE, SEKO)
Equipo 3 → I (SIKA, SITO, SIMA, SIKE, SIKO)
Equipo 4 → O (SOKA, SOTO, SOMA, SOKE, SOKO)
Equipo 5 → U (SUKA, SUTO, SUMA, SUKE, SUKO)
"""

VOCALES_EQUIPO = {
    1: "A",
    2: "E",
    3: "I",
    4: "O",
    5: "U",
    6: "A",  # Si hay más de 5 equipos, vuelve a empezar
    7: "E",
    8: "I",
    9: "O",
    10: "U",
}

# Sufijos disponibles para las 2 letras finales
SUFIJOS_SONITE = [
    "KA", "TO", "MA", "KE", "KO",
    "PA", "RE", "TA", "NA", "LA",
    "RA", "SA", "VA", "ZA", "DA",
]

# Sufijos para VODITE (letra inicial V)
SUFIJOS_VODITE = [
    "RO", "CA", "TA", "LA", "NA",
    "MA", "PA", "RA", "SA", "VA",
]


def generar_nombres_equipo(numero_equipo, tipo="SONITE", cantidad=5, ya_usados=None):
    """
    Genera nombres de marcas para un equipo.
    
    Args:
        numero_equipo: 1-5 (o más)
        tipo: "SONITE" (empieza con S) o "VODITE" (empieza con V)
        cantidad: número de nombres a generar (max 5)
        ya_usados: set de nombres que no se pueden repetir
    
    Returns:
        Lista de nombres únicos
    """
    if ya_usados is None:
        ya_usados = set()
    
    vocal = VOCALES_EQUIPO.get(numero_equipo, "A")
    letra_inicial = "S" if tipo == "SONITE" else "V"
    sufijos = SUFIJOS_SONITE if tipo == "SONITE" else SUFIJOS_VODITE
    
    nombres = []
    for sufijo in sufijos:
        if len(nombres) >= cantidad:
            break
        
        nombre = f"{letra_inicial}{vocal}{sufijo}"
        
        if nombre not in ya_usados:
            nombres.append(nombre)
            ya_usados.add(nombre)
    
    return nombres


def generar_nombres_todos_equipos(num_equipos, tipo="SONITE", marcas_por_equipo=2):
    """
    Genera nombres de marcas para TODOS los equipos.
    
    Returns:
        dict { numero_equipo: [nombres] }
    """
    ya_usados = set()
    resultado = {}
    
    for num_equipo in range(1, num_equipos + 1):
        nombres = generar_nombres_equipo(
            num_equipo, tipo, marcas_por_equipo, ya_usados
        )
        resultado[num_equipo] = nombres
    
    return resultado


def vocal_equipo(numero_equipo):
    """Devuelve la vocal correspondiente al equipo."""
    return VOCALES_EQUIPO.get(numero_equipo, "A")


def validar_nombre_labsag(nombre, numero_equipo, tipo="SONITE"):
    """
    Valida si un nombre cumple el formato LABSAG.
    
    Returns:
        (bool, str) → (es_válido, mensaje_error)
    """
    if len(nombre) != 4:
        return False, "El nombre debe tener exactamente 4 letras"
    
    letra_inicial_esperada = "S" if tipo == "SONITE" else "V"
    if nombre[0].upper() != letra_inicial_esperada:
        return False, f"El nombre debe empezar con '{letra_inicial_esperada}'"
    
    vocal_esperada = vocal_equipo(numero_equipo)
    if nombre[1].upper() != vocal_esperada:
        return False, f"La segunda letra debe ser '{vocal_esperada}' para el equipo {numero_equipo}"
    
    if not nombre.isalpha():
        return False, "Solo se permiten letras"
    
    return True, ""