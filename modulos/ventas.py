"""
modulos/ventas.py - Corralia v3
Registro de ventas con sistema de clientes y comisiones.
"""

import streamlit as st
import time
import pandas as pd
from datetime import date, datetime
from database import fetch_all, fetch_one, execute
import cloudinary
import cloudinary.uploader
from config import CLOUDINARY_CONFIG

cloudinary.config(
    cloud_name=CLOUDINARY_CONFIG["cloud_name"],
    api_key=CLOUDINARY_CONFIG["api_key"],
    api_secret=CLOUDINARY_CONFIG["api_secret"],
)

COMISIONES = {
    "Nuevo":        3.00,
    "Retenido":     1.50,
    "Recuperado":   2.00,
    "Sin comision": 0.00,
}


# ── Clientes ──────────────────────────────────────────────────────────────────

def get_clientes() -> list[dict]:
    return fetch_all("""
        SELECT c.*, u.nombre AS vendedor
        FROM clientes c
        JOIN usuarios u ON u.id = c.usuario_id
        WHERE c.activo = 1
        ORDER BY c.nombre
    """)


def get_cliente_por_telefono(telefono: str):
    return fetch_one(
        "SELECT c.*, u.nombre AS vendedor FROM clientes c JOIN usuarios u ON u.id = c.usuario_id WHERE c.telefono = %s",
        (telefono,)
    )


def crear_cliente(nombre: str, telefono: str, tipo: str, usuario_id: int) -> int:
    return execute(
        "INSERT INTO clientes (nombre, telefono, tipo, usuario_id) VALUES (%s, %s, %s, %s)",
        (nombre, telefono, tipo, usuario_id)
    )


# ── Registro de venta ─────────────────────────────────────────────────────────

def mostrar_registro_venta():
    st.markdown("### Registrar Venta")

    from modulos.lotes import get_inventario_completo, get_lote

    # Limpiar estados de navegacion y camara
    corral_origen = st.session_state.pop("corral_presel", None)
    st.session_state.pop("tab_presel", None)
    st.session_state.pop("camara_bascula_activa", None)
    st.session_state.pop("foto_bascula_url", None)

    # ── Paso 1: Cliente ───────────────────────────────────────────────────────
    st.markdown("**1. Cliente**")

    todos_clientes = fetch_all(
        """SELECT c.*, u.nombre AS vendedor 
           FROM clientes c 
           LEFT JOIN usuarios u ON u.id = c.usuario_id
           WHERE c.activo = 1
           ORDER BY c.nombre""",
    )

    cliente = None

    if not todos_clientes:
        st.error("No hay clientes registrados. Pide a Saúl que registre clientes primero.")
        return

    etiquetas = [f"{c['nombre']} ({c['telefono']})" for c in todos_clientes]
    mapa = {f"{c['nombre']} ({c['telefono']})": c for c in todos_clientes}

    sel = st.radio("Selecciona el cliente:", etiquetas, key="venta_sel_cliente")
    cliente = mapa.get(sel)

    if not cliente:
        return

    st.success(f"**{cliente['nombre']}** — {cliente['tipo']} — Vendedor: {cliente['vendedor'] or 'Sin vendedor'} — Comisión: ${COMISIONES.get(cliente['tipo'], 0)}/kg")

    st.markdown("---")

    # ── Paso 2: Animales ──────────────────────────────────────────────────────
    st.markdown("**2. Animales**")

    df_inv = pd.DataFrame(get_inventario_completo())
    
    # Solo corrales con tipos vendibles
    tipos_vendibles = {"Destete", "Engorda", "Desecho"}
    df_vendibles = df_inv[
        (df_inv["poblacion_actual"] > 0) &
        (df_inv["tipo_animal"].apply(
            lambda x: any(t.strip() in tipos_vendibles for t in str(x).split("/"))
        ))
    ]

    if df_vendibles.empty:
        st.info("No hay animales disponibles para venta (Destete, Engorda o Desecho).")
        return

    corrales_v = df_vendibles["corral"].unique().tolist()
    corral_sel = st.radio("Corral:", corrales_v, key="venta_corral", horizontal=True)
    datos_corral = df_vendibles[df_vendibles["corral"] == corral_sel].iloc[0]
    id_corral = int(datos_corral["id"])

    # Solo tipos vendibles en ese corral
    tipos_en_corral = [t.strip() for t in str(datos_corral["tipo_animal"]).split("/")
                       if t.strip() in tipos_vendibles]
    tipo_animal = st.radio("Tipo:", tipos_en_corral, key="venta_tipo_animal", horizontal=True)

    lote = get_lote(id_corral, tipo_animal)
    disponible = int(lote["poblacion_actual"]) if lote else 0
    st.caption(f"Disponibles: {disponible}")

    cantidad = st.number_input("Cantidad:", min_value=1, max_value=disponible, step=1, key="venta_cantidad")

    st.markdown("---")

    # ── Paso 3: Precio y peso ─────────────────────────────────────────────────
    st.markdown("**3. Precio**")

    from database import fetch_one as _fetch_one
    row_precio = _fetch_one("SELECT valor FROM configuracion WHERE clave = 'precio_kg'")
    precio_sistema = float(row_precio["valor"]) if row_precio else 48.00
    rol_actual = st.session_state.get("usuario_rol", "admin")

    # Comision automatica segun tipo de cliente
    comision_kg = COMISIONES.get(cliente["tipo"], 0.0) if cliente else 0.0

    es_destete = tipo_animal == "Destete"

    if es_destete:
        # Destete se vende por cabeza, no por kilo
        st.info("Destete — venta por cabeza")
        col3, col4 = st.columns(2)
        precio_cabeza = col3.number_input("Precio por cabeza ($):", min_value=0.0, step=50.0, key="venta_precio_cab")
        peso_kg = 0.0
        precio_kg = 0.0
        comision_unit = comision_kg  # comision en pesos por cabeza vendida
        total_venta    = round(precio_cabeza * cantidad, 2)
        total_comision = round(comision_unit * cantidad, 2)
        total_rancho   = round((precio_cabeza - comision_unit) * cantidad, 2)
        if precio_cabeza > 0:
            col4.metric("Total venta", f"${total_venta:,.2f}")
            st.info(
                f"Total venta: **${total_venta:,.2f}** | "
                f"Rancho: **${total_rancho:,.2f}** | "
                f"Comisión: **${total_comision:,.2f}**"
            )
    else:
        # Engorda y Desecho por kilo
        col3, col4 = st.columns(2)
        peso_kg = col3.number_input("Peso total (kg):", min_value=0.1, step=0.5, key="venta_peso")

        if rol_actual == "admin":
            precio_kg = col4.number_input("Precio por kg ($):", min_value=0.0,
                                           value=precio_sistema, step=0.50, key="venta_precio")
        else:
            precio_kg = precio_sistema
            col4.info(f"Precio del día: **${precio_kg}/kg**")

        precio_cabeza  = 0.0
        precio_rancho  = precio_kg - comision_kg
        total_rancho   = round(precio_rancho * peso_kg, 2)
        total_comision = round(comision_kg * peso_kg, 2)
        total_venta    = round(precio_kg * peso_kg, 2)

        if precio_kg > 0:
            st.info(
                f"Total venta: **${total_venta:,.2f}** | "
                f"Rancho: **${total_rancho:,.2f}** | "
                f"Comisión ({comision_kg}/kg): **${total_comision:,.2f}**"
            )

    st.markdown("---")

    # ── Confirmar venta ───────────────────────────────────────────────────────
    st.session_state.foto_bascula_url = None  # Sin foto por ahora
    puede_confirmar = (
        cliente is not None and
        (peso_kg > 0 or precio_cabeza > 0) and
        (precio_kg > 0 or precio_cabeza > 0)
    )

    if st.button(
        "Confirmar venta",
        type="primary",
        use_container_width=True,
        disabled=not puede_confirmar,
        key="btn_confirmar_venta"
    ):
        # Restar del inventario
        execute(
            "UPDATE lotes SET poblacion_actual = GREATEST(poblacion_actual - %s, 0) WHERE id_chiquero = %s AND tipo_animal = %s",
            (cantidad, id_corral, tipo_animal)
        )

        # Registrar venta
        execute(
            """INSERT INTO ventas
               (cliente_id, usuario_id, tipo_animal, cantidad, peso_kg, precio_kg,
                comision_kg, total_rancho, total_comision, foto_bascula)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (cliente["id"], st.session_state.usuario_id, tipo_animal, cantidad,
             peso_kg, precio_kg if not es_destete else precio_cabeza,
             comision_kg, total_rancho, total_comision, "")
        )

        # Historial
        execute(
            """INSERT INTO historial_movimientos
               (id_chiquero_destino, tipo_animal, cantidad, tipo_evento, id_usuario, notas, foto_evidencia)
               VALUES (%s, %s, %s, 'VENTA', %s, %s, %s)""",
            (id_corral, tipo_animal, cantidad, st.session_state.usuario_nombre,
             f"Venta a {cliente['nombre']} — ${total_venta:,.2f}", None)
        )

        st.session_state.pop("accion_activa", None)
        st.success(f"Venta registrada. Total: ${total_venta:,.2f} | Comisión: ${total_comision:,.2f}")
        st.session_state.pagina = "mapa"
        time.sleep(2)
        st.rerun()

    if not puede_confirmar:
        if not cliente:
            st.warning("Selecciona un cliente para continuar.")


# ── Historial de ventas (para Admin) ─────────────────────────────────────────

def mostrar_historial_ventas():
    st.title("Ventas")
    st.caption("Historial y comisiones — solo Admin")

    tab1, tab2, tab3 = st.tabs(["Historial", "Comisiones", "Clientes"])

    with tab1:
        st.subheader("Ventas del mes")
        ventas = fetch_all("""
            SELECT v.fecha, c.nombre AS cliente, c.tipo AS tipo_cliente,
                   u.nombre AS vendedor, v.tipo_animal, v.cantidad,
                   v.peso_kg, v.precio_kg, v.total_rancho, v.total_comision,
                   v.foto_bascula, v.notas
            FROM ventas v
            JOIN clientes c ON c.id = v.cliente_id
            JOIN usuarios u ON u.id = v.usuario_id
            ORDER BY v.fecha DESC
            LIMIT 100
        """)

        if not ventas:
            st.info("Sin ventas registradas.")
        else:
            total_mes     = sum(v["total_rancho"] for v in ventas)
            total_com_mes = sum(v["total_comision"] for v in ventas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Total ventas", f"${sum(v['peso_kg']*v['precio_kg'] for v in ventas):,.2f}")
            c2.metric("Al rancho", f"${total_mes:,.2f}")
            c3.metric("En comisiones", f"${total_com_mes:,.2f}")

            st.markdown("---")
            for v in ventas:
                fecha = v["fecha"].strftime("%d/%m/%Y %H:%M") if v["fecha"] else "?"
                with st.expander(
                    f"{fecha} — {v['cliente']} ({v['tipo_cliente']}) — ${v['total_rancho']:,.2f}",
                    expanded=False
                ):
                    col1, col2 = st.columns(2)
                    col1.markdown(f"""
                    **Vendedor:** {v['vendedor']}  
                    **Animal:** {v['cantidad']} {v['tipo_animal']}  
                    **Peso:** {v['peso_kg']} kg  
                    **Precio:** ${v['precio_kg']}/kg  
                    **Total rancho:** ${v['total_rancho']:,.2f}  
                    **Comisión:** ${v['total_comision']:,.2f}  
                    """)
                    if v["foto_bascula"]:
                        col2.image(v["foto_bascula"], caption="Báscula", use_container_width=True)

    with tab2:
        st.subheader("Comisiones por vendedor")
        comisiones = fetch_all("""
            SELECT u.nombre AS vendedor,
                   COUNT(v.id) AS num_ventas,
                   SUM(v.total_comision) AS total_comision,
                   SUM(v.peso_kg) AS kg_vendidos
            FROM ventas v
            JOIN usuarios u ON u.id = v.usuario_id
            GROUP BY v.usuario_id
            ORDER BY total_comision DESC
        """)
        if not comisiones:
            st.info("Sin comisiones registradas.")
        else:
            for c in comisiones:
                st.markdown(f"""
                <div style="border-left:4px solid #2E7D32; padding:10px; margin-bottom:8px; background:#f9f9f9;">
                    <strong>{c['vendedor']}</strong> — {c['num_ventas']} ventas — 
                    {c['kg_vendidos']:.1f} kg vendidos<br>
                    <span style="color:#2E7D32; font-size:18px; font-weight:700;">
                        ${c['total_comision']:,.2f}
                    </span> en comisiones
                </div>
                """, unsafe_allow_html=True)

    with tab3:
        st.subheader("Cartera de clientes")
        clientes = fetch_all("""
            SELECT c.nombre, c.telefono, c.tipo, u.nombre AS vendedor,
                   COUNT(v.id) AS num_compras,
                   SUM(v.total_rancho) AS total_comprado
            FROM clientes c
            JOIN usuarios u ON u.id = c.usuario_id
            LEFT JOIN ventas v ON v.cliente_id = c.id
            WHERE c.activo = 1
            GROUP BY c.id
            ORDER BY total_comprado DESC
        """)
        if not clientes:
            st.info("Sin clientes registrados.")
        else:
            df = pd.DataFrame(clientes)
            df.columns = ["Nombre", "Teléfono", "Tipo", "Vendedor", "Compras", "Total $"]
            st.dataframe(df, use_container_width=True, hide_index=True)