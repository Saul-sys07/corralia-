def _tarjeta(row):
    cap  = max(int(row["capacidad_max"] or 1), 1)
    pob  = int(row["poblacion_actual"] or 0)
    area = float(row["area_m2"] or 0)
    pct  = pob / cap

    es_exclusivo = any(t in str(row.get("tipo_animal", ""))
                       for t in ["Semental", "Pie de Cr"])
    if pob == 0:
        color_hex   = "#9E9E9E"
        color_barra = "#E0E0E0"
        estado      = "VACÍO"
        emoji       = "⚫"
    elif es_exclusivo and pob <= cap:
        color_hex   = "#2E7D32"
        color_barra = "#4CAF50"
        estado      = "OCUPADO"
        emoji       = "🟢"
    elif pct >= 1.0:
        color_hex   = "#C62828"
        color_barra = "#EF5350"
        estado      = "EXCEDIDO"
        emoji       = "🔴"
    elif pct >= 0.9:
        color_hex   = "#F57F17"
        color_barra = "#FFC107"
        estado      = "AL LÍMITE"
        emoji       = "🟡"
    else:
        color_hex   = "#2E7D32"
        color_barra = "#4CAF50"
        estado      = "OK"
        emoji       = "🟢"

    pct_barra = min(pct * 100, 100)

    parto_html = ""
    if row.get("fecha_parto") and str(row["fecha_parto"]) not in ("None", "NaT", ""):
        try:
            parto_html = f"<div style='color:#E65100;font-size:11px;margin-top:4px;'>🗓 Parto: {row['fecha_parto'].strftime('%d/%m/%Y')}</div>"
        except Exception:
            pass

    estado_pc = ""
    val = row.get("estado_pie_cria")
    if val and str(val) not in ("None", "", "nan", "NaN"):
        estado_pc = f"<div style='color:#7B1FA2;font-size:11px;margin-top:2px;'>🔘 {val}</div>"

    area_str = f"{area:.1f} m²" if area > 0 else ""

    tipo_animal_raw = str(row.get("tipo_animal", ""))
    tipo_badge = tipo_animal_raw if (pob > 0 and tipo_animal_raw != "VACIO") else ""

    label_expander = f"{emoji} {row['nombre']}  —  {pob}/{cap}  {tipo_badge}"

    with st.expander(label_expander, expanded=False):
        # ── Tarjeta info ──────────────────────────────────────
        st.markdown(f"""
        <div style="
            border: 2px solid {color_hex};
            border-radius: 12px;
            padding: 14px 12px 10px;
            background: #fafafa;
            text-align: center;
            margin-bottom: 10px;
        ">
            <div style="font-size:11px;color:{color_hex};font-weight:700;letter-spacing:1px;margin-bottom:6px;">
                {emoji} {estado}
            </div>
            <div style="font-size:36px;font-weight:800;color:#111;line-height:1;">
                {pob}
            </div>
            <div style="font-size:12px;color:#888;margin-bottom:10px;">
                de {cap} {'lugar' if cap == 1 else 'lugares'}
            </div>
            <div style="background:#e0e0e0;border-radius:20px;height:10px;overflow:hidden;margin:0 8px 8px;">
                <div style="
                    width:{pct_barra:.0f}%;
                    height:100%;
                    background:{color_barra};
                    border-radius:20px;
                "></div>
            </div>
            <div style="font-size:11px;color:#aaa;">{area_str}</div>
            <div style="font-size:12px;font-weight:600;color:#444;margin-top:4px;">{tipo_badge}</div>
            {estado_pc}
            {parto_html}
        </div>
        """, unsafe_allow_html=True)

        # ── Botones de acción ─────────────────────────────────
        if pob > 0:
            tipos_en_corral = [t.strip() for t in tipo_animal_raw.split("/")
                               if t.strip() and t.strip() != "VACIO"]
            if len(tipos_en_corral) > 1:
                st.selectbox("Tipo:", tipos_en_corral, key=f"tipo_acc_{row['id']}")

            rol_actual = st.session_state.get("usuario_rol", "admin")
            mostrar_venta = rol_actual in ("admin", "encargado_general")

            if mostrar_venta:
                b1, b2, b3, b4 = st.columns(4)
            else:
                b1, b2, b3 = st.columns(3)

            if b1.button("🔄 Traslado", key=f"tras_{row['id']}", use_container_width=True):
                st.session_state.pagina = "traspaso"
                st.session_state.corral_presel = row['nombre']
                st.rerun()
            if b2.button("💀 Muerte", key=f"muer_{row['id']}", use_container_width=True):
                st.session_state.pagina = "traspaso"
                st.session_state.tab_presel = "muerte"
                st.session_state.corral_presel = row['nombre']
                st.rerun()
            if b3.button("📦 Etapa", key=f"etap_{row['id']}", use_container_width=True):
                st.session_state.pagina = "traspaso"
                st.session_state.tab_presel = "etapa"
                st.session_state.corral_presel = row['nombre']
                st.rerun()
            if mostrar_venta:
                if b4.button("💰 Venta", key=f"vent_{row['id']}", use_container_width=True):
                    st.session_state.pagina = "traspaso"
                    st.session_state.tab_presel = "venta"
                    st.session_state.corral_presel = row['nombre']
                    st.rerun()