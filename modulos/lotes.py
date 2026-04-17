import streamlit as st
"""
models/lotes.py — Corralia v3
Motor central del sistema: registro de animales, flujo de estados
del pie de cría, y traspasos entre chiqueros.

Los tres bugs de Gemini están resueltos aquí:
  Bug #1 → upsert con ON DUPLICATE KEY (nunca duplica id_chiquero+tipo_animal)
  Bug #2 → mover_animales() opera por tipo, no vacía todo el corral
  Bug #3 → validar_ingreso() en chiqueros.py se llama antes de cualquier insert
"""

from datetime import datetime, timedelta, date
from typing import Optional

from database import fetch_all, fetch_one, execute, upsert_lote
from config import (
    DIAS_GESTACION,
    ESTADOS_PIE_CRIA,
    TRANSICIONES_PIE_CRIA,
    ESTADO_REQUIERE_FOTO,
    TIPOS_CRITICOS,
)
import modulos.chiqueros as chiqueros_model


# ─── Lectura ──────────────────────────────────────────────────────────────────

def get_lotes_chiquero(id_chiquero: int) -> list[dict]:
    """Devuelve todos los lotes (tipos de animal) de un chiquero con población > 0."""
    return fetch_all(
        """
        SELECT l.*, c.nombre AS nombre_chiquero
        FROM lotes l
        JOIN chiqueros c ON c.id = l.id_chiquero
        WHERE l.id_chiquero = %s AND l.poblacion_actual > 0
        ORDER BY l.tipo_animal
        """,
        (id_chiquero,),
    )


def get_lote(id_chiquero: int, tipo_animal: str) -> Optional[dict]:
    """Devuelve el lote específico de un tipo de animal en un chiquero."""
    return fetch_one(
        "SELECT * FROM lotes WHERE id_chiquero = %s AND tipo_animal = %s",
        (id_chiquero, tipo_animal),
    )


def get_inventario_completo() -> list[dict]:
    """
    Vista completa para el mapa táctico y el dashboard.
    Un registro por chiquero con su población total y tipos presentes.
    """
    return fetch_all(
        """
        SELECT
            c.id,
            c.nombre                                                        AS corral,
            c.tipo                                                          AS tipo_chiquero,
            c.capacidad_max,
            c.area_m2,
            IFNULL(SUM(l.poblacion_actual), 0)                             AS poblacion_actual,
            IFNULL(GROUP_CONCAT(
                DISTINCT l.tipo_animal ORDER BY l.tipo_animal SEPARATOR ' / '
            ), 'VACÍO')                                                    AS tipo_animal,
            MAX(l.fecha_parto_estimada)                                    AS fecha_parto,
            GROUP_CONCAT(
                DISTINCT l.estado_pie_cria
                ORDER BY l.estado_pie_cria SEPARATOR ', '
            )                                                              AS estado_pie_cria
        FROM chiqueros c
        LEFT JOIN lotes l ON c.id = l.id_chiquero AND l.poblacion_actual > 0
        GROUP BY c.id
        ORDER BY c.nombre
        """
    )


def get_herniados() -> list[dict]:
    """
    Devuelve todos los herniados con su chiquero.
    Siempre se muestran destacados en el dashboard.
    """
    return fetch_all(
        """
        SELECT l.*, c.nombre AS corral
        FROM lotes l
        JOIN chiqueros c ON c.id = l.id_chiquero
        WHERE l.tipo_animal = 'Herniados' AND l.poblacion_actual > 0
        """
    )


def get_pie_cria_por_estado() -> dict[str, int]:
    """Devuelve conteo de pie de cría agrupado por estado reproductivo."""
    rows = fetch_all(
        """
        SELECT IFNULL(estado_pie_cria, 'Sin estado') AS estado, SUM(poblacion_actual) AS total
        FROM lotes
        WHERE tipo_animal = 'Pie de Cría' AND poblacion_actual > 0
        GROUP BY estado_pie_cria
        """
    )
    return {row["estado"]: int(row["total"]) for row in rows}


def get_proximos_partos(dias: int = 30) -> list[dict]:
    """
    Devuelve pie de cría en gestación con parto estimado en los próximos `dias` días.
    """
    return fetch_all(
        """
        SELECT
            c.nombre AS corral,
            l.arete,
            l.poblacion_actual,
            l.fecha_monta,
            l.fecha_parto_estimada,
            DATEDIFF(l.fecha_parto_estimada, CURDATE()) AS dias_restantes
        FROM lotes l
        JOIN chiqueros c ON c.id = l.id_chiquero
        WHERE l.tipo_animal = 'Pie de Cría'
          AND l.estado_pie_cria = 'Gestación'
          AND l.fecha_parto_estimada IS NOT NULL
          AND l.fecha_parto_estimada <= DATE_ADD(CURDATE(), INTERVAL %s DAY)
        ORDER BY l.fecha_parto_estimada
        """,
        (dias,),
    )


# ─── Registro inicial ─────────────────────────────────────────────────────────

def registrar_animales(
    id_chiquero: int,
    tipo_animal: str,
    cantidad: int,
    estado_pie_cria: Optional[str] = None,
    fecha_monta: Optional[date] = None,
    arete: str = "S/A",
    notas: str = "",
    usuario: str = "",
) -> tuple[bool, str, Optional[datetime]]:
    """
    Registra animales en un chiquero con todas las validaciones.

    Flujo:
    1. Valida que el tipo de animal puede entrar al chiquero
    2. Hace upsert (nunca duplica — fix bug #1)
    3. Si es Pie de Cría con fecha de monta, calcula fecha de parto estimada
    4. Registra en historial

    Devuelve (exito, mensaje, fecha_parto_estimada)
    """
    # 1. Validación de chiquero
    ok, msg = chiqueros_model.validar_ingreso(id_chiquero, tipo_animal, cantidad)
    if not ok:
        return False, msg, None

    # 2. Calcular fecha de parto si aplica
    fecha_parto = None
    if fecha_monta and tipo_animal == "Pie de Cría":
        if isinstance(fecha_monta, date) and not isinstance(fecha_monta, datetime):
            fecha_monta = datetime.combine(fecha_monta, datetime.min.time())
        fecha_parto = fecha_monta + timedelta(days=DIAS_GESTACION)

    # 3. Upsert principal (fix bug #1)
    upsert_lote(id_chiquero, tipo_animal, cantidad)

    # 4. Actualizar campos adicionales si es pie de cría
    if tipo_animal == "Pie de Cría":
        _actualizar_datos_pie_cria(
            id_chiquero=id_chiquero,
            estado=estado_pie_cria or "Disponible",
            fecha_monta=fecha_monta,
            fecha_parto=fecha_parto,
            arete=arete,
            notas=notas,
        )
    elif notas or arete != "S/A":
        execute(
            "UPDATE lotes SET arete = %s, notas = %s WHERE id_chiquero = %s AND tipo_animal = %s",
            (arete, notas, id_chiquero, tipo_animal),
        )

    # 5. Historial
    _registrar_en_historial(
        id_origen=None,
        id_destino=id_chiquero,
        tipo_animal=tipo_animal,
        cantidad=cantidad,
        tipo_evento="ENTRADA",
        usuario=usuario,
        notas=notas or f"Registro inicial de {cantidad} {tipo_animal}",
    )

    fecha_str = fecha_parto.strftime("%d/%m/%Y") if fecha_parto else None
    msg_ok = f"{cantidad} {tipo_animal} registrados."
    if fecha_str:
        msg_ok += f" Parto estimado: {fecha_str}"

    return True, msg_ok, fecha_parto


# ─── Traspasos ────────────────────────────────────────────────────────────────

def mover_animales(
    id_chiquero_origen: int,
    id_chiquero_destino: int,
    tipo_animal: str,
    cantidad: int,
    nuevo_tipo_destino: Optional[str] = None,
    usuario: str = "",
    notas: str = "",
) -> tuple[bool, str]:
    """
    Mueve `cantidad` animales de un tipo específico entre chiqueros.

    Fix bug #2: opera SOLO sobre el tipo_animal indicado, nunca toca
    los otros tipos que puedan existir en el mismo chiquero.

    `nuevo_tipo_destino` permite cambiar de etapa en el traspaso
    (ej: Desarrollo → Engorda). Si es None, se mantiene el mismo tipo.

    Devuelve (exito, mensaje).
    """
    tipo_destino = nuevo_tipo_destino or tipo_animal

    # Verificar stock en origen
    lote_origen = get_lote(id_chiquero_origen, tipo_animal)
    if not lote_origen or lote_origen["poblacion_actual"] < cantidad:
        disponible = lote_origen["poblacion_actual"] if lote_origen else 0
        return False, f"Solo hay {disponible} {tipo_animal} disponibles en origen."

    # Validar destino
    ok, msg = chiqueros_model.validar_ingreso(id_chiquero_destino, tipo_destino, cantidad)
    if not ok:
        return False, msg

    # Restar del origen (solo este tipo — fix bug #2)
    execute(
        """
        UPDATE lotes
        SET poblacion_actual = GREATEST(poblacion_actual - %s, 0)
        WHERE id_chiquero = %s AND tipo_animal = %s
        """,
        (cantidad, id_chiquero_origen, tipo_animal),
    )

    # Sumar en destino (upsert — fix bug #1)
    upsert_lote(id_chiquero_destino, tipo_destino, cantidad)

    # Historial
    nota_auto = notas or f"Traspaso de {cantidad} {tipo_animal}"
    if nuevo_tipo_destino and nuevo_tipo_destino != tipo_animal:
        nota_auto = notas or f"Avance de etapa: {tipo_animal} → {tipo_destino}"

    _registrar_en_historial(
        id_origen=id_chiquero_origen,
        id_destino=id_chiquero_destino,
        tipo_animal=tipo_destino,
        cantidad=cantidad,
        tipo_evento="TRASPASO",
        usuario=usuario,
        notas=nota_auto,
    )

    return True, f"{cantidad} {tipo_destino} movidos correctamente."


# ─── Estados del Pie de Cría ──────────────────────────────────────────────────

def avanzar_estado_pie_cria(
    id_chiquero: int,
    nuevo_estado: str,
    foto_monta: Optional[str] = None,
    fecha_monta: Optional[date] = None,
    usuario: str = "",
) -> tuple[bool, str]:
    """
    Avanza el estado reproductivo del pie de cría en un chiquero.

    Valida:
    - El estado nuevo es una transición válida desde el actual
    - Si nuevo_estado = 'Cubierta', foto_monta es obligatoria

    Devuelve (exito, mensaje).
    """
    lote = get_lote(id_chiquero, "Pie de Cría")
    if not lote:
        return False, "No hay Pie de Cría en este chiquero."

    estado_actual = lote.get("estado_pie_cria") or "Disponible"
    transiciones_validas = TRANSICIONES_PIE_CRIA.get(estado_actual, [])

    if nuevo_estado not in transiciones_validas:
        return False, (
            f"No se puede pasar de '{estado_actual}' a '{nuevo_estado}'. "
            f"Transiciones válidas: {', '.join(transiciones_validas) or 'ninguna'}"
        )

    if nuevo_estado == ESTADO_REQUIERE_FOTO and not foto_monta:
        return False, "Se requiere foto de monta para registrar como Cubierta."

    # Calcular fecha de parto si pasa a gestación
    fecha_parto = None
    if nuevo_estado == "Gestación" and lote.get("fecha_monta"):
        fecha_monta_dt = lote["fecha_monta"]
        if isinstance(fecha_monta_dt, date) and not isinstance(fecha_monta_dt, datetime):
            fecha_monta_dt = datetime.combine(fecha_monta_dt, datetime.min.time())
        fecha_parto = fecha_monta_dt + timedelta(days=DIAS_GESTACION)

    # Si viene nueva fecha de monta (en el paso Cubierta)
    if fecha_monta and nuevo_estado == "Cubierta":
        if isinstance(fecha_monta, date) and not isinstance(fecha_monta, datetime):
            fecha_monta = datetime.combine(fecha_monta, datetime.min.time())
        fecha_parto = fecha_monta + timedelta(days=DIAS_GESTACION)
    else:
        fecha_monta = lote.get("fecha_monta")

    _actualizar_datos_pie_cria(
        id_chiquero=id_chiquero,
        estado=nuevo_estado,
        fecha_monta=fecha_monta,
        fecha_parto=fecha_parto,
        foto_monta=foto_monta,
    )

    _registrar_en_historial(
        id_origen=None,
        id_destino=id_chiquero,
        tipo_animal="Pie de Cría",
        cantidad=lote["poblacion_actual"],
        tipo_evento="CAMBIO_ESTADO",
        usuario=usuario,
        notas=f"Estado: {estado_actual} → {nuevo_estado}",
        foto_evidencia=foto_monta,
    )

    return True, f"Estado actualizado: {estado_actual} → {nuevo_estado}"


# ─── Helpers internos ─────────────────────────────────────────────────────────

def _actualizar_datos_pie_cria(
    id_chiquero: int,
    estado: str,
    fecha_monta=None,
    fecha_parto=None,
    arete: str = "S/A",
    notas: str = "",
    foto_monta: Optional[str] = None,
) -> None:
    execute(
        """
        UPDATE lotes
        SET estado_pie_cria      = %s,
            fecha_monta          = %s,
            fecha_parto_estimada = %s,
            arete                = %s,
            notas                = %s,
            foto_monta           = IFNULL(%s, foto_monta)
        WHERE id_chiquero = %s AND tipo_animal = 'Pie de Cría'
        """,
        (estado, fecha_monta, fecha_parto, arete, notas, foto_monta, id_chiquero),
    )


def _registrar_en_historial(
    id_origen: Optional[int],
    id_destino: int,
    tipo_animal: str,
    cantidad: int,
    tipo_evento: str,
    usuario: str,
    notas: str = "",
    foto_evidencia: Optional[str] = None,
) -> None:
    execute(
        """
        INSERT INTO historial_movimientos
            (id_chiquero_origen, id_chiquero_destino, tipo_animal,
             cantidad, tipo_evento, id_usuario, notas, foto_evidencia)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (id_origen, id_destino, tipo_animal, cantidad,
         tipo_evento, usuario, notas, foto_evidencia),
    )