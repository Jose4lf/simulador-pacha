"""
Utilidades de seguridad de PACHA.

Centraliza:
- generación de contraseñas temporales aleatorias;
- política de contraseñas;
- verificación de hashes (con compatibilidad para valores legados);
- tokens CSRF;
- límite básico de intentos de login.

El límite de intentos vive en memoria: es una protección por proceso.
Con varios workers de Gunicorn cada uno mantiene su propio contador.
"""
import hmac
import secrets
import string
import threading
import time
from collections import deque

from werkzeug.security import check_password_hash, generate_password_hash

LONGITUD_MINIMA = 8
LONGITUD_MAXIMA = 128
LONGITUD_TEMPORAL = 12

# Sin caracteres ambiguos (O/0, I/l/1) para dictarlas por teléfono o escribirlas.
_ALFABETO = "".join(
    c for c in (string.ascii_letters + string.digits) if c not in "O0Il1"
)

MAX_INTENTOS_LOGIN = 5
VENTANA_INTENTOS_SEGUNDOS = 15 * 60
_intentos = {}
_lock_intentos = threading.Lock()


def generar_password_temporal(longitud=LONGITUD_TEMPORAL):
    """Genera una contraseña aleatoria que cumple la política vigente."""
    if longitud < LONGITUD_MINIMA:
        longitud = LONGITUD_MINIMA

    while True:
        candidata = "".join(secrets.choice(_ALFABETO) for _ in range(longitud))
        if (any(c.islower() for c in candidata)
                and any(c.isupper() for c in candidata)
                and any(c.isdigit() for c in candidata)):
            return candidata


def validar_password(password, username=None):
    """Devuelve (es_valida, mensaje). No registra la contraseña."""
    if not password or not isinstance(password, str):
        return False, "La contraseña es obligatoria."

    if len(password) < LONGITUD_MINIMA:
        return False, f"La contraseña debe tener al menos {LONGITUD_MINIMA} caracteres."
    if len(password) > LONGITUD_MAXIMA:
        return False, f"La contraseña no puede superar {LONGITUD_MAXIMA} caracteres."
    if not any(c.isalpha() for c in password):
        return False, "La contraseña debe incluir al menos una letra."
    if not any(c.isdigit() for c in password):
        return False, "La contraseña debe incluir al menos un número."
    if password.strip() != password:
        return False, "La contraseña no puede empezar ni terminar con espacios."
    if username and password.lower() == str(username).lower():
        return False, "La contraseña no puede ser igual al nombre de usuario."
    return True, ""


def hashear_password(password):
    return generate_password_hash(password)


def es_hash(valor):
    """True si el valor parece un hash de Werkzeug y no texto plano."""
    if not valor:
        return False
    return str(valor).startswith(("scrypt:", "pbkdf2:", "argon2"))


def verificar_password(hash_guardado, password):
    """Verifica un hash; acepta valores legados en texto plano."""
    if not hash_guardado or password is None:
        return False
    try:
        if es_hash(hash_guardado):
            return check_password_hash(hash_guardado, password)
        return hmac.compare_digest(str(hash_guardado), str(password))
    except (ValueError, TypeError):
        return False


def generar_csrf_token():
    return secrets.token_urlsafe(32)


def tokens_iguales(a, b):
    if not a or not b:
        return False
    return hmac.compare_digest(str(a), str(b))


def _clave_intentos(usuario, ip):
    return f"{(usuario or '').strip().lower()}|{ip or ''}"


def _purgar(cola, ahora):
    limite = ahora - VENTANA_INTENTOS_SEGUNDOS
    while cola and cola[0] < limite:
        cola.popleft()


def login_bloqueado(usuario, ip, ahora=None):
    """Indica si la combinación usuario/IP superó los intentos permitidos."""
    ahora = time.monotonic() if ahora is None else ahora
    clave = _clave_intentos(usuario, ip)
    with _lock_intentos:
        cola = _intentos.get(clave)
        if not cola:
            return False
        _purgar(cola, ahora)
        if not cola:
            _intentos.pop(clave, None)
            return False
        return len(cola) >= MAX_INTENTOS_LOGIN


def segundos_para_desbloqueo(usuario, ip, ahora=None):
    ahora = time.monotonic() if ahora is None else ahora
    clave = _clave_intentos(usuario, ip)
    with _lock_intentos:
        cola = _intentos.get(clave)
        if not cola:
            return 0
        _purgar(cola, ahora)
        if len(cola) < MAX_INTENTOS_LOGIN:
            return 0
        return max(1, int(VENTANA_INTENTOS_SEGUNDOS - (ahora - cola[0])))


def registrar_fallo_login(usuario, ip, ahora=None):
    ahora = time.monotonic() if ahora is None else ahora
    clave = _clave_intentos(usuario, ip)
    with _lock_intentos:
        cola = _intentos.setdefault(clave, deque())
        _purgar(cola, ahora)
        cola.append(ahora)


def limpiar_intentos_login(usuario, ip):
    clave = _clave_intentos(usuario, ip)
    with _lock_intentos:
        _intentos.pop(clave, None)


def limpiar_todos_los_intentos():
    """Solo para pruebas y tareas administrativas."""
    with _lock_intentos:
        _intentos.clear()
