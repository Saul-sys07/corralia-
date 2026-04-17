import streamlit as st
"""
models/chiqueros.py — Corralia v3
Consultas y validaciones relacionadas con chiqueros.
Regla central: la validación de qué animal puede entrar a qué corral
vive aquí, no en el schema de la base de datos.
"""

from database import fetch_all, fetch_one, execute
from config import (
    ANIMALES_PERMITIDOS_EN,
    M2_POR_ANIMAL,
    TIPOS_EXCLUSIVOS,
    ALERTA_CAPACIDAD_AMARILLO,
    ALERTA_CAPACIDAD_ROJO,
)


# ─── Lectura ──────────────────────────────────────────────────────────────────

def get_chiqueros() -> list[dict]:
    """
    Devuelve todos los chiqueros con su ocupación actual calculada.
    Incluye: área m², población total, tipos de animal presentes,
    próximo parto estimado y estado de capacidad (ok/alerta/excedido).
    """
    sql = """
        SELECT
            c.id,
            c.nombre,
            c.tipo,
            c.largo,
            c.ancho,
            c.capacidad_max,
            c.area_m2,
            IFNULL(SUM(l.poblacion_actual), 0)                              AS poblacion_actual,
            IFNULL(GROUP_CONCAT(
                DISTINCT l.tipo_animal
                ORDER BY l.tipo_animal
                SEPARATOR ' / '
            ), 'VACÍO')                                                     AS tipos_animal,
            MAX(l.fecha_parto_estimada)                                     AS fecha_parto_estimada,
            GROUP_CONCAT(
                DISTINCT l.estado_pie_cria
                ORDER BY l.estado_pie_cria
                SEPARATOR ', '
            )                                                               AS estados_pie_cria
        FROM chiqueros c
        LEFT JOIN lotes l ON c.id = l.id_chiquero AND l.poblacion_actual > 0
        GROUP BY c.id
        ORDER BY c.nombre
    """
    rows = fetch_all(sql)
    for row in rows:
        row["estado_capacidad"] = _calcular_estado_capacidad(
            row["poblacion_actual"], row["capacidad_max"]
        )
    return rows


def get_chiquero(id_chiquero: int) -> dict | None:
    """Devuelve un chiquero por id, con su ocupación."""
    sql = """
        SELECT
            c.id, c.nombre, c.tipo, c.zona, c.largo, c.ancho,
            c.capacidad_max, c.area_m2,
            IFNULL(SUM(l.poblacion_actual), 0) AS poblacion_actual
        FROM chiqueros c
        LEFT JOIN lotes l ON c.id = l.id_chiquero AND l.poblacion_actual > 0
        WHERE c.id = %s
        GROUP BY c.id
    """
    row = fetch_one(sql, (id_chiquero,))
    if row:
        row["estado_capacidad"] = _calcular_estado_capacidad(
            row["poblacion_actual"], row["capacidad_max"]
        )
    return row


def get_chiqueros_disponibles_para(tipo_animal: str) -> list[dict]:
    """
    Devuelve solo los chiqueros donde puede entrar este tipo de animal.
    Aplica: regla de tipo de chiquero + regla de exclusividad.
    """
    todos = get_chiqueros()
    resultado = []
    for ch in todos:
        ok, _ = validar_ingreso(ch["id"], tipo_animal, 1, todos_chiqueros=todos)
        if ok:
            resultado.append(ch)
    return resultado


# ─── Validación ───────────────────────────────────────────────────────────────

def validar_ingreso(
    id_chiquero: int,
    tipo_animal: str,
    cantidad: int,
    todos_chiqueros: list[dict] | None = None,
) -> tuple[bool, str]:
    """
    Valida si `cantidad` animales de `tipo_animal` pueden entrar al chiquero.

    Reglas que aplica en orden:
    1. El tipo de chiquero acepta este tipo de animal (ANIMALES_PERMITIDOS_EN)
    2. Si el animal es exclusivo (Semental, Pie de Cría), el chiquero debe estar vacío
       o tener solo ese mismo tipo
    3. La capacidad en m² no se excede

    Devuelve (True, "") si pasa, o (False, "motivo") si falla.
    """
    if todos_chiqueros is None:
        ch = get_chiquero(id_chiquero)
    else:
        ch = next((c for c in todos_chiqueros if c["id"] == id_chiquero), None)

    if not ch:
        return False, "Chiquero no encontrado"

    # Regla 1 — tipo de chiquero
    permitidos = ANIMALES_PERMITIDOS_EN.get(ch["tipo"], set())
    if tipo_animal not in permitidos:
        return False, (
            f"Un {ch['tipo']} no acepta {tipo_animal}. "
            f"Solo admite: {', '.join(sorted(permitidos))}"
        )


    # Regla 2 - exclusividad
    # Excepcion: Paridera puede tener Pie de Cria + Crias (madre con lechones)
    es_combo_paridera = (
        ch.get("tipo") == "Paridera" and
        tipo_animal == "Crías"
    )
    if tipo_animal in TIPOS_EXCLUSIVOS and not es_combo_paridera:
        tipos_presentes = ch.get("tipos_animal", "VACÍO")
        if tipos_presentes not in ("VACÍO", tipo_animal) and tipo_animal not in tipos_presentes:
            return False, (
                f"Este chiquero ya tiene {tipos_presentes}. "
                f"{tipo_animal} necesita chiquero exclusivo."
            )

    # Regla 3 - capacidad m2
    # float() en todo: MySQL devuelve Decimal, Python necesita float
    m2_necesario     = float(M2_POR_ANIMAL.get(tipo_animal, 0.82))
    poblacion_actual = float(ch.get("poblacion_actual") or 0)
    area             = float(ch.get("area_m2") or 0) or (
                           float(ch.get("largo") or 0) * float(ch.get("ancho") or 0)
                       )

    if area > 0:
        m2_disponibles = area - (poblacion_actual * m2_necesario)
        m2_requeridos  = float(cantidad) * m2_necesario
        if m2_requeridos > m2_disponibles:
            cabezas_max = int(area / m2_necesario)
            return False, (
                f"Sin espacio: necesitas {m2_requeridos:.1f}m2 "
                f"pero solo hay {m2_disponibles:.1f}m2 libres. "
                f"Maximo recomendado para este corral: {cabezas_max} cabezas."
            )

    return True, ""


# ─── CRUD ─────────────────────────────────────────────────────────────────────

def crear_chiquero(nombre: str, tipo: str, largo: float, ancho: float, capacidad_max: int) -> int:
    """Inserta un nuevo chiquero. Devuelve el id creado."""
    sql = """
        INSERT INTO chiqueros (nombre, tipo, largo, ancho, capacidad_max)
        VALUES (%s, %s, %s, %s, %s)
    """
    return execute(sql, (nombre, tipo, float(largo), float(ancho), int(capacidad_max)))


def actualizar_chiquero(id_chiquero: int, nombre: str, tipo: str, largo: float, ancho: float, capacidad_max: int) -> None:
    """Actualiza los datos físicos de un chiquero."""
    sql = """
        UPDATE chiqueros
        SET nombre = %s, tipo = %s, largo = %s, ancho = %s, capacidad_max = %s
        WHERE id = %s
    """
    execute(sql, (nombre, tipo, float(largo), float(ancho), int(capacidad_max), id_chiquero))


# ─── Alertas de capacidad ─────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def get_alertas_capacidad() -> list[dict]:
    """
    Devuelve chiqueros al 90%+ de capacidad.
    Excluye cap=1 (Semental/Paridera): 1/1 es normal, no alerta.
    """
    chiqueros = get_chiqueros()
    alertas = []
    for ch in chiqueros:
        cap = ch["capacidad_max"] or 1
        if cap == 1:
            continue
        pct = float(ch["poblacion_actual"] or 0) / cap
        if pct >= ALERTA_CAPACIDAD_AMARILLO:
            alertas.append({
                **ch,
                "porcentaje": round(pct * 100, 1),
                "nivel": "rojo" if pct >= ALERTA_CAPACIDAD_ROJO else "amarillo",
            })
    return sorted(alertas, key=lambda x: x["porcentaje"], reverse=True)

# ─── Helpers internos ─────────────────────────────────────────────────────────

def _calcular_estado_capacidad(poblacion: int, capacidad_max: int) -> str:
    """Devuelve 'vacio', 'ok', 'alerta' o 'excedido'."""
    if poblacion == 0:
        return "vacio"
    cap = capacidad_max or 1
    pct = poblacion / cap
    if pct >= ALERTA_CAPACIDAD_ROJO:
        return "excedido"
    if pct >= ALERTA_CAPACIDAD_AMARILLO:
        return "alerta"
    return "ok"