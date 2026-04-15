"""
database.py - Corralia v3
Conexiones directas a MySQL sin pool.
Mas estable en Streamlit Cloud con Railway gratuito.
"""

import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager
from typing import Optional
import streamlit as st

from config import DB_CONFIG


def _get_connection():
    """Crea una conexion directa a MySQL."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except Error as e:
        st.error(f"Error de conexion: {e}")
        raise


@contextmanager
def get_connection():
    """
    Context manager que abre y cierra una conexion por cada operacion.
    Sin pool — mas estable en Railway gratuito.
    """
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Error as e:
        conn.rollback()
        raise e
    finally:
        if conn.is_connected():
            conn.close()


def fetch_all(sql: str, params: tuple = ()) -> list[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        return cursor.fetchall()


def fetch_one(sql: str, params: tuple = ()) -> Optional[dict]:
    with get_connection() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params)
        return cursor.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return cursor.lastrowid


def execute_many(sql: str, params_list: list[tuple]) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(sql, params_list)
        return cursor.rowcount


def upsert_lote(id_chiquero: int, tipo_animal: str, cantidad: int) -> int:
    sql = """
        INSERT INTO lotes (id_chiquero, tipo_animal, poblacion_actual)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            poblacion_actual = poblacion_actual + VALUES(poblacion_actual)
    """
    return execute(sql, (id_chiquero, tipo_animal, cantidad))


def test_connection() -> tuple[bool, str]:
    try:
        row = fetch_one("SELECT VERSION() AS v")
        return True, row["v"]
    except Exception as e:
        return False, str(e)