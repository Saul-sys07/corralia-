"""
modulos/almacen.py - Corralia v3
Control de inventario de alimento e insumos.
La materia no se destruye, se transforma.
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from database import fetch_all, execute, fetch_one

def hora_mexico():
    return datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)

# Ingredientes de la revoltura
INGREDIENTES_REVOLTURA = ["Maíz molido", "Salvado", "Soya", "Sal/Omega/Minerales", "Melaza"]

# kg por bulto de cada ingrediente
KG_POR_BULTO = {
    "Maíz molido": 40,
    "Salvado": 25,
    "Soya": 40,
    "Pellet Destete/Crecimiento": 40,
    "Pellet Finalizador (Engorda)": 40,
    "Pellet Otro": 40,
}

PRODUCTOS_PELLET = [
    "Pellet Destete/Crecimiento",
    "Pellet Finalizador (Engorda)",
    "Pellet Otro",
]

PRODUCTOS_OTRO = [
    "Gasolina camioneta",
    "Gasolina bomba",
    "Medicamento/Vacuna",
    "Material construcción",
    "Otro",
]

UNIDADES = {
    "Maíz molido": "bulto",
    "Salvado": "bulto",
    "Soya": "bulto",
    "Sal/Omega/Minerales": "kg",
    "Melaza": "litro",
    "Revoltura lista": "kg",
    "Pellet Destete/Crecimiento": "bulto",
    "Pellet Finalizador (Engorda)": "bulto",
    "Pellet Otro": "bulto",
    "Gasolina camioneta": "litro",
    "Gasolina bomba": "litro",
    "Medicamento/Vacuna": "pieza",
    "Material construcción": "pieza",
    "Otro": "pieza",
}


def _get_stock(producto):
    """Devuelve el stock actual de un producto."""
    row = fetch_one("""
        SELECT IFNULL(SUM(CASE WHEN tipo='entrada' THEN cantidad ELSE -cantidad END), 0) AS stock
        FROM almacen WHERE producto = %s
    """, (producto,))
    return float(row["stock"]) if row else 0.0


def mostrar_almacen():
    st.title("Almacén")
    st.caption("Control de alimento e insumos")

    tab1, tab2, tab3, tab4 = st.tabs(["Compra", "Hacer Revoltura", "Uso", "Inventario"])

    with tab1:
        _registrar_compra()
    with tab2:
        _hacer_revoltura()
    with tab3:
        _registrar_uso()
    with tab4:
        _mostrar_inventario()


def _registrar_compra():
    """Beyin registra lo que compró — entra al inventario."""
    st.subheader("Registrar compra")
    st.caption("Lo que llegó hoy de Forrajes La Palma o donde sea")

    categoria = st.radio("Categoría:", ["Ingredientes revoltura", "Pellet", "Otro"],
                         horizontal=True, key="comp_cat")

    if categoria == "Ingredientes revoltura":
        productos = INGREDIENTES_REVOLTURA
    elif categoria == "Pellet":
        productos = PRODUCTOS_PELLET
    else:
        productos = PRODUCTOS_OTRO

    producto = st.radio("Producto:", productos, horizontal=True, key="comp_prod")
    unidad = UNIDADES.get(producto, "pieza")
    kg_bulto = KG_POR_BULTO.get(producto)

    col1, col2 = st.columns(2)
    cantidad = col1.number_input(f"Cantidad ({unidad}):", min_value=0.1, step=1.0, key="comp_cant")
    if kg_bulto and unidad == "bulto":
        col1.caption(f"= {cantidad * kg_bulto:.0f} kg")

    costo = col2.number_input("Costo total ($):", min_value=0.0, step=10.0, key="comp_costo")

    if st.button("Registrar compra", type="primary", use_container_width=True, key="btn_compra"):
        execute(
            """INSERT INTO almacen
               (tipo, categoria, producto, cantidad, unidad, costo, notas, usuario_id, fecha)
               VALUES ('entrada', %s, %s, %s, %s, %s, %s, %s, %s)""",
            (categoria, producto, cantidad, unidad, costo,
             f"Compra: {cantidad} {unidad} de {producto}",
             st.session_state.usuario_nombre, hora_mexico())
        )
        st.success(f"Registrado: {cantidad} {unidad} de {producto} — ${costo:,.2f}")
        time.sleep(1)
        st.rerun()


def _hacer_revoltura():
    """Transforma ingredientes en revoltura lista."""
    st.subheader("Hacer revoltura")
    st.caption("Los bultos se transforman en revoltura lista — la materia no se destruye 🐷")

    # Mostrar stock actual de ingredientes
    st.markdown("**Stock disponible:**")
    col1, col2, col3, col4, col5 = st.columns(5)
    stocks = {p: _get_stock(p) for p in INGREDIENTES_REVOLTURA}

    col1.metric("Maíz", f"{stocks['Maíz molido']:.0f} bts")
    col2.metric("Salvado", f"{stocks['Salvado']:.0f} bts")
    col3.metric("Soya", f"{stocks['Soya']:.0f} bts")
    col4.metric("Sal/Min", f"{stocks['Sal/Omega/Minerales']:.0f} kg")
    col5.metric("Melaza", f"{stocks['Melaza']:.0f} lts")

    st.markdown("---")
    st.markdown("**¿Cuánto vas a usar en esta revoltura?**")

    col1, col2 = st.columns(2)
    maiz   = col1.number_input("Maíz (bultos):", min_value=0.0,
                                max_value=float(max(stocks["Maíz molido"], 0.1)),
                                value=min(6.0, float(max(stocks["Maíz molido"], 0.1))),
                                step=1.0, key="rev_maiz")
    salvado = col2.number_input("Salvado (bultos):", min_value=0.0,
                                 max_value=float(max(stocks["Salvado"], 0.1)),
                                 value=min(6.0, float(max(stocks["Salvado"], 0.1))),
                                 step=1.0, key="rev_salvado")
    soya   = col1.number_input("Soya (bultos):", min_value=0.0,
                                max_value=float(max(stocks["Soya"], 0.1)),
                                value=min(1.0, float(max(stocks["Soya"], 0.1))),
                                step=1.0, key="rev_soya")
    sal    = col2.number_input("Sal/Minerales (kg):", min_value=0.0,
                                max_value=float(max(stocks["Sal/Omega/Minerales"], 0.1)),
                                value=min(2.0, float(max(stocks["Sal/Omega/Minerales"], 0.1))),
                                step=0.5, key="rev_sal")
    melaza = col1.number_input("Melaza (litros):", min_value=0.0,
                                max_value=float(max(stocks["Melaza"], 0.1)),
                                value=min(30.0, float(max(stocks["Melaza"], 0.1))),
                                step=1.0, key="rev_melaza")

    # Calcular kg totales de revoltura
    kg_revoltura = (maiz * 40) + (salvado * 25) + (soya * 40) + sal
    st.info(f"Revoltura resultante: **{kg_revoltura:.0f} kg**")

    if st.button("Hacer revoltura", type="primary", use_container_width=True, key="btn_revoltura"):
        usuario = st.session_state.usuario_nombre
        fecha = hora_mexico()
        notas = f"Revoltura: {maiz:.0f}bt maíz + {salvado:.0f}bt salvado + {soya:.0f}bt soya + {sal:.0f}kg sal + {melaza:.0f}L melaza"

        # Descontar ingredientes
        ingredientes = [
            ("Maíz molido", maiz, "bulto"),
            ("Salvado", salvado, "bulto"),
            ("Soya", soya, "bulto"),
            ("Sal/Omega/Minerales", sal, "kg"),
            ("Melaza", melaza, "litro"),
        ]
        for prod, cant, unid in ingredientes:
            if cant > 0:
                execute(
                    """INSERT INTO almacen
                       (tipo, categoria, producto, cantidad, unidad, costo, notas, usuario_id, fecha)
                       VALUES ('salida', 'Ingredientes revoltura', %s, %s, %s, NULL, %s, %s, %s)""",
                    (prod, cant, unid, notas, usuario, fecha)
                )

        # Agregar revoltura lista al inventario
        execute(
            """INSERT INTO almacen
               (tipo, categoria, producto, cantidad, unidad, costo, notas, usuario_id, fecha)
               VALUES ('entrada', 'revoltura', 'Revoltura lista', %s, 'kg', NULL, %s, %s, %s)""",
            (kg_revoltura, notas, usuario, fecha)
        )

        st.success(f"Revoltura lista: {kg_revoltura:.0f} kg registrados en inventario")
        time.sleep(1.5)
        st.rerun()


def _registrar_uso():
    """Registra lo que se consumió — revoltura o pellet."""
    st.subheader("Registrar uso")
    st.caption("Lo que se consumió esta semana")

    # Stock actual
    rev_stock = _get_stock("Revoltura lista")
    st.info(f"Revoltura disponible: **{rev_stock:.0f} kg**")

    uso_tipo = st.radio("¿Qué se usó?", ["Revoltura", "Pellet", "Otro"],
                        horizontal=True, key="uso_tipo")

    if uso_tipo == "Revoltura":
        producto = "Revoltura lista"
        unidad = "kg"
        cantidad = st.number_input("Kg consumidos:", min_value=0.1,
                                    max_value=float(max(rev_stock, 0.1)),
                                    step=10.0, key="uso_cant")
    elif uso_tipo == "Pellet":
        producto = st.radio("Tipo:", PRODUCTOS_PELLET, horizontal=True, key="uso_pellet")
        unidad = "bulto"
        stock_p = _get_stock(producto)
        st.caption(f"Stock: {stock_p:.0f} bultos")
        cantidad = st.number_input("Bultos consumidos:", min_value=0.1,
                                    step=1.0, key="uso_cant")
    else:
        producto = st.radio("Producto:", PRODUCTOS_OTRO, horizontal=True, key="uso_otro")
        unidad = UNIDADES.get(producto, "pieza")
        cantidad = st.number_input(f"Cantidad ({unidad}):", min_value=0.1,
                                    step=1.0, key="uso_cant")

    if st.button("Registrar uso", type="primary", use_container_width=True, key="btn_uso"):
        execute(
            """INSERT INTO almacen
               (tipo, categoria, producto, cantidad, unidad, costo, notas, usuario_id, fecha)
               VALUES ('salida', %s, %s, %s, %s, NULL, %s, %s, %s)""",
            (uso_tipo, producto, cantidad, unidad,
             f"Uso semanal: {cantidad} {unidad} de {producto}",
             st.session_state.usuario_nombre, hora_mexico())
        )
        st.success(f"Uso registrado: {cantidad} {unidad} de {producto}")
        time.sleep(1)
        st.rerun()


def _mostrar_inventario():
    """Inventario actual — entradas menos salidas."""
    st.subheader("Inventario actual")

    inv = fetch_all("""
        SELECT producto, unidad,
               SUM(CASE WHEN tipo='entrada' THEN cantidad ELSE -cantidad END) AS stock,
               SUM(CASE WHEN tipo='entrada' AND costo IS NOT NULL THEN costo ELSE 0 END) AS total_invertido
        FROM almacen
        GROUP BY producto, unidad
        ORDER BY 
            CASE producto
                WHEN 'Revoltura lista' THEN 0
                WHEN 'Maíz molido' THEN 1
                WHEN 'Salvado' THEN 2
                WHEN 'Soya' THEN 3
                WHEN 'Sal/Omega/Minerales' THEN 4
                WHEN 'Melaza' THEN 5
                ELSE 6
            END
    """)

    if not inv:
        st.info("Sin movimientos registrados.")
        return

    for r in inv:
        stock = float(r["stock"])
        if stock <= 0:
            continue
        kg = KG_POR_BULTO.get(r["producto"])
        kg_str = f" = {stock * kg:.0f} kg" if kg and r["unidad"] == "bulto" else ""
        color = "#1976D2" if r["producto"] == "Revoltura lista" else "#2E7D32"

        st.markdown(f"""
        <div style="border-left:4px solid {color};padding:8px 12px;
                    background:#f9f9f9;border-radius:3px;margin-bottom:6px;">
            <strong>{r['producto']}</strong>: {stock:.1f} {r['unidad']}{kg_str}<br>
            <small style="color:#888;">Invertido: ${r['total_invertido']:,.2f}</small>
        </div>
        """, unsafe_allow_html=True)