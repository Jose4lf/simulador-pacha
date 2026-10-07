"""
Modelos de base de datos - PACHA
Diseño normalizado aplicando 1FN, 2FN, 3FN y 4FN.
Soporta el simulador Markestrated completo con 5 segmentos, 3 canales,
15 estudios de mercado, atributos físicos, escalas semánticas y más.
"""
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey,
    Index, UniqueConstraint, Text
)
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import json

Base = declarative_base()


# ============================================================
# CATÁLOGOS BASE
# ============================================================

class Simulador(Base):
    """Catálogo de simuladores disponibles."""
    __tablename__ = 'simuladores'

    id = Column(Integer, primary_key=True)
    codigo = Column(String(30), unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255))
    estado = Column(String(30), default="en_desarrollo")  # activo | en_desarrollo | proximamente
    orden = Column(Integer, default=0)

    asignaciones = relationship("AsignacionSimulador", back_populates="simulador")


class AsignacionSimulador(Base):
    """Asignación profesor ↔ simulador."""
    __tablename__ = 'asignaciones_simulador'
    __table_args__ = (
        UniqueConstraint('usuario_id', 'simulador_id', name='uq_asignacion'),
    )

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id', ondelete="CASCADE"), nullable=False)
    simulador_id = Column(Integer, ForeignKey('simuladores.id', ondelete="CASCADE"), nullable=False)
    creada = Column(DateTime, default=datetime.now)

    usuario = relationship("Usuario", back_populates="simuladores_asignados")
    simulador = relationship("Simulador", back_populates="asignaciones")


# ============================================================
# USUARIOS
# ============================================================

class Usuario(Base):
    """Usuarios del sistema (decano, profesor, alumno)."""
    __tablename__ = 'usuarios'
    __table_args__ = (
        Index('ix_usuario_username', 'username'),
        Index('ix_usuario_rol', 'rol'),
    )

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False)
    nombre = Column(String(100))
    email = Column(String(120))
    activo = Column(Boolean, default=True)
    bloqueado = Column(Boolean, default=False)
    equipo_id = Column(Integer, ForeignKey('equipos.id', ondelete="SET NULL"), nullable=True)
    es_representante = Column(Boolean, default=False)
    creado = Column(DateTime, default=datetime.now)

    equipo = relationship("Equipo", foreign_keys=[equipo_id])
    simuladores_asignados = relationship(
        "AsignacionSimulador", back_populates="usuario", cascade="all, delete-orphan"
    )


# ============================================================
# INDUSTRIAS Y EQUIPOS
# ============================================================

class Industria(Base):
    """Industria = simulación activa por profesor."""
    __tablename__ = 'industrias'

    id = Column(Integer, primary_key=True)
    nombre = Column(String(100), unique=True, nullable=False)
    simulador_codigo = Column(String(30), nullable=False, default="markestrated")
    profesor_id = Column(Integer, ForeignKey('usuarios.id'), nullable=False)
    anio_actual = Column(Integer, default=0)
    anio_maximo = Column(Integer, default=10)
    estado = Column(String(20), default="inicializada")
    permitir_envio = Column(Boolean, default=True)

    # Parámetros económicos (sin JSON)
    inflacion_anual = Column(Float, default=0.09)
    inflacion_acumulada = Column(Float, default=0.09)
    tipo_cambio_usd = Column(Float, default=11.90)
    crecimiento_pib = Column(Float, default=0.04)
    presupuesto_inicial = Column(Float, default=10000)

    creada = Column(DateTime, default=datetime.now)

    equipos = relationship("Equipo", back_populates="industria", cascade="all, delete-orphan")
    segmentos = relationship("Segmento", back_populates="industria", cascade="all, delete-orphan")
    canales = relationship("Canal", back_populates="industria", cascade="all, delete-orphan")


class Equipo(Base):
    """Equipo/Firma dentro de una industria."""
    __tablename__ = 'equipos'
    __table_args__ = (
        UniqueConstraint('industria_id', 'numero', name='uq_equipo_industria'),
    )

    id = Column(Integer, primary_key=True)
    industria_id = Column(Integer, ForeignKey('industrias.id', ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)
    nombre_empresa = Column(String(100))
    presupuesto_actual = Column(Float, default=10000)
    ya_decidio = Column(Boolean, default=False)
    bloqueado = Column(Boolean, default=False)
    fecha_decision = Column(DateTime, nullable=True)

    industria = relationship("Industria", back_populates="equipos")
    marcas = relationship("Marca", back_populates="equipo", cascade="all, delete-orphan")
    decisiones = relationship("Decision", back_populates="equipo", cascade="all, delete-orphan")
    reportes = relationship("Reporte", back_populates="equipo", cascade="all, delete-orphan")
    proyectos = relationship("ProyectoID", back_populates="equipo", cascade="all, delete-orphan")


# ============================================================
# SEGMENTOS Y CANALES
# ============================================================

class Segmento(Base):
    """Segmentos de mercado (5 por industria)."""
    __tablename__ = 'segmentos'
    __table_args__ = (
        UniqueConstraint('industria_id', 'numero', name='uq_segmento_industria'),
    )

    id = Column(Integer, primary_key=True)
    industria_id = Column(Integer, ForeignKey('industrias.id', ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)
    nombre = Column(String(50), nullable=False)
    peso = Column(Float, default=0.20)
    valor_ideal_x = Column(Float, default=0)
    valor_ideal_y = Column(Float, default=0)
    valor_ideal_escala_valor = Column(Float, default=4)
    valor_ideal_escala_potencia = Column(Float, default=4)
    valor_ideal_escala_diseno = Column(Float, default=4)

    industria = relationship("Industria", back_populates="segmentos")


class Canal(Base):
    """Canales de distribución (3 por industria)."""
    __tablename__ = 'canales'
    __table_args__ = (
        UniqueConstraint('industria_id', 'numero', name='uq_canal_industria'),
    )

    id = Column(Integer, primary_key=True)
    industria_id = Column(Integer, ForeignKey('industrias.id', ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)
    nombre = Column(String(50), nullable=False)
    total_distribuidores = Column(Integer, default=3000)
    margen_promedio = Column(Float, default=0.40)

    industria = relationship("Industria", back_populates="canales")


# ============================================================
# MARCAS Y ATRIBUTOS
# ============================================================

class Marca(Base):
    """Marcas de cada equipo."""
    __tablename__ = 'marcas'
    __table_args__ = (
        UniqueConstraint('equipo_id', 'nombre', name='uq_marca_equipo'),
    )

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey('equipos.id', ondelete="CASCADE"), nullable=False)
    nombre = Column(String(10), nullable=False)
    tipo = Column(String(10), default="SONITE")
    activa = Column(Boolean, default=True)
    anio_lanzamiento = Column(Integer, default=0)
    calidad_actual = Column(Float, default=50)

    # Valores actuales (última decisión aplicada)
    precio_actual = Column(Float, default=300)
    publicidad_actual = Column(Float, default=2500)
    investigacion_actual = Column(Float, default=0)
    produccion_actual = Column(Float, default=100)

    equipo = relationship("Equipo", back_populates="marcas")


class AtributoFisico(Base):
    """Atributos físicos de cada marca (6 por marca por año)."""
    __tablename__ = 'atributos_fisicos'
    __table_args__ = (
        UniqueConstraint('marca_id', 'numero', 'anio', name='uq_atributo_marca'),
    )

    id = Column(Integer, primary_key=True)
    marca_id = Column(Integer, ForeignKey('marcas.id', ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)  # 1-6
    valor = Column(Float, default=0)
    anio = Column(Integer, nullable=False)


class EscalaSemantica(Base):
    """Escalas semánticas por marca (VALOR/POTENCIA/DISENO)."""
    __tablename__ = 'escalas_semanticas'
    __table_args__ = (
        UniqueConstraint('marca_id', 'tipo', 'anio', name='uq_escala_marca'),
    )

    id = Column(Integer, primary_key=True)
    marca_id = Column(Integer, ForeignKey('marcas.id', ondelete="CASCADE"), nullable=False)
    tipo = Column(String(20), nullable=False)  # VALOR | POTENCIA | DISENO
    valor = Column(Float, default=4)
    anio = Column(Integer, nullable=False)


class PosicionPerceptual(Base):
    """Posición de cada marca en el mapa perceptual por año."""
    __tablename__ = 'posiciones_perceptuales'
    __table_args__ = (
        UniqueConstraint('marca_id', 'anio', name='uq_posicion_marca'),
    )

    id = Column(Integer, primary_key=True)
    marca_id = Column(Integer, ForeignKey('marcas.id', ondelete="CASCADE"), nullable=False)
    posicion_x = Column(Float, default=0)
    posicion_y = Column(Float, default=0)
    anio = Column(Integer, nullable=False)


class FuerzaVentas(Base):
    """Fuerza de ventas por marca y canal."""
    __tablename__ = 'fuerza_ventas'
    __table_args__ = (
        UniqueConstraint('marca_id', 'canal_id', 'anio', name='uq_fuerza_marca_canal'),
    )

    id = Column(Integer, primary_key=True)
    marca_id = Column(Integer, ForeignKey('marcas.id', ondelete="CASCADE"), nullable=False)
    canal_id = Column(Integer, ForeignKey('canales.id', ondelete="CASCADE"), nullable=False)
    vendedores = Column(Integer, default=0)
    detallistas = Column(Integer, default=0)
    anio = Column(Integer, nullable=False)


# ============================================================
# DECISIONES
# ============================================================

class Decision(Base):
    """Cabecera de decisión por equipo y año."""
    __tablename__ = 'decisiones'
    __table_args__ = (
        UniqueConstraint('equipo_id', 'anio', name='uq_decision_equipo_anio'),
    )

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey('equipos.id', ondelete="CASCADE"), nullable=False)
    anio = Column(Integer, nullable=False)
    enviada = Column(DateTime, default=datetime.now)

    equipo = relationship("Equipo", back_populates="decisiones")
    marcas = relationship("DecisionMarca", back_populates="decision", cascade="all, delete-orphan")
    estudios = relationship("DecisionEstudio", back_populates="decision", cascade="all, delete-orphan")


class DecisionMarca(Base):
    """Decisión por marca dentro de una decisión."""
    __tablename__ = 'decision_marca'
    __table_args__ = (
        UniqueConstraint('decision_id', 'marca_nombre', name='uq_decision_marca_nombre'),
    )

    id = Column(Integer, primary_key=True)
    decision_id = Column(Integer, ForeignKey('decisiones.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    proyecto_id_nombre = Column(String(50), nullable=True)
    produccion = Column(Float, default=0)
    presupuesto_publicitario = Column(Float, default=0)
    porcentaje_estudios_publicitarios = Column(Float, default=5)
    precio_venta = Column(Float, default=300)
    objetivo_perceptual_x = Column(Float, nullable=True)
    objetivo_perceptual_y = Column(Float, nullable=True)

    decision = relationship("Decision", back_populates="marcas")
    vendedores = relationship("DecisionVendedor", back_populates="decision_marca", cascade="all, delete-orphan")


class DecisionVendedor(Base):
    """Vendedores por canal en una decisión de marca."""
    __tablename__ = 'decision_vendedores'
    __table_args__ = (
        UniqueConstraint('decision_marca_id', 'canal_id', name='uq_decision_vendedor_canal'),
    )

    id = Column(Integer, primary_key=True)
    decision_marca_id = Column(Integer, ForeignKey('decision_marca.id', ondelete="CASCADE"), nullable=False)
    canal_id = Column(Integer, ForeignKey('canales.id', ondelete="CASCADE"), nullable=False)
    vendedores = Column(Integer, default=0)

    decision_marca = relationship("DecisionMarca", back_populates="vendedores")


class DecisionEstudio(Base):
    """Estudios de mercado marcados en una decisión."""
    __tablename__ = 'decision_estudios'
    __table_args__ = (
        UniqueConstraint('decision_id', 'estudio_id', name='uq_decision_estudio'),
    )

    id = Column(Integer, primary_key=True)
    decision_id = Column(Integer, ForeignKey('decisiones.id', ondelete="CASCADE"), nullable=False)
    estudio_id = Column(Integer, ForeignKey('estudios_mercado.id', ondelete="CASCADE"), nullable=False)
    comprado = Column(Boolean, default=False)

    decision = relationship("Decision", back_populates="estudios")


# ============================================================
# PROYECTOS I+D
# ============================================================

class ProyectoID(Base):
    """Proyectos de investigación y desarrollo."""
    __tablename__ = 'proyectos'

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey('equipos.id', ondelete="CASCADE"), nullable=False)
    nombre = Column(String(50), nullable=False)
    anio_inicio = Column(Integer, nullable=False)
    anio_aprobacion = Column(Integer, nullable=True)
    estado = Column(String(20), default="en_desarrollo")
    gastos = Column(Float, default=0)
    marca_destino_id = Column(Integer, ForeignKey('marcas.id', ondelete="SET NULL"), nullable=True)
    es_nueva_marca = Column(Boolean, default=False)

    equipo = relationship("Equipo", back_populates="proyectos")
    atributos = relationship("ProyectoAtributo", back_populates="proyecto", cascade="all, delete-orphan")


class ProyectoAtributo(Base):
    """Atributos objetivo del proyecto I+D (6 por proyecto)."""
    __tablename__ = 'proyecto_atributos'
    __table_args__ = (
        UniqueConstraint('proyecto_id', 'numero', name='uq_proyecto_atributo'),
    )

    id = Column(Integer, primary_key=True)
    proyecto_id = Column(Integer, ForeignKey('proyectos.id', ondelete="CASCADE"), nullable=False)
    numero = Column(Integer, nullable=False)
    valor_objetivo = Column(Float, default=0)

    proyecto = relationship("ProyectoID", back_populates="atributos")


# ============================================================
# REPORTES
# ============================================================

class Reporte(Base):
    """Cabecera de reporte anual por equipo."""
    __tablename__ = 'reportes'
    __table_args__ = (
        UniqueConstraint('equipo_id', 'anio', name='uq_reporte_equipo_anio'),
    )

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey('equipos.id', ondelete="CASCADE"), nullable=False)
    anio = Column(Integer, nullable=False)

    mercado_total = Column(Float, default=0)
    contribucion_bruta_total = Column(Float, default=0)
    contribucion_neta_total = Column(Float, default=0)
    presupuesto_proximo_periodo = Column(Float, default=0)
    inflacion_aplicada = Column(Float, default=0)
    crecimiento_pnb = Column(Float, default=0)
    tipo_cambio = Column(Float, default=0)

    creado = Column(DateTime, default=datetime.now)

    equipo = relationship("Equipo", back_populates="reportes")
    marcas = relationship("ReporteMarca", back_populates="reporte", cascade="all, delete-orphan")


class ReporteMarca(Base):
    """Reporte detallado por marca."""
    __tablename__ = 'reporte_marca'
    __table_args__ = (
        UniqueConstraint('reporte_id', 'marca_nombre', name='uq_reporte_marca_nombre'),
    )

    id = Column(Integer, primary_key=True)
    reporte_id = Column(Integer, ForeignKey('reportes.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)

    produccion = Column(Float, default=0)
    unidades_vendidas = Column(Float, default=0)
    inventario = Column(Float, default=0)
    precio_final = Column(Float, default=0)
    precio_promedio = Column(Float, default=0)
    costo_transferencia = Column(Float, default=0)
    ingresos = Column(Float, default=0)
    costo_productos_vendidos = Column(Float, default=0)
    costo_inventario = Column(Float, default=0)
    publicidad = Column(Float, default=0)
    contribucion_bruta_marketing = Column(Float, default=0)
    porcion_mercado = Column(Float, default=0)

    reporte = relationship("Reporte", back_populates="marcas")
    canales = relationship("ReporteMarcaCanal", back_populates="reporte_marca", cascade="all, delete-orphan")
    segmentos = relationship("ReporteMarcaSegmento", back_populates="reporte_marca", cascade="all, delete-orphan")


class ReporteMarcaCanal(Base):
    """Ventas de una marca por canal."""
    __tablename__ = 'reporte_marca_canal'
    __table_args__ = (
        UniqueConstraint('reporte_marca_id', 'canal_id', name='uq_reporte_marca_canal'),
    )

    id = Column(Integer, primary_key=True)
    reporte_marca_id = Column(Integer, ForeignKey('reporte_marca.id', ondelete="CASCADE"), nullable=False)
    canal_id = Column(Integer, ForeignKey('canales.id', ondelete="CASCADE"), nullable=False)
    vendedores = Column(Integer, default=0)
    detallistas = Column(Integer, default=0)
    ventas_unidades = Column(Float, default=0)

    reporte_marca = relationship("ReporteMarca", back_populates="canales")


class ReporteMarcaSegmento(Base):
    """Ventas de una marca por segmento."""
    __tablename__ = 'reporte_marca_segmento'
    __table_args__ = (
        UniqueConstraint('reporte_marca_id', 'segmento_id', name='uq_reporte_marca_segmento'),
    )

    id = Column(Integer, primary_key=True)
    reporte_marca_id = Column(Integer, ForeignKey('reporte_marca.id', ondelete="CASCADE"), nullable=False)
    segmento_id = Column(Integer, ForeignKey('segmentos.id', ondelete="CASCADE"), nullable=False)
    ventas_unidades = Column(Float, default=0)
    porcion_mercado = Column(Float, default=0)

    reporte_marca = relationship("ReporteMarca", back_populates="segmentos")


# ============================================================
# ESTUDIOS DE MERCADO
# ============================================================

class EstudioMercado(Base):
    """Catálogo de los 15 estudios de mercado."""
    __tablename__ = 'estudios_mercado'

    id = Column(Integer, primary_key=True)
    numero = Column(Integer, unique=True, nullable=False)
    nombre = Column(String(100), nullable=False)
    descripcion = Column(String(255))
    costo_base = Column(Float, default=0)
    tipo_producto = Column(String(10), default="SONITE")


class CompraEstudio(Base):
    """Estudios comprados por cada equipo en cada año."""
    __tablename__ = 'compras_estudios'
    __table_args__ = (
        UniqueConstraint('equipo_id', 'estudio_id', 'anio', name='uq_compra_estudio'),
    )

    id = Column(Integer, primary_key=True)
    equipo_id = Column(Integer, ForeignKey('equipos.id', ondelete="CASCADE"), nullable=False)
    estudio_id = Column(Integer, ForeignKey('estudios_mercado.id', ondelete="CASCADE"), nullable=False)
    anio = Column(Integer, nullable=False)
    comprado = Column(DateTime, default=datetime.now)

    awareness = relationship("EstudioAwareness", back_populates="compra", cascade="all, delete-orphan")
    intenciones = relationship("EstudioIntencion", back_populates="compra", cascade="all, delete-orphan")
    panel_consumidores = relationship("EstudioPanelConsumidores", back_populates="compra", cascade="all, delete-orphan")
    panel_distribuidores = relationship("EstudioPanelDistribuidores", back_populates="compra", cascade="all, delete-orphan")
    escalas = relationship("EstudioEscala", back_populates="compra", cascade="all, delete-orphan")
    mapa = relationship("EstudioMapa", back_populates="compra", cascade="all, delete-orphan")
    pronosticos = relationship("EstudioPronostico", back_populates="compra", cascade="all, delete-orphan")
    publicidad_comp = relationship("EstudioPublicidadCompetencia", back_populates="compra", cascade="all, delete-orphan")
    fuerza_ventas_comp = relationship("EstudioFuerzaVentasCompetencia", back_populates="compra", cascade="all, delete-orphan")


class EstudioAwareness(Base):
    __tablename__ = 'estudio_awareness'
    __table_args__ = (
        UniqueConstraint('compra_id', 'marca_nombre', name='uq_estudio_awareness'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    awareness = Column(Float, default=0)

    compra = relationship("CompraEstudio", back_populates="awareness")


class EstudioIntencion(Base):
    __tablename__ = 'estudio_intencion_compra'
    __table_args__ = (
        UniqueConstraint('compra_id', 'marca_nombre', 'segmento_id', name='uq_estudio_intencion'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    segmento_id = Column(Integer, ForeignKey('segmentos.id', ondelete="CASCADE"), nullable=False)
    intencion = Column(Float, default=0)

    compra = relationship("CompraEstudio", back_populates="intenciones")


class EstudioPanelConsumidores(Base):
    __tablename__ = 'estudio_panel_consumidores'
    __table_args__ = (
        UniqueConstraint('compra_id', 'marca_nombre', 'segmento_id', name='uq_estudio_panel_cons'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    segmento_id = Column(Integer, ForeignKey('segmentos.id', ondelete="CASCADE"), nullable=False)
    porcion_mercado = Column(Float, default=0)
    ventas_unidades = Column(Float, default=0)

    compra = relationship("CompraEstudio", back_populates="panel_consumidores")


class EstudioPanelDistribuidores(Base):
    __tablename__ = 'estudio_panel_distribuidores'
    __table_args__ = (
        UniqueConstraint('compra_id', 'marca_nombre', 'canal_id', name='uq_estudio_panel_dist'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    canal_id = Column(Integer, ForeignKey('canales.id', ondelete="CASCADE"), nullable=False)
    porcion_mercado = Column(Float, default=0)
    ventas_unidades = Column(Float, default=0)

    compra = relationship("CompraEstudio", back_populates="panel_distribuidores")


class EstudioEscala(Base):
    __tablename__ = 'estudio_escalas'
    __table_args__ = (
        UniqueConstraint('compra_id', 'marca_nombre', 'escala', name='uq_estudio_escala'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    escala = Column(String(20), nullable=False)  # VALOR | POTENCIA | DISENO
    valor = Column(Float, default=4)

    compra = relationship("CompraEstudio", back_populates="escalas")


class EstudioMapa(Base):
    __tablename__ = 'estudio_mapa_perceptual'
    __table_args__ = (
        UniqueConstraint('compra_id', 'entidad_tipo', 'entidad_nombre', name='uq_estudio_mapa'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    entidad_tipo = Column(String(20), nullable=False)  # MARCA | SEGMENTO
    entidad_nombre = Column(String(50), nullable=False)
    posicion_x = Column(Float, default=0)
    posicion_y = Column(Float, default=0)

    compra = relationship("CompraEstudio", back_populates="mapa")


class EstudioPronostico(Base):
    __tablename__ = 'estudio_pronostico'
    __table_args__ = (
        UniqueConstraint('compra_id', 'segmento_id', name='uq_estudio_pronostico'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    segmento_id = Column(Integer, ForeignKey('segmentos.id', ondelete="CASCADE"), nullable=False)
    unidades_esperadas = Column(Float, default=0)

    compra = relationship("CompraEstudio", back_populates="pronosticos")


class EstudioPublicidadCompetencia(Base):
    __tablename__ = 'estudio_publicidad_competencia'
    __table_args__ = (
        UniqueConstraint('compra_id', 'marca_nombre', name='uq_estudio_pub_comp'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    publicidad_estimada = Column(Float, default=0)

    compra = relationship("CompraEstudio", back_populates="publicidad_comp")


class EstudioFuerzaVentasCompetencia(Base):
    __tablename__ = 'estudio_fuerza_ventas_competencia'
    __table_args__ = (
        UniqueConstraint('compra_id', 'marca_nombre', 'canal_id', name='uq_estudio_fv_comp'),
    )

    id = Column(Integer, primary_key=True)
    compra_id = Column(Integer, ForeignKey('compras_estudios.id', ondelete="CASCADE"), nullable=False)
    marca_nombre = Column(String(10), nullable=False)
    canal_id = Column(Integer, ForeignKey('canales.id', ondelete="CASCADE"), nullable=False)
    vendedores_estimados = Column(Integer, default=0)

    compra = relationship("CompraEstudio", back_populates="fuerza_ventas_comp")


# ============================================================
# CONFIGURACIÓN Y AUDITORÍA
# ============================================================

class Configuracion(Base):
    __tablename__ = 'configuracion'

    id = Column(Integer, primary_key=True)
    clave = Column(String(50), unique=True, nullable=False)
    valor = Column(String(255))
    actualizada = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class LogActividad(Base):
    __tablename__ = 'logs_actividad'

    id = Column(Integer, primary_key=True)
    usuario_id = Column(Integer, ForeignKey('usuarios.id', ondelete="SET NULL"), nullable=True)
    accion = Column(String(50), nullable=False)
    detalle = Column(String(255))
    ip = Column(String(45))
    creado = Column(DateTime, default=datetime.now)