"""
models/movimientos.py — Corralia v3
Historial de movimientos, alertas del sistema y consultas de auditoría.
"""

from datetime import datetime
from typing import Optional

from database import fetch_all, fetch_one, execute
from config import TIPOS_CRITICOS


# ─── Historial ────────────────────────────────────────────────────────────────

def get_historial(
    id_chiquero: Optional[int] = None,
    tipo_evento: Optional[str] = None,
    limit: int = 100,
) -> list[dict]:
    """
    Devuelve el historial de movimientos, más reciente primero.
    Filtra opcionalmente por chiquero y/o tipo de evento.
    """
    condiciones = []
    params = []

    if id_chiquero:
        condiciones.append(
            "(h.id_chiquero_origen = %s OR h.id_chiquero_destino = %s)"
        )
        params.extend([id_chiquero, id_chiquero])

    if tipo_evento:
        condiciones.append("h.tipo_evento = %s")
        params.append(tipo_evento)

    where = ("WHERE " + " AND ".join(condiciones)) if condiciones else ""
    params.append(limit)

    return fetch_all(
        f"""
        SELECT
            h.id,
            h.fecha,
            h.tipo_evento,
            h.tipo_animal,
            h.cantidad,
            h.notas,
            h.foto_evidencia,
            h.id_usuario                        AS usuario,
            co.nombre                           AS corral_origen,
            cd.nombre                           AS corral_destino
        FROM historial_movimientos h
        LEFT JOIN chiqueros co ON co.id = h.id_chiquero_origen
        LEFT JOIN chiqueros cd ON cd.id = h.id_chiquero_destino
        {where}
        ORDER BY h.fecha DESC
        LIMIT %s
        """,
        tuple(params),
    )


# ─── Alertas del sistema ──────────────────────────────────────────────────────

def get_alertas_activas() -> list[dict]:
    """
    Devuelve alertas no leídas, ordenadas por fecha descendente.
    """
    return fetch_all(
        """
        SELECT id, fecha, usuario, tipo, mensaje
        FROM alertas_sistema
        WHERE leido = 0
        ORDER BY fecha DESC
        """
    )


def crear_alerta(
    tipo: str,
    mensaje: str,
    usuario: str = "sistema",
) -> None:
    """Registra una alerta nueva en el sistema."""
    execute(
        """
        INSERT INTO alertas_sistema (usuario, tipo, mensaje)
        VALUES (%s, %s, %s)
        """,
        (usuario, tipo, mensaje),
    )


def marcar_alerta_leida(id_alerta: int) -> None:
    execute(
        "UPDATE alertas_sistema SET leido = 1 WHERE id = %s",
        (id_alerta,),
    )


def marcar_todas_leidas() -> None:
    execute("UPDATE alertas_sistema SET leido = 1 WHERE leido = 0")


# ─── Alertas automáticas ─────────────────────────────────────────────────────

def generar_alertas_partos_proximos(dias: int = 7) -> int:
    """
    Crea alertas de tipo PARTO_PROXIMO para partos en los próximos `dias` días.
    No duplica alertas si ya existe una para ese corral+fecha.
    Devuelve el número de alertas nuevas creadas.
    """
    proximos = fetch_all(
        """
        SELECT c.nombre AS corral, l.fecha_parto_estimada,
               DATEDIFF(l.fecha_parto_estimada, CURDATE()) AS dias_restantes
        FROM lotes l
        JOIN chiqueros c ON c.id = l.id_chiquero
        WHERE l.tipo_animal = 'Pie de Cría'
          AND l.estado_pie_cria = 'Gestación'
          AND l.fecha_parto_estimada IS NOT NULL
          AND l.fecha_parto_estimada BETWEEN CURDATE()
              AND DATE_ADD(CURDATE(), INTERVAL %s DAY)
        """,
        (dias,),
    )

    creadas = 0
    for p in proximos:
        mensaje = (
            f"Parto próximo en {p['corral']}: "
            f"faltan {p['dias_restantes']} días "
            f"({p['fecha_parto_estimada'].strftime('%d/%m/%Y')})"
        )
        # Evitar duplicados revisando si ya existe esa alerta hoy
        existe = fetch_one(
            """
            SELECT id FROM alertas_sistema
            WHERE tipo = 'PARTO_PROXIMO'
              AND mensaje = %s
              AND DATE(fecha) = CURDATE()
            """,
            (mensaje,),
        )
        if not existe:
            crear_alerta("PARTO_PROXIMO", mensaje)
            creadas += 1

    return creadas


def get_resumen_criticos() -> dict:
    """
    Devuelve totales de animales críticos (Herniados, Desecho).
    Se usa para el banner de alerta siempre visible en el dashboard.
    """
    rows = fetch_all(
        """
        SELECT tipo_animal, SUM(poblacion_actual) AS total
        FROM lotes
        WHERE tipo_animal IN ('Herniados', 'Desecho')
          AND poblacion_actual > 0
        GROUP BY tipo_animal
        """
    )
    return {row["tipo_animal"]: int(row["total"]) for row in rows}


def get_verificaciones_celo_pendientes() -> list[dict]:
    """
    Devuelve pie de cria en estado Cubierta que ya cumplieron 21 dias
    desde la fecha de monta y aun no se ha confirmado si quedaron gestantes.
    """
    from config import DIAS_CONFIRMACION_GESTACION
    return fetch_all(
        """
        SELECT
            l.id,
            l.id_chiquero,
            l.arete,
            l.fecha_monta,
            l.fecha_parto_estimada,
            l.poblacion_actual,
            c.nombre AS corral,
            DATEDIFF(CURDATE(), l.fecha_monta) AS dias_desde_monta
        FROM lotes l
        JOIN chiqueros c ON c.id = l.id_chiquero
        WHERE l.tipo_animal = 'Pie de Cr\u00eda'
          AND l.estado_pie_cria = 'Cubierta'
          AND l.fecha_monta IS NOT NULL
          AND DATEDIFF(CURDATE(), l.fecha_monta) >= %s
        ORDER BY l.fecha_monta ASC
        """,
        (DIAS_CONFIRMACION_GESTACION,),
    )


def confirmar_gestacion(id_chiquero: int, usuario: str) -> tuple[bool, str]:
    from database import execute
    execute(
        "UPDATE lotes SET estado_pie_cria = 'Gestación' WHERE id_chiquero = %s AND tipo_animal = 'Pie de Cría'",
        (id_chiquero,),
    )
    from modulos.lotes import _registrar_en_historial
    _registrar_en_historial(
        id_origen=None,
        id_destino=id_chiquero,
        tipo_animal='Pie de Cría',
        cantidad=1,
        tipo_evento='CAMBIO_ESTADO',
        usuario=usuario,
        notas='Confirmacion gestacion: no regreso al celo a los 21 dias',
    )
    return True, 'Gestacion confirmada.'


def cancelar_monta(id_chiquero: int, usuario: str) -> tuple[bool, str]:
    from database import execute
    execute(
        "UPDATE lotes SET estado_pie_cria = 'Disponible', fecha_monta = NULL, fecha_parto_estimada = NULL, foto_monta = NULL WHERE id_chiquero = %s AND tipo_animal = 'Pie de Cría'",
        (id_chiquero,),
    )
    from modulos.lotes import _registrar_en_historial
    _registrar_en_historial(
        id_origen=None,
        id_destino=id_chiquero,
        tipo_animal='Pie de Cría',
        cantidad=1,
        tipo_evento='CAMBIO_ESTADO',
        usuario=usuario,
        notas='Regreso al celo a los 21 dias - monta cancelada',
    )
    return True, 'Regresada a Disponible.'