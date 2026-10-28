"""
Servicio de proyectos de I&D — PACHA (Etapa 5)
==============================================

Cierra el ciclo que el Manual ya describe:

1. El equipo registra un proyecto (marca existente o marca nueva) con sus seis
   atributos objetivo y un presupuesto anual.
2. Al procesar la ronda de ese año, I&D evalúa el proyecto con las reglas de
   ``core.modelo_id`` y guarda el resultado (aprobado o fallido, atributo
   crítico y presupuesto adicional sugerido).
3. En el año siguiente, el equipo aplica el proyecto aprobado escribiendo su
   nombre junto a la marca en la hoja de decisiones. Al procesar esa ronda, la
   marca recibe los atributos, el costo unitario y el índice de calidad.
4. Una marca nueva solo nace cuando se aplica un proyecto aprobado de tipo
   "marca nueva" en una fila nueva de la hoja de decisiones.

Límites tomados del manual
--------------------------
- Nombre ``P`` + ``S``/``V`` + tres letras (PSAMA).
- 100 a 1000 miles de Bs por proyecto Sonite.
- Máximo 4 proyectos por año y 5 nombres de proyecto por simulación.
- Un proyecto fallido se reenvía con el mismo nombre y atributos, subiendo el
  presupuesto.
"""
import re

from infraestructura.database import get_session
from core.modelo_id import (
    COSTO_SOBRE_ESTANDAR_MAXIMO, MAX_PROYECTOS_POR_ANIO,
    MAX_PROYECTOS_POR_SIMULACION, NOMBRES_ATRIBUTOS, PRESUPUESTO_MAXIMO,
    PRESUPUESTO_MINIMO, PRESUPUESTO_POR_COSTO, PRESUPUESTO_POR_UNIDAD,
    RANGOS_SONITE, costo_estandar, evaluar_proyecto, indice_calidad,
    presupuesto_requerido, probabilidad_exito, validar_atributos,
    validar_nombre,
)
from core.models import (
    AtributoFisico, Canal, Equipo, FuerzaVentas, Industria, LogActividad,
    Marca, ProyectoAtributo, ProyectoID, ProyectoResultado,
)

ATRIBUTOS_REFERENCIA_DEFECTO = {
    1: 10.0, 2: 5.0, 3: 50.0, 4: 20.0, 5: 20.0, 6: 100.0,
}
NOMBRE_MARCA_VALIDO = r"^[A-Z]{4,10}$"
MAX_MARCAS_POR_EQUIPO = 5

ESTADOS = {
    "en_desarrollo": "En desarrollo",
    "aprobado": "Aprobado",
    "aplicado": "Aplicado",
    "fallido": "Fallido",
    "cancelado": "Cancelado",
}


def _r(valor, decimales=2):
    return round(float(valor), decimales)


def _atributos_marca(session, marca, anio):
    """Atributos vigentes de la marca (último año disponible <= anio)."""
    filas = session.query(AtributoFisico).filter(
        AtributoFisico.marca_id == marca.id,
        AtributoFisico.anio <= anio,
    ).order_by(AtributoFisico.anio.desc(), AtributoFisico.numero).all()
    if not filas:
        return {}
    ultimo = filas[0].anio
    return {f.numero: float(f.valor or 0) for f in filas if f.anio == ultimo}


def _atributos_proyecto(proyecto):
    return {
        a.numero: float(a.valor_objetivo or 0)
        for a in proyecto.atributos
    }


def _referencia_equipo(session, equipo, anio):
    """Perfil de referencia para una marca nueva: promedio del equipo."""
    marcas = session.query(Marca).filter_by(
        equipo_id=equipo.id, activa=True
    ).all()
    acumulado = {}
    for marca in marcas:
        atributos = _atributos_marca(session, marca, anio)
        for numero, valor in atributos.items():
            acumulado.setdefault(numero, []).append(valor)
    referencia = {}
    for numero in range(1, 7):
        valores = acumulado.get(numero)
        referencia[numero] = (
            _r(sum(valores) / len(valores)) if valores
            else ATRIBUTOS_REFERENCIA_DEFECTO[numero]
        )
    return referencia


def _guardar_atributos(session, marca, valores, anio):
    for numero in range(1, 7):
        fila = session.query(AtributoFisico).filter_by(
            marca_id=marca.id, numero=numero, anio=anio
        ).first()
        if fila:
            fila.valor = float(valores[numero])
        else:
            session.add(AtributoFisico(
                marca_id=marca.id, numero=numero,
                valor=float(valores[numero]), anio=anio,
            ))


def _aplicar_atributos(session, marca, valores, anio):
    _guardar_atributos(session, marca, valores, anio)
    marca.costo_unitario = float(valores.get(6) or 0)
    marca.calidad_actual = indice_calidad(valores)


class ProyectoService:

    # ------------------------------------------------------------------
    # Lectura
    # ------------------------------------------------------------------
    @staticmethod
    def contexto_equipo(equipo_id):
        """Datos para la pantalla de I&D del alumno."""
        session = get_session()
        try:
            equipo = session.query(Equipo).filter_by(id=equipo_id).first()
            if not equipo:
                return None
            industria = session.query(Industria).filter_by(
                id=equipo.industria_id
            ).first()
            if not industria:
                return None
            anio = int(industria.anio_actual or 0)
            return {
                "equipo": {
                    "id": equipo.id, "numero": equipo.numero,
                    "nombre_empresa": equipo.nombre_empresa,
                },
                "industria": {
                    "id": industria.id, "nombre": industria.nombre,
                    "anio_actual": anio,
                    "anio_maximo": int(industria.anio_maximo or 10),
                    "estado": industria.estado,
                    "permitir_envio": bool(industria.permitir_envio),
                },
                "marcas": ProyectoService._marcas(session, equipo, anio),
                "proyectos": ProyectoService._proyectos(session, equipo.id),
                "aprobados": ProyectoService._aprobados(session, equipo.id, anio),
                "proyectos_este_anio": session.query(ProyectoID).filter(
                    ProyectoID.equipo_id == equipo.id,
                    ProyectoID.anio_inicio == anio,
                    ProyectoID.estado != "cancelado",
                ).count(),
                "nombres_usados": ProyectoService._nombres_usados(
                    session, equipo.id
                ),
                "limites": {
                    "por_anio": MAX_PROYECTOS_POR_ANIO,
                    "por_simulacion": MAX_PROYECTOS_POR_SIMULACION,
                    "marcas": MAX_MARCAS_POR_EQUIPO,
                    "presupuesto_min": PRESUPUESTO_MINIMO,
                    "presupuesto_max": PRESUPUESTO_MAXIMO,
                },
                "rangos": [
                    {"numero": numero, "nombre": NOMBRES_ATRIBUTOS[numero],
                     "minimo": limites[0], "maximo": limites[1]}
                    for numero, limites in RANGOS_SONITE.items()
                ],
                "tarifas": [
                    {"numero": numero, "nombre": NOMBRES_ATRIBUTOS[numero],
                     "tarifa": PRESUPUESTO_POR_UNIDAD[numero]}
                    for numero in range(1, 6)
                ] + [{
                    "numero": 6, "nombre": "Reducir el costo",
                    "tarifa": PRESUPUESTO_POR_COSTO,
                }],
                "anio_bloqueado": anio == 0 or industria.estado == "finalizada"
                                  or not industria.permitir_envio,
            }
        finally:
            session.close()

    @staticmethod
    def _marcas(session, equipo, anio):
        marcas = session.query(Marca).filter_by(
            equipo_id=equipo.id, activa=True
        ).order_by(Marca.id).all()
        resultado = []
        for marca in marcas:
            atributos = _atributos_marca(session, marca, anio)
            resultado.append({
                "id": marca.id,
                "nombre": marca.nombre,
                "costo_unitario": float(marca.costo_unitario or 0),
                "calidad": float(marca.calidad_actual or 0),
                "atributos": [
                    {"numero": numero, "nombre": NOMBRES_ATRIBUTOS[numero],
                     "valor": atributos.get(numero)}
                    for numero in range(1, 7)
                ],
            })
        return resultado

    @staticmethod
    def _proyectos(session, equipo_id):
        proyectos = session.query(ProyectoID).filter_by(
            equipo_id=equipo_id
        ).order_by(ProyectoID.anio_inicio.desc(), ProyectoID.id.desc()).all()
        resultado = []
        for proyecto in proyectos:
            marca = None
            if proyecto.marca_destino_id:
                marca = session.query(Marca).filter_by(
                    id=proyecto.marca_destino_id
                ).first()
            resultados = session.query(ProyectoResultado).filter_by(
                proyecto_id=proyecto.id
            ).order_by(ProyectoResultado.anio.desc()).all()
            atributos = _atributos_proyecto(proyecto)
            resultado.append({
                "id": proyecto.id,
                "nombre": proyecto.nombre,
                "estado": proyecto.estado,
                "estado_etiqueta": ESTADOS.get(
                    proyecto.estado, proyecto.estado
                ),
                "anio_inicio": proyecto.anio_inicio,
                "anio_aprobacion": proyecto.anio_aprobacion,
                "anio_aplicacion": proyecto.anio_aplicacion,
                "gastos": float(proyecto.gastos or 0),
                "presupuesto_miles": _r(float(proyecto.gastos or 0) / 1000.0),
                "es_nueva_marca": bool(proyecto.es_nueva_marca),
                "marca_destino": marca.nombre if marca else (
                    "Marca nueva" if proyecto.es_nueva_marca else "—"
                ),
                "costo_estandar": float(proyecto.costo_estandar or 0),
                "presupuesto_normal": float(proyecto.presupuesto_normal or 0),
                "probabilidad": float(proyecto.probabilidad_calculada or 0),
                "atributos": [
                    {"numero": numero, "nombre": NOMBRES_ATRIBUTOS[numero],
                     "valor": atributos.get(numero)}
                    for numero in range(1, 7)
                ],
                "resultados": [{
                    "anio": r.anio,
                    "resultado": r.resultado,
                    "probabilidad": float(r.probabilidad or 0),
                    "atributo_fallido": r.atributo_fallido,
                    "presupuesto_adicional": float(r.presupuesto_adicional or 0),
                    "costo_minimo": r.costo_minimo,
                    "detalle": r.detalle or "",
                } for r in resultados],
            })
        return resultado

    @staticmethod
    def _aprobados(session, equipo_id, anio):
        proyectos = session.query(ProyectoID).filter(
            ProyectoID.equipo_id == equipo_id,
            ProyectoID.estado == "aprobado",
            ProyectoID.anio_aprobacion <= anio,
        ).order_by(ProyectoID.nombre).all()
        return [{
            "id": p.id,
            "nombre": p.nombre,
            "es_nueva_marca": bool(p.es_nueva_marca),
            "marca_destino_id": p.marca_destino_id,
            "atributos": _atributos_proyecto(p),
        } for p in proyectos]

    @staticmethod
    def _nombres_usados(session, equipo_id):
        filas = session.query(ProyectoID.nombre).filter(
            ProyectoID.equipo_id == equipo_id,
            ProyectoID.estado != "cancelado",
        ).distinct().all()
        return len(filas)

    @staticmethod
    def listar_por_industria(industria_id):
        """Vista del profesor: proyectos de todos los equipos."""
        session = get_session()
        try:
            equipos = session.query(Equipo).filter_by(
                industria_id=industria_id
            ).order_by(Equipo.numero).all()
            return [{
                "equipo_id": eq.id,
                "numero": eq.numero,
                "nombre_empresa": eq.nombre_empresa,
                "proyectos": ProyectoService._proyectos(session, eq.id),
            } for eq in equipos]
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Alta y cancelación
    # ------------------------------------------------------------------
    @staticmethod
    def crear_proyecto(equipo_id, anio, datos, usuario_id=None):
        session = get_session()
        try:
            equipo = session.query(Equipo).filter_by(id=equipo_id).first()
            if not equipo:
                return {"error": "Equipo no encontrado"}
            if equipo.bloqueado:
                return {"error": "El equipo está bloqueado por el profesor"}
            industria = session.query(Industria).filter_by(
                id=equipo.industria_id
            ).first()
            if not industria:
                return {"error": "Industria no encontrada"}

            anio = int(anio)
            if anio != int(industria.anio_actual or 0):
                return {"error": "Solo puedes registrar proyectos del período actual."}
            if anio <= 0:
                return {"error": "El Año 0 es de diagnóstico: I&D empieza en el Año 1."}
            if industria.estado == "finalizada":
                return {"error": "La simulación está finalizada."}
            if not industria.permitir_envio:
                return {"error": "El envío de decisiones está deshabilitado."}

            nombre = (datos.get("nombre") or "").strip().upper()
            if not validar_nombre(nombre):
                return {"error": (
                    "Nombre de proyecto inválido. Usa P + S/V + tres letras "
                    "(por ejemplo PSAMA)."
                )}

            atributos = {}
            for numero in range(1, 7):
                try:
                    atributos[numero] = float(datos["atributos"][numero - 1])
                except (KeyError, IndexError, TypeError, ValueError):
                    return {"error": "Faltan atributos o no son numéricos."}
            ok, mensaje = validar_atributos(atributos)
            if not ok:
                return {"error": mensaje}

            try:
                presupuesto = float(datos.get("presupuesto") or 0)
            except (TypeError, ValueError):
                return {"error": "El presupuesto no es numérico."}
            if presupuesto < PRESUPUESTO_MINIMO or presupuesto > PRESUPUESTO_MAXIMO:
                return {"error": (
                    f"El presupuesto debe estar entre {PRESUPUESTO_MINIMO:g} y "
                    f"{PRESUPUESTO_MAXIMO:g} miles de Bs (Sonite)."
                )}

            # Destino: marca existente del equipo o marca nueva.
            marca_id = datos.get("marca_id")
            marca_destino = None
            nueva = False
            nombre_marca_nueva = None
            if marca_id:
                marca_destino = session.query(Marca).filter_by(
                    id=int(marca_id), equipo_id=equipo.id, activa=True
                ).first()
                if not marca_destino:
                    return {"error": "La marca destino no pertenece a tu equipo."}
                actuales = _atributos_marca(session, marca_destino, anio)
                if not actuales:
                    return {"error": (
                        "La marca no tiene atributos físicos registrados; "
                        "no se puede calcular el esfuerzo de I&D."
                    )}
            else:
                nueva = True
                nombre_marca_nueva = (
                    datos.get("marca_nueva") or ""
                ).strip().upper()
                if not re.match(NOMBRE_MARCA_VALIDO, nombre_marca_nueva):
                    return {"error": (
                        "El nombre de la marca nueva debe tener entre 4 y 10 "
                        "letras mayúsculas."
                    )}
                existente = session.query(Marca).filter_by(
                    equipo_id=equipo.id, nombre=nombre_marca_nueva
                ).first()
                if existente:
                    return {"error": f"Ya existe una marca {nombre_marca_nueva} en tu equipo."}
                activas = session.query(Marca).filter_by(
                    equipo_id=equipo.id, activa=True
                ).count()
                if activas >= MAX_MARCAS_POR_EQUIPO:
                    return {"error": (
                        f"Tu equipo ya tiene {MAX_MARCAS_POR_EQUIPO} marcas "
                        "activas; no puede lanzar otra."
                    )}
                actuales = _referencia_equipo(session, equipo, anio)

            normal = presupuesto_requerido(actuales, atributos)
            if normal <= 0:
                return {"error": (
                    "El proyecto no cambia ningún atributo ni reduce el costo: "
                    "no hay esfuerzo de I&D que financiar."
                )}
            if normal > PRESUPUESTO_MAXIMO:
                return {"error": (
                    f"El presupuesto normal del proyecto ({normal:,.2f} miles de Bs) "
                    f"supera el máximo Sonite de {PRESUPUESTO_MAXIMO:g}. "
                    "Reduce el cambio solicitado."
                )}

            # Reglas de nombres y de reenvío.
            intentos = session.query(ProyectoID).filter(
                ProyectoID.equipo_id == equipo.id,
                ProyectoID.nombre == nombre,
            ).order_by(ProyectoID.anio_inicio.desc(), ProyectoID.id.desc()).all()
            ultimo = intentos[0] if intentos else None
            reenvio = False

            if ultimo is not None:
                if ultimo.estado in ("aprobado", "aplicado"):
                    return {"error": (
                        f"El proyecto {nombre} ya fue aprobado. Usa otro nombre."
                    )}
                if ultimo.estado == "en_desarrollo":
                    return {"error": f"El proyecto {nombre} ya está en desarrollo este año."}
                if ultimo.estado == "cancelado":
                    return {"error": (
                        f"El nombre {nombre} fue cancelado; usa otro nombre."
                    )}
                if ultimo.estado == "fallido":
                    anteriores = _atributos_proyecto(ultimo)
                    if any(
                        abs(anteriores.get(n, 0) - atributos[n]) > 1e-6
                        for n in range(1, 7)
                    ):
                        return {"error": (
                            "Para reenviar un proyecto fallido debes mantener "
                            "los mismos atributos y subir el presupuesto."
                        )}
                    if presupuesto <= float(ultimo.gastos or 0) / 1000.0 + 1e-6:
                        return {"error": (
                            "Para reenviar un proyecto fallido debes aumentar "
                            "el presupuesto respecto del intento anterior."
                        )}
                    reenvio = True

            if not reenvio:
                usados = ProyectoService._nombres_usados(session, equipo.id)
                if usados >= MAX_PROYECTOS_POR_SIMULACION:
                    return {"error": (
                        f"Tu equipo alcanzó el máximo de "
                        f"{MAX_PROYECTOS_POR_SIMULACION} proyectos de I&D."
                    )}

            proyectos_anio = session.query(ProyectoID).filter(
                ProyectoID.equipo_id == equipo.id,
                ProyectoID.anio_inicio == anio,
                ProyectoID.estado != "cancelado",
            ).count()
            if proyectos_anio >= MAX_PROYECTOS_POR_ANIO:
                return {"error": (
                    f"El Centro de I&D admite máximo "
                    f"{MAX_PROYECTOS_POR_ANIO} proyectos por año."
                )}

            estandar = costo_estandar(atributos)
            limite = estandar * (1.0 + COSTO_SOBRE_ESTANDAR_MAXIMO)
            estimacion = {
                "presupuesto_normal": normal,
                "probabilidad": probabilidad_exito(presupuesto, normal),
                "costo_estandar": estandar,
                "costo_objetivo": atributos[6],
                "costo_maximo": _r(limite),
                "fracaso_automatico": atributos[6] > limite + 0.01,
            }

            proyecto = ProyectoID(
                equipo_id=equipo.id,
                nombre=nombre,
                anio_inicio=anio,
                estado="en_desarrollo",
                gastos=presupuesto * 1000.0,
                costo_estandar=estandar,
                presupuesto_normal=normal,
                probabilidad_calculada=estimacion["probabilidad"],
                marca_destino_id=marca_destino.id if marca_destino else None,
                es_nueva_marca=nueva,
            )
            session.add(proyecto)
            session.flush()
            for numero in range(1, 7):
                session.add(ProyectoAtributo(
                    proyecto_id=proyecto.id, numero=numero,
                    valor_objetivo=atributos[numero],
                ))

            session.add(LogActividad(
                usuario_id=usuario_id,
                accion="proyecto_id_creado",
                detalle=(
                    f"Equipo {equipo.id}, {nombre}, año {anio}, "
                    f"presupuesto {presupuesto:g} miles Bs"
                )[:255],
            ))
            session.commit()
            return {
                "ok": True,
                "proyecto_id": proyecto.id,
                "nombre": nombre,
                "estimacion": estimacion,
                "marca_nueva": nombre_marca_nueva,
            }
        except Exception as exc:
            session.rollback()
            return {"error": str(exc)}
        finally:
            session.close()

    @staticmethod
    def cancelar_proyecto(equipo_id, proyecto_id, usuario_id=None):
        session = get_session()
        try:
            proyecto = session.query(ProyectoID).filter_by(
                id=proyecto_id, equipo_id=equipo_id
            ).first()
            if not proyecto:
                return {"error": "Proyecto no encontrado"}
            if proyecto.estado != "en_desarrollo":
                return {"error": "Solo se pueden cancelar proyectos en desarrollo."}
            equipo = session.query(Equipo).filter_by(id=equipo_id).first()
            industria = session.query(Industria).filter_by(
                id=equipo.industria_id
            ).first()
            if proyecto.anio_inicio != int(industria.anio_actual or 0):
                return {"error": "Solo puedes cancelar proyectos del período actual."}
            proyecto.estado = "cancelado"
            session.add(LogActividad(
                usuario_id=usuario_id,
                accion="proyecto_id_cancelado",
                detalle=f"Equipo {equipo_id}, proyecto {proyecto.nombre}"[:255],
            ))
            session.commit()
            return {"ok": True}
        except Exception as exc:
            session.rollback()
            return {"error": str(exc)}
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Procesamiento de la ronda (invocado por SimulacionService)
    # ------------------------------------------------------------------
    @staticmethod
    def evaluar_proyectos(session, industria, equipos, anio):
        """Evalúa los proyectos iniciados en ``anio`` y guarda el resultado."""
        ids = [eq.id for eq in equipos]
        proyectos = session.query(ProyectoID).filter(
            ProyectoID.equipo_id.in_(ids),
            ProyectoID.anio_inicio == anio,
            ProyectoID.estado == "en_desarrollo",
        ).order_by(ProyectoID.id).all()

        aprobados = 0
        fallidos = []
        for proyecto in proyectos:
            objetivo = _atributos_proyecto(proyecto)
            if proyecto.marca_destino_id:
                marca = session.query(Marca).filter_by(
                    id=proyecto.marca_destino_id
                ).first()
                actuales = (
                    _atributos_marca(session, marca, anio) if marca else {}
                )
            else:
                equipo = session.query(Equipo).filter_by(
                    id=proyecto.equipo_id
                ).first()
                actuales = _referencia_equipo(session, equipo, anio)

            resultado = evaluar_proyecto(
                actuales, objetivo, float(proyecto.gastos or 0) / 1000.0,
                equipo_id=proyecto.equipo_id,
                nombre=proyecto.nombre,
                anio=anio,
                semilla=f"industria-{industria.id}",
            )

            proyecto.estado = "aprobado" if resultado["aprobado"] else "fallido"
            if resultado["aprobado"]:
                proyecto.anio_aprobacion = anio + 1
                aprobados += 1
            else:
                fallidos.append({
                    "proyecto": proyecto.nombre,
                    "equipo_id": proyecto.equipo_id,
                    "atributo_fallido": NOMBRES_ATRIBUTOS.get(
                        resultado["atributo_fallido"], "—"
                    ),
                    "adicional": resultado["presupuesto_adicional"],
                    "detalle": resultado["detalle"],
                })

            session.add(ProyectoResultado(
                proyecto_id=proyecto.id,
                anio=anio,
                resultado="aprobado" if resultado["aprobado"] else "fallido",
                probabilidad=resultado["probabilidad"],
                presupuesto_normal=resultado["presupuesto_normal"],
                presupuesto_asignado=resultado["presupuesto_asignado"],
                atributo_fallido=resultado["atributo_fallido"],
                presupuesto_adicional=resultado["presupuesto_adicional"],
                costo_estandar=resultado["costo_estandar"],
                costo_minimo=resultado["costo_minimo"],
                detalle=resultado["detalle"][:255],
            ))

        return {
            "evaluados": len(proyectos),
            "aprobados": aprobados,
            "fallidos": fallidos,
        }

    @staticmethod
    def aplicar_proyectos_decisiones(session, equipos, decisiones, anio):
        """Aplica los proyectos aprobados que los equipos usan en su hoja."""
        ids = [eq.id for eq in equipos]
        aprobados = {}
        for proyecto in session.query(ProyectoID).filter(
            ProyectoID.equipo_id.in_(ids),
            ProyectoID.estado == "aprobado",
            ProyectoID.anio_aprobacion <= anio,
        ).all():
            aprobados.setdefault(proyecto.equipo_id, {})[
                proyecto.nombre
            ] = proyecto

        aplicados = []
        marcas_nuevas = []
        avisos = []

        for equipo in equipos:
            decision = decisiones.get(equipo.id)
            if not decision:
                continue
            marcas = session.query(Marca).filter_by(
                equipo_id=equipo.id, activa=True
            ).all()
            por_nombre = {m.nombre.upper(): m for m in marcas}
            disponibles = aprobados.get(equipo.id, {})

            for dm in decision.marcas:
                nombre_marca = (dm.marca_nombre or "").strip().upper()
                nombre_proyecto = (dm.proyecto_id_nombre or "").strip().upper()

                if nombre_marca in por_nombre:
                    if not nombre_proyecto:
                        continue
                    proyecto = disponibles.get(nombre_proyecto)
                    if not proyecto:
                        avisos.append(
                            f"Equipo {equipo.numero}: el proyecto {nombre_proyecto} "
                            f"de la marca {nombre_marca} no está aprobado; se ignoró."
                        )
                        continue
                    if proyecto.es_nueva_marca:
                        avisos.append(
                            f"Equipo {equipo.numero}: {nombre_proyecto} es para "
                            "una marca nueva y se usó en una marca existente."
                        )
                        continue
                    marca = por_nombre[nombre_marca]
                    if (proyecto.marca_destino_id
                            and proyecto.marca_destino_id != marca.id):
                        avisos.append(
                            f"Equipo {equipo.numero}: {nombre_proyecto} fue "
                            f"aprobado para otra marca y no se aplicó a {nombre_marca}."
                        )
                        continue
                    valores = _atributos_proyecto(proyecto)
                    _aplicar_atributos(session, marca, valores, anio + 1)
                    proyecto.estado = "aplicado"
                    proyecto.anio_aplicacion = anio + 1
                    aplicados.append({
                        "equipo_id": equipo.id, "proyecto": proyecto.nombre,
                        "marca": marca.nombre, "nueva": False,
                    })
                    continue

                # Fila que no corresponde a una marca existente: marca nueva.
                if not nombre_proyecto:
                    continue
                proyecto = disponibles.get(nombre_proyecto)
                if not proyecto or not proyecto.es_nueva_marca:
                    avisos.append(
                        f"Equipo {equipo.numero}: la marca {nombre_marca} no "
                        "existe y no hay un proyecto aprobado de marca nueva."
                    )
                    continue
                if session.query(Marca).filter_by(
                    equipo_id=equipo.id, nombre=nombre_marca
                ).first():
                    avisos.append(
                        f"Equipo {equipo.numero}: la marca {nombre_marca} ya existe."
                    )
                    continue
                activas = session.query(Marca).filter_by(
                    equipo_id=equipo.id, activa=True
                ).count()
                if activas >= MAX_MARCAS_POR_EQUIPO:
                    avisos.append(
                        f"Equipo {equipo.numero}: ya tiene "
                        f"{MAX_MARCAS_POR_EQUIPO} marcas activas."
                    )
                    continue

                valores = _atributos_proyecto(proyecto)
                marca = Marca(
                    equipo_id=equipo.id,
                    nombre=nombre_marca,
                    tipo="SONITE",
                    activa=True,
                    anio_lanzamiento=anio + 1,
                    precio_actual=float(dm.precio_venta or 300),
                    publicidad_actual=float(dm.presupuesto_publicitario or 0),
                    produccion_actual=float(dm.produccion or 0),
                    calidad_actual=indice_calidad(valores),
                    costo_unitario=float(valores.get(6) or 0),
                )
                session.add(marca)
                session.flush()
                _guardar_atributos(session, marca, valores, anio + 1)

                canales = session.query(Canal).filter_by(
                    industria_id=equipo.industria_id
                ).order_by(Canal.numero).all()
                for canal in canales:
                    vendedores = 0
                    for dv in dm.vendedores:
                        if dv.canal_id == canal.id:
                            vendedores = int(dv.vendedores or 0)
                            break
                    session.add(FuerzaVentas(
                        marca_id=marca.id, canal_id=canal.id,
                        vendedores=vendedores, detallistas=0, anio=anio + 1,
                    ))

                proyecto.estado = "aplicado"
                proyecto.anio_aplicacion = anio + 1
                marcas_nuevas.append({
                    "equipo_id": equipo.id, "proyecto": proyecto.nombre,
                    "marca": nombre_marca,
                })

        return {
            "aplicados": aplicados,
            "marcas_nuevas": marcas_nuevas,
            "avisos": avisos,
        }
