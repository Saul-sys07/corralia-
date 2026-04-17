"""
modulos/clientes.py - Corralia v3
Gestion de clientes — solo Admin (Saul).
Ciclo de vida: Nuevo → Retenido → Disponible → Recuperado → Retenido
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from database import fetch_all, fetch_one, execute


COMISIONES = {
    "Nuevo":      3.00,
    "Retenido":   1.50,
    "Recuperado": 2.00,
    "Sin comision": 0.00,
}

DIAS_PARA_DISPONIBLE = 365  # 1 año sin comprar → disponible


def _actualizar_estados_clientes():
    """
    Revisa todos los clientes Retenidos y Recuperados.
    Si llevan mas de 1 año sin comprar → pasan a Disponible.
    Se ejecuta al abrir el modulo.
    """
    limite = date.today() - timedelta(days=DIAS_PARA_DISPONIBLE)

    # Clientes retenidos/recuperados cuya ultima compra fue hace mas de 1 año
    clientes_vencidos = fetch_all(
        """
        SELECT c.id, c.nombre
        FROM clientes c
        WHERE c.tipo IN ('Retenido', 'Recuperado')
        AND c.activo = 1
        AND (
            SELECT MAX(DATE(v.fecha))
            FROM ventas v
            WHERE v.cliente_id = c.id
        ) < %s
        OR (
            c.tipo IN ('Retenido', 'Recuperado')
            AND c.activo = 1
            AND NOT EXISTS (SELECT 1 FROM ventas v WHERE v.cliente_id = c.id)
        )
        """,
        (limite,)
    )

    for c in clientes_vencidos:
        execute(
            "UPDATE clientes SET tipo = 'Disponible', usuario_id = NULL WHERE id = %s",
            (c["id"],)
        )


def get_comision_cliente(cliente_id: int) -> float:
    """Devuelve la comision por kg para un cliente."""
    cliente = fetch_one("SELECT tipo FROM clientes WHERE id = %s", (cliente_id,))
    if not cliente:
        return 0.0
    return COMISIONES.get(cliente["tipo"], 0.0)


def mostrar_clientes():
    st.title("Clientes")
    st.caption("Gestion de cartera — solo Admin")

    # Actualizar estados automaticamente
    _actualizar_estados_clientes()

    tab1, tab2 = st.tabs(["Cartera", "Registrar cliente"])

    with tab1:
        _mostrar_cartera()

    with tab2:
        _registrar_cliente()


def _mostrar_cartera():
    st.subheader("Cartera de clientes")

    # Filtro por tipo
    tipos = ["Todos", "Nuevo", "Retenido", "Recuperado", "Disponible"]
    filtro = st.selectbox("Filtrar por tipo:", tipos, key="filtro_tipo_cliente")

    if filtro == "Todos":
        clientes = fetch_all("""
            SELECT c.id, c.nombre, c.telefono, c.tipo,
                   COALESCE(u.nombre, '—') AS vendedor,
                   (SELECT MAX(v.fecha) FROM ventas v WHERE v.cliente_id = c.id) AS ultima_compra,
                   (SELECT COUNT(*) FROM ventas v WHERE v.cliente_id = c.id) AS num_compras,
                   (SELECT SUM(v.total_rancho) FROM ventas v WHERE v.cliente_id = c.id) AS total_comprado
            FROM clientes c
            LEFT JOIN usuarios u ON u.id = c.usuario_id
            WHERE c.activo = 1
            ORDER BY c.tipo, c.nombre
        """)
    else:
        clientes = fetch_all("""
            SELECT c.id, c.nombre, c.telefono, c.tipo,
                   COALESCE(u.nombre, '—') AS vendedor,
                   (SELECT MAX(v.fecha) FROM ventas v WHERE v.cliente_id = c.id) AS ultima_compra,
                   (SELECT COUNT(*) FROM ventas v WHERE v.cliente_id = c.id) AS num_compras,
                   (SELECT SUM(v.total_rancho) FROM ventas v WHERE v.cliente_id = c.id) AS total_comprado
            FROM clientes c
            LEFT JOIN usuarios u ON u.id = c.usuario_id
            WHERE c.activo = 1 AND c.tipo = %s
            ORDER BY c.nombre
        """, (filtro,))

    if not clientes:
        st.info("No hay clientes registrados.")
        return

    colores_tipo = {
        "Nuevo":      "🟢",
        "Retenido":   "🔵",
        "Recuperado": "🟡",
        "Disponible": "⚪",
        "Sin comision": "⚫",
    }

    for c in clientes:
        emoji = colores_tipo.get(c["tipo"], "⚪")
        ultima = c["ultima_compra"].strftime("%d/%m/%Y") if c["ultima_compra"] else "Sin compras"
        total = f"${c['total_comprado']:,.2f}" if c["total_comprado"] else "$0"

        with st.expander(
            f"{emoji} {c['nombre']} — {c['tipo']} — Vendedor: {c['vendedor']}",
            expanded=False
        ):
            col1, col2 = st.columns(2)
            col1.markdown(f"""
            **Teléfono:** {c['telefono']}  
            **Tipo:** {c['tipo']} ({COMISIONES.get(c['tipo'], 0)}/kg)  
            **Vendedor:** {c['vendedor']}  
            **Compras:** {c['num_compras'] or 0}  
            **Total comprado:** {total}  
            **Última compra:** {ultima}
            """)

            col2.markdown("**Modificar:**")
            usuarios = fetch_all("SELECT id, nombre FROM usuarios WHERE activo = 1 ORDER BY nombre")
            nombres_u = {u["nombre"]: u["id"] for u in usuarios}
            nombres_u["— Sin vendedor —"] = None

            nuevo_tipo = col2.selectbox(
                "Tipo:",
                ["Nuevo", "Retenido", "Recuperado", "Disponible", "Sin comision"],
                index=["Nuevo", "Retenido", "Recuperado", "Disponible", "Sin comision"].index(c["tipo"]) if c["tipo"] in ["Nuevo", "Retenido", "Recuperado", "Disponible", "Sin comision"] else 0,
                key=f"tipo_{c['id']}"
            )
            nuevo_vendedor = col2.selectbox(
                "Vendedor:",
                list(nombres_u.keys()),
                index=list(nombres_u.keys()).index(c["vendedor"]) if c["vendedor"] in nombres_u else 0,
                key=f"vend_{c['id']}"
            )

            if col2.button("Actualizar", key=f"upd_{c['id']}", type="primary"):
                execute(
                    "UPDATE clientes SET tipo = %s, usuario_id = %s WHERE id = %s",
                    (nuevo_tipo, nombres_u[nuevo_vendedor], c["id"])
                )
                st.success("Cliente actualizado.")
                st.rerun()


def _registrar_cliente():
    st.subheader("Registrar nuevo cliente")

    usuarios = fetch_all("SELECT id, nombre FROM usuarios WHERE activo = 1 ORDER BY nombre")
    nombres_u = {u["nombre"]: u["id"] for u in usuarios}

    col1, col2 = st.columns(2)
    nombre   = col1.text_input("Nombre:", key="cli_nombre")
    telefono = col2.text_input("Teléfono:", placeholder="10 dígitos", key="cli_tel")

    col3, col4 = st.columns(2)
    tipo     = col3.selectbox("Tipo:", ["Nuevo", "Retenido", "Recuperado", "Sin comision"], key="cli_tipo")
    vendedor = col4.selectbox("Vendedor:", list(nombres_u.keys()), key="cli_vendedor")

    st.caption(f"Comisión aplicable: **${COMISIONES.get(tipo, 0)}/kg**")

    if st.button("Registrar cliente", type="primary", use_container_width=True):
        if not nombre:
            st.error("El nombre es obligatorio.")
            return
        if not telefono or len(telefono) < 10:
            st.error("El teléfono debe tener al menos 10 dígitos.")
            return

        existente = fetch_one("SELECT id FROM clientes WHERE telefono = %s", (telefono,))
        if existente:
            st.error("Ya existe un cliente con ese teléfono.")
            return

        execute(
            "INSERT INTO clientes (nombre, telefono, tipo, usuario_id) VALUES (%s, %s, %s, %s)",
            (nombre, telefono, tipo, nombres_u[vendedor])
        )
        st.success(f"Cliente '{nombre}' registrado como {tipo} — Comisión: ${COMISIONES.get(tipo, 0)}/kg")
        # Limpiar formulario
        for key in ["cli_nombre", "cli_tel"]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()