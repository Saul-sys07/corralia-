"""
database.py — Corralia v3
Pool de conexiones MySQL y funciones auxiliares para queries.
Todos los modelos importan get_connection() desde aquí.
"""

import mysql.connector
from mysql.connector import pooling, Error
from contextlib import contextmanager
from typing import Any, Optional
import streamlit as st

from config import DB_CONFIG

# ─── Pool de conexiones ───────────────────────────────────────────────────────
# Se inicializa una sola vez por sesión de Streamlit usando st.cache_resource
# para no abrir un pool nuevo en cada rerun.

@st.cache_resource
def _get_pool() -> pooling.MySQLConnectionPool:
    """Crea el pool de conexiones una sola vez por instancia de la app."""
    try:
        pool = pooling.MySQLConnectionPool(
    pool_name="corralia_pool",
    pool_size=2,
    connection_timeout=30,
    **DB_CONFIG,
)
        return pool
    except Error as e:
        st.error(f"Error al conectar con la base de datos: {e}")
        raise


@contextmanager
def get_connection():
    """
    Context manager que entrega una conexión del pool y la devuelve al terminar.

    Uso:
        with get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(...)
    """
    pool = _get_pool()
    conn = pool.get_connection()
    try:
        yield conn
        conn.commit()
    except Error as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ─── Helpers de query ─────────────────────────────────────────────────────────

def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    """
    Ejecuta un SELECT y devuelve todos los resultados como lista de dicts.

    Ejemplo:
        rows = fetch_all("SELECT * FROM chiqueros WHERE tipo = %s", ("Comunal",))
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        return cursor.fetchall()


def fetch_one(sql: str, params: tuple = ()) -> Optional[dict]:
    """
    Ejecuta un SELECT y devuelve el primer resultado como dict, o None.
    """
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        return cursor.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """
    Ejecuta un INSERT, UPDATE o DELETE.
    Devuelve el lastrowid (útil para INSERTs).

    Ejemplo:
        nuevo_id = execute(
            "INSERT INTO lotes (id_chiquero, tipo_animal, poblacion_actual) VALUES (%s, %s, %s)",
            (1, "Engorda", 10)
        )
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.lastrowid


def execute_many(sql: str, params_list: list[tuple]) -> int:
    """
    Ejecuta el mismo statement con múltiples conjuntos de parámetros.
    Devuelve el número de filas afectadas.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(sql, params_list)
        return cursor.rowcount


def upsert_lote(id_chiquero: int, tipo_animal: str, cantidad: int) -> int:
    """
    Inserta un lote o suma la cantidad si ya existe (id_chiquero, tipo_animal).
    Este es el fix al bug #1: nunca crea filas duplicadas en el mismo corral+tipo.

    Devuelve el id del lote afectado.
    """
    sql = """
        INSERT INTO lotes (id_chiquero, tipo_animal, poblacion_actual)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            poblacion_actual = poblacion_actual + VALUES(poblacion_actual)
    """
    return execute(sql, (id_chiquero, tipo_animal, cantidad))


def test_connection() -> tuple[bool, str]:
    """
    Verifica que la conexión a MySQL funcione.
    Devuelve (True, version_string) o (False, mensaje_error).
    Útil para mostrar estado en el sidebar de Streamlit.
    """
    try:
        row = fetch_one("SELECT VERSION() AS v")
        return True, row["v"]
    except Exception as e:
        return False, str(e)
