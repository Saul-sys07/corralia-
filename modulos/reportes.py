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
    st.title("Reportes")
    st.caption("Panel exclusivo de administracion - Saul")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Pie de Cria", "Proximos Partos", "Alertas", "Historial", "Asistencia"
    ])

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
                    if r['foto_entrada'] and os.path.exists(r['foto_entrada']):
                        c1.markdown("**Entrada**")
                        c1.image(r['foto_entrada'], use_container_width=True)
                    else:
                        c1.caption("Sin foto de entrada")

                    if r['foto_salida'] and os.path.exists(r['foto_salida']):
                        c2.markdown("**Salida**")
                        c2.image(r['foto_salida'], use_container_width=True)
                    else:
                        c2.caption("Sin foto de salida")