"""
modulos/reportes.py - Corralia v3
Reportes y analisis. Solo visible para Admin (Saul).
"""

import streamlit as st
import pandas as pd
import os
from datetime import date
from modulos.lotes import get_proximos_partos, get_pie_cria_por_estado, get_inventario_completo
from modulos.movimientos import get_historial, get_alertas_activas, marcar_todas_leidas
from modulos.chiqueros import get_alertas_capacidad


def mostrar_reportes():
    col_titulo, col_refresh = st.columns([5, 1])
    col_titulo.title("Reportes")
    if col_refresh.button("🔄 Actualizar", use_container_width=True, key="refresh_reportes"):
        st.rerun()
    st.caption("Panel exclusivo de administracion - Saul")

    tab0, tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Reporte Mensual", "Pie de Cria", "Proximos Partos", "Alertas", "Historial", "Asistencia"
    ])

    with tab0:
        _reporte_mensual()

    # Tab 1: Estado del pie de cria
    with tab1:
        st.subheader("Estado reproductivo del pie de cria")
        estados = get_pie_cria_por_estado()

        if not estados:
            st.info("No hay pie de cria registrado.")
        else:
            cols = st.columns(len(estados))
            colores = {
                "Disponible": "#7B1FA2",
                "Cubierta":   "#0288D1",
                "Gestacion":  "#2E7D32",
                "Gestaci\u00f3n": "#2E7D32",
                "Parida":     "#E65100",
                "Desecho":    "#616161",
                "Sin estado": "#9E9E9E",
            }
            for i, (estado, total) in enumerate(estados.items()):
                with cols[i]:
                    color = colores.get(estado, "#333")
                    st.markdown(f"""
                    <div style="border:2px solid {color}; border-radius:10px;
                                padding:16px; text-align:center; margin-bottom:10px;">
                        <div style="font-size:28px; font-weight:800; color:{color};">{total}</div>
                        <div style="font-size:12px; color:#555;">{estado}</div>
                    </div>
                    """, unsafe_allow_html=True)

        st.markdown("---")
        st.subheader("Inventario completo")
        df = pd.DataFrame(get_inventario_completo())
        if not df.empty:
            df_show = df[["corral", "tipo_chiquero", "tipo_animal",
                          "poblacion_actual", "capacidad_max", "area_m2"]].copy()
            df_show.columns = ["Corral", "Tipo", "Animales", "Poblacion", "Capacidad", "m2"]
            st.dataframe(df_show, use_container_width=True, hide_index=True)

    # Tab 2: Proximos partos
    with tab2:
        st.subheader("Partos estimados proximos 30 dias")
        partos = get_proximos_partos(dias=30)

        if not partos:
            st.info("No hay partos programados en los proximos 30 dias.")
        else:
            for p in partos:
                dias = int(p["dias_restantes"]) if p["dias_restantes"] else "?"
                color = "#D32F2F" if isinstance(dias, int) and dias <= 7 else "#E65100"
                fecha_str = p["fecha_parto_estimada"].strftime("%d/%m/%Y") if p["fecha_parto_estimada"] else "?"
                st.markdown(f"""
                <div style="border-left:4px solid {color}; padding:10px;
                            background:#fff8f0; border-radius:4px; margin-bottom:8px;">
                    <strong>{p['corral']}</strong> - Arete: {p['arete'] or 'S/A'}<br>
                    <span style="color:{color};">Fecha: {fecha_str} - faltan <strong>{dias} dias</strong></span><br>
                    <small>Monta: {p['fecha_monta'].strftime('%d/%m/%Y') if p['fecha_monta'] else 'Sin fecha'}</small>
                </div>
                """, unsafe_allow_html=True)

    # Tab 3: Alertas
    with tab3:
        st.subheader("Alertas activas")
        alertas = get_alertas_activas()
        alertas_cap = get_alertas_capacidad()

        if alertas_cap:
            st.markdown("**Capacidad de corrales:**")
            for a in alertas_cap:
                nivel = "🔴" if a["nivel"] == "rojo" else "🟡"
                st.write(f"{nivel} **{a['nombre']}** - {a['porcentaje']}% ocupado")

        st.markdown("---")
        if not alertas:
            st.success("Sin alertas pendientes.")
        else:
            for a in alertas:
                tipo_icon = {"PARTO_PROXIMO": "🐷", "CAPACIDAD": "📦",
                             "FOTO_PENDIENTE": "📷", "ESTADO_ANIMAL": "⚠️"}.get(a.get("tipo", ""), "🔔")
                st.warning(f"{tipo_icon} {a['mensaje']}")
            if st.button("Marcar todas como leidas"):
                marcar_todas_leidas()
                st.rerun()

    # Tab 4: Historial
    with tab4:
        st.subheader("Historial de movimientos")
        filtro_evento = st.selectbox(
            "Filtrar por evento:",
            ["Todos", "ENTRADA", "TRASPASO", "PARTO", "VENTA", "MUERTE", "CAMBIO_ESTADO"]
        )
        evento = None if filtro_evento == "Todos" else filtro_evento
        historial = get_historial(tipo_evento=evento, limit=100)

        if not historial:
            st.info("Sin registros.")
        else:
            for h in historial:
                fecha   = h["fecha"].strftime("%d/%m/%Y %H:%M") if h["fecha"] else "?"
                origen  = h.get("corral_origen")  or "-"
                destino = h.get("corral_destino") or "-"
                nota    = h.get("notas") or ""
                st.markdown(f"""
                <div style="border-left:3px solid #2E7D32; padding:8px 12px;
                            background:#f9f9f9; border-radius:3px; margin-bottom:6px;">
                    <small style="color:#888;">{fecha} - Por: {h.get('usuario','?')}</small><br>
                    <strong>{h['tipo_evento']}</strong>: {h['cantidad']} {h['tipo_animal']}<br>
                    {origen} -> {destino}<br>
                    <small><i>{nota}</i></small>
                </div>
                """, unsafe_allow_html=True)

    # Tab 5: Asistencia
    with tab5:
        st.subheader("Asistencia del dia")
        from database import fetch_all

        fecha_sel = st.date_input("Fecha:", value=date.today())

        registros = fetch_all(
            """
            SELECT a.nombre, a.fecha_entrada, a.fecha_salida,
                   a.foto_entrada, a.foto_salida, u.rol
            FROM asistencia a
            JOIN usuarios u ON u.id = a.usuario_id
            WHERE DATE(a.fecha_entrada) = %s
            ORDER BY a.fecha_entrada
            """,
            (fecha_sel,)
        )

        if not registros:
            st.info(f"Sin registros para {fecha_sel.strftime('%d/%m/%Y')}.")
        else:
            for r in registros:
                salida_str = r['fecha_salida'].strftime('%H:%M') if r['fecha_salida'] else "Sin salida"
                with st.expander(
                    f"{r['nombre']} — Entrada: {r['fecha_entrada'].strftime('%H:%M')} | Salida: {salida_str}",
                    expanded=False
                ):
                    c1, c2 = st.columns(2)
                    if r['foto_entrada'] and str(r['foto_entrada']).startswith('http'):
                        c1.markdown("**Entrada**")
                        c1.image(r['foto_entrada'], use_container_width=True)
                    else:
                        c1.caption("Sin foto de entrada")

                    if r['foto_salida'] and str(r['foto_salida']).startswith('http'):
                        c2.markdown("**Salida**")
                        c2.image(r['foto_salida'], use_container_width=True)
                    else:
                        c2.caption("Sin foto de salida")


def _reporte_mensual():
    """Reporte mensual limpio para el papá."""
    from database import fetch_all, fetch_one
    from datetime import date, datetime
    from zoneinfo import ZoneInfo

    hoy = date.today()

    # Selector de mes
    col1, col2 = st.columns(2)
    mes = col1.selectbox("Mes:", list(range(1, 13)),
                         index=hoy.month - 1,
                         format_func=lambda m: ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                                                "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][m-1],
                         key="rep_mes")
    anio = col2.number_input("Año:", min_value=2024, max_value=2030,
                              value=hoy.year, step=1, key="rep_anio")

    nombre_mes = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                  "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][mes-1]

    st.markdown("---")
    st.markdown(f"## 🐖 Rancho Yáñez — {nombre_mes} {anio}")
    st.caption("Atlacomulco, Estado de México")
    st.markdown("---")

    # ── Inventario actual ─────────────────────────────────────────────────────
    st.markdown("### 📦 Inventario actual")
    inv = fetch_all("""
        SELECT l.tipo_animal, SUM(l.poblacion_actual) AS total
        FROM lotes l
        WHERE l.poblacion_actual > 0
        GROUP BY l.tipo_animal
        ORDER BY l.tipo_animal
    """)
    total_animales = 0
    for r in inv:
        st.markdown(f"**{r['tipo_animal']}:** {int(r['total'])} animales")
        total_animales += int(r['total'])
    st.markdown(f"**Total en rancho: {total_animales} animales**")

    st.markdown("---")

    # ── Movimientos del mes ───────────────────────────────────────────────────
    st.markdown("### 📊 Movimientos del mes")

    movs = fetch_all("""
        SELECT tipo_evento, SUM(cantidad) AS total
        FROM historial_movimientos
        WHERE MONTH(fecha) = %s AND YEAR(fecha) = %s
        GROUP BY tipo_evento
    """, (mes, anio))

    movs_dict = {m["tipo_evento"]: int(m["total"]) for m in movs}
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🍼 Nacidos", movs_dict.get("PARTO", 0))
    col2.metric("💀 Muertes", movs_dict.get("MUERTE", 0))
    col3.metric("💰 Vendidos", movs_dict.get("VENTA", 0))
    col4.metric("🔄 Traspasos", movs_dict.get("TRASPASO", 0))

    st.markdown("---")

    # ── Finanzas del mes ──────────────────────────────────────────────────────
    st.markdown("### 💵 Finanzas del mes")

    # Depositos del mes
    dep = fetch_one("""
        SELECT IFNULL(SUM(monto),0) AS t FROM finanzas
        WHERE tipo='deposito' AND MONTH(fecha)=%s AND YEAR(fecha)=%s
    """, (mes, anio))
    total_dep = float(dep["t"]) if dep else 0

    # Ventas del mes
    ven = fetch_one("""
        SELECT IFNULL(SUM(total_rancho),0) AS t FROM ventas
        WHERE MONTH(fecha)=%s AND YEAR(fecha)=%s
    """, (mes, anio))
    total_ven = float(ven["t"]) if ven else 0

    # Gastos almacen del mes
    alm = fetch_one("""
        SELECT IFNULL(SUM(costo),0) AS t FROM almacen
        WHERE tipo='entrada' AND costo IS NOT NULL
        AND MONTH(fecha)=%s AND YEAR(fecha)=%s
    """, (mes, anio))
    total_alm = float(alm["t"]) if alm else 0

    # Sueldos del mes
    sue = fetch_one("""
        SELECT IFNULL(SUM(monto),0) AS t FROM finanzas
        WHERE tipo='sueldo' AND MONTH(fecha)=%s AND YEAR(fecha)=%s
    """, (mes, anio))
    total_sue = float(sue["t"]) if sue else 0

    total_ingresos = total_dep + total_ven
    total_gastos = total_alm + total_sue
    utilidad = total_ven - total_gastos

    st.markdown("**Ingresos:**")
    col1, col2 = st.columns(2)
    col1.metric("Depósitos recibidos", f"${total_dep:,.2f}")
    col2.metric("Ventas del mes", f"${total_ven:,.2f}")

    st.markdown("**Gastos:**")
    col3, col4 = st.columns(2)
    col3.metric("Alimento e insumos", f"${total_alm:,.2f}")
    col4.metric("Sueldos", f"${total_sue:,.2f}")

    st.markdown("---")

    col_u, col_s = st.columns(2)
    utilidad_color = "normal" if utilidad >= 0 else "inverse"
    col_u.metric("Utilidad bruta del mes", f"${utilidad:,.2f}",
                 delta="positiva" if utilidad >= 0 else "negativa",
                 delta_color=utilidad_color)

    saldo_beyin = total_dep + total_ven - total_alm - total_sue
    col_s.metric("Saldo con Beyin", f"${saldo_beyin:,.2f}")

    if utilidad >= 0:
        st.success(f"✅ Mes rentable — utilidad de ${utilidad:,.2f}")
    else:
        st.error(f"⚠️ Gastos superan ventas por ${abs(utilidad):,.2f}")