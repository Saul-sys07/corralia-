"""
modulos/almacen.py - Corralia v3
Control de inventario de alimento e insumos.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from database import fetch_all, execute

def hora_mexico():
    return datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)

PRODUCTOS = {
    "pellet": [
        "Pellet Destete/Crecimiento",
        "Pellet Finalizador (Engorda)",
        "Pellet Otro",
    ],
    "revoltura": [
        "Maíz molido",
        "Salvado",
        "Soya",
        "Sal/Omega/Minerales",
        "Melaza",
    ],
    "otro": [
        "Medicamento/Vacuna",
        "Gasolina camioneta",
        "Gasolina bomba",
        "Material construcción",
        "Otro",
    ]
}

UNIDADES = {
    "Maíz molido": "bulto",
    "Salvado": "bulto",
    "Soya": "bulto",
    "Sal/Omega/Minerales": "kg",
    "Melaza": "litro",
    "Pellet Destete/Crecimiento": "bulto",
    "Pellet Finalizador (Engorda)": "bulto",
    "Pellet Otro": "bulto",
    "Gasolina camioneta": "litro",
    "Gasolina bomba": "litro",
    "Medicamento/Vacuna": "pieza",
    "Material construcción": "pieza",
    "Otro": "pieza",
}

KG_POR_BULTO = {
    "Maíz molido": 40,
    "Salvado": 25,
    "Soya": 40,
    "Pellet Destete/Crecimiento": 40,
    "Pellet Finalizador (Engorda)": 40,
}


def mostrar_almacen():
    st.title("Almacén")
    st.caption("Control de alimento e insumos")

    tab1, tab2, tab3 = st.tabs(["Registrar", "Inventario", "Historial"])

    with tab1:
        _registrar_movimiento()

    with tab2:
        _mostrar_inventario()

    with tab3:
        _mostrar_historial()


def _registrar_movimiento():
    st.subheader("Registrar movimiento")

    tipo = st.radio("Tipo:", ["Compra (entrada)", "Uso semanal (salida)"],
                    horizontal=True, key="alm_tipo")
    es_entrada = tipo == "Compra (entrada)"

    categoria = st.radio("Categoría:", ["pellet", "revoltura", "otro"],
                         horizontal=True, key="alm_cat",
                         format_func=lambda x: x.capitalize())

    productos_cat = PRODUCTOS[categoria]
    producto = st.radio("Producto:", productos_cat,
                        horizontal=True, key="alm_prod")

    unidad = UNIDADES.get(producto, "pieza")
    kg_bulto = KG_POR_BULTO.get(producto)

    col1, col2 = st.columns(2)
    cantidad = col1.number_input(
        f"Cantidad ({unidad}):",
        min_value=0.1, step=0.5, key="alm_cant"
    )

    if kg_bulto and unidad == "bulto":
        col1.caption(f"= {cantidad * kg_bulto:.0f} kg")

    costo = None
    if es_entrada:
        costo = col2.number_input("Costo ($):", min_value=0.0, step=10.0, key="alm_costo")

    notas = st.text_input("Notas (opcional):", key="alm_notas")

    if st.button("Registrar", type="primary", use_container_width=True, key="btn_alm"):
        execute(
            """INSERT INTO almacen
               (tipo, categoria, producto, cantidad, unidad, costo, notas, usuario_id, fecha)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            ("entrada" if es_entrada else "salida",
             categoria, producto, cantidad, unidad,
             costo, notas, st.session_state.usuario_nombre, hora_mexico())
        )
        accion = "Compra" if es_entrada else "Uso"
        st.success(f"{accion} registrada: {cantidad} {unidad} de {producto}" +
                   (f" — ${costo:,.2f}" if costo else ""))
        import time
        time.sleep(1)
        st.rerun()


def _mostrar_inventario():
    st.subheader("Inventario actual")
    st.caption("Entradas menos salidas registradas")

    inv = fetch_all("""
        SELECT producto, unidad,
               SUM(CASE WHEN tipo='entrada' THEN cantidad ELSE -cantidad END) AS stock,
               SUM(CASE WHEN tipo='entrada' THEN costo ELSE 0 END) AS total_invertido
        FROM almacen
        GROUP BY producto, unidad
        HAVING stock > 0
        ORDER BY producto
    """)

    if not inv:
        st.info("Sin movimientos registrados.")
        return

    for r in inv:
        kg = KG_POR_BULTO.get(r["producto"])
        kg_str = f" ({r['stock'] * kg:.0f} kg)" if kg and r["unidad"] == "bulto" else ""
        st.markdown(f"""
        <div style="border-left:4px solid #2E7D32;padding:8px 12px;
                    background:#f9f9f9;border-radius:3px;margin-bottom:6px;">
            <strong>{r['producto']}</strong>: {r['stock']:.1f} {r['unidad']}{kg_str}<br>
            <small style="color:#888;">Total invertido: ${r['total_invertido']:,.2f}</small>
        </div>
        """, unsafe_allow_html=True)


def _mostrar_historial():
    st.subheader("Historial de movimientos")

    movimientos = fetch_all("""
        SELECT fecha, tipo, categoria, producto, cantidad, unidad, costo, notas, usuario_id
        FROM almacen
        ORDER BY fecha DESC
        LIMIT 50
    """)

    if not movimientos:
        st.info("Sin movimientos.")
        return

    for m in movimientos:
        fecha = m["fecha"].strftime("%d/%m/%Y %H:%M") if m["fecha"] else "?"
        emoji = "📦" if m["tipo"] == "entrada" else "📤"
        costo_str = f" — ${m['costo']:,.2f}" if m["costo"] else ""
        st.markdown(f"""
        <div style="border-left:3px solid {'#2E7D32' if m['tipo']=='entrada' else '#E65100'};
                    padding:6px 12px;background:#f9f9f9;border-radius:3px;margin-bottom:4px;">
            <small style="color:#888;">{fecha} — {m['usuario_id']}</small><br>
            {emoji} <strong>{m['producto']}</strong>: {m['cantidad']} {m['unidad']}{costo_str}<br>
            {'<small><i>' + m['notas'] + '</i></small>' if m['notas'] else ''}
        </div>
        """, unsafe_allow_html=True)