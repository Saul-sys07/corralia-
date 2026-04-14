import streamlit as st
import pandas as pd
import modulos.lotes as lotes_logic
from datetime import date
import time
import database as db
from streamlit_autorefresh import st_autorefresh

def mostrar_dashboard(df_lotes):
    # --- 1. CÁLCULO DE BIENESTAR ---
    df_lotes['m2_por_animal'] = df_lotes.apply(
        lambda x: x['area_m2'] / x['poblacion_actual'] if x['poblacion_actual'] > 0 else 0, 
        axis=1
    )

    # --- 🚨 SECCIÓN DE ALERTAS ---
    alertas = lotes_logic.obtener_alertas_reproduccion()
    if not alertas.empty:
        st.error(f"⚠️ **ATENCIÓN: Tienes {len(alertas)} confirmaciones de preñez pendientes.**")
        with st.expander("🔍 Ver detalles", expanded=False):
            for _, alert in alertas.iterrows():
                st.warning(f"📍 **{alert['nombre']}**: {int(alert['poblacion_actual'])} {alert['tipo_animal']}. Revisar confirmación.")

    # --- 📊 MÉTRICAS DE ALTO NIVEL ---
    total = df_lotes['poblacion_actual'].sum()
    cap_total = df_lotes['capacidad_max'].sum()
    ocupacion = (total / cap_total * 100) if cap_total > 0 else 0
    cerdos_vivos = df_lotes[df_lotes['poblacion_actual'] > 0]
    m2_promedio = cerdos_vivos['m2_por_animal'].mean() if not cerdos_vivos.empty else 0.0

    k1, k2, k3 = st.columns(3)
    k1.metric("Población Total", f"{int(total)} Cabezas", "Inventario Real")
    k2.metric("Ocupación", f"{ocupacion:.1f}%", f"{int(cap_total)} Espacios")
    k3.metric("Espacio Promedio", f"{m2_promedio:.2f} m²/animal", "Bienestar")

    st.markdown("---")

    # --- 🐖 DESGLOSE POR ETAPAS (Aquí es donde se definen sm, pc, etc.) ---
    st.subheader("📦 Inventario por Etapas")
    
    # Función interna para sumar rápido
    def sum_etapa(etapa_nombre):
        # Buscamos si el nombre de la etapa está en la columna tipo_animal (que ahora puede traer "Parida / Crías")
        return df_lotes[df_lotes['tipo_animal'].str.contains(etapa_nombre, na=False)]['poblacion_actual'].sum()

    # Definimos las variables que VS Code extrañaba
    sm, pc = sum_etapa('Semental'), sum_etapa('Pie de Cría')
    gb, pr = sum_etapa('Gestación'), sum_etapa('Próxima a Parir')
    la, cr = sum_etapa('Lactante'), sum_etapa('Crías')
    de, en = sum_etapa('Desarrollo'), sum_etapa('Engorda')
    ds, hz = sum_etapa('Desecho'), sum_etapa('Herniados')

    # Mostramos en columnas pequeñas
    r1 = st.columns(5)
    r1[0].metric("Sementales", int(sm))
    r1[1].metric("Pie de Cría", int(pc))
    r1[2].metric("Gestación", int(gb))
    r1[3].metric("Próximos", int(pr))
    r1[4].metric("Lactantes", int(la))

    r2 = st.columns(5)
    r2[0].metric("Crías", int(cr))
    r2[1].metric("Desarrollo", int(de))
    r2[2].metric("Engorda", int(en))
    r2[3].metric("Desecho", int(ds))
    r2[4].metric("Herniados", int(hz))

    st.markdown("---")
    
    # --- 📅 PRÓXIMOS EVENTOS CRÍTICOS ---
    st.markdown("### 📅 Próximos Partos")
    df_partos = df_lotes[df_lotes['fecha_parto'].notna()].sort_values('fecha_parto')
    
    if not df_partos.empty:
        proximos = df_partos[:4]
        cols_p = st.columns(len(proximos)) 
        for i, (_, row) in enumerate(proximos.iterrows()):
            f_parto = row['fecha_parto']
            dias = (f_parto.date() - date.today()).days
            with cols_p[i]:
                st.info(f"🐷 **{row['corral']}**\n\nParto: {f_parto.strftime('%d/%b')}\n\nFaltan: **{dias} días**")
    else:
        st.write("No hay partos programados.")

    st.markdown("---")
    col1, col2 = st.columns(2)

    def card(sigla, nombre, valor, bg, tx):
        st.markdown(f"""
        <div style="display:flex; align-items:center; gap:15px; padding:10px; 
                    background-color:{bg}; border-radius:10px; margin-bottom:8px; border: 1px solid #eee;">
            <div style="width:40px; height:40px; background:white; color:{tx}; 
                        border-radius:50%; display:flex; align-items:center; 
                        justify-content:center; font-weight:bold; border: 2px solid {tx};">
                {sigla}
            </div>
            <div style="flex:1; font-weight:600; color:#333;">{nombre}</div>
            <div style="font-size:18px; font-weight:700; color:{tx};">{int(valor)}</div>
        </div>""", unsafe_allow_html=True)

    with col1:
        st.markdown("#### 🧬 Reproducción")
        card("SM", "Sementales", sm, "#E3F2FD", "#0D47A1")
        card("PC", "Pie de Cría", pc, "#F3E5F5", "#7B1FA2")
        card("GB", "Gestación", gb, "#E8F5E9", "#2E7D32")
        card("PR", "Próxima a Parir", pr, "#FFF3E0", "#E65100")
        card("LA", "Lactante / Parida", la, "#FFFDE7", "#FBC02D")

    with col2:
        st.markdown("#### 📈 Crecimiento")
        card("CR", "Crías / Lechones", cr, "#FCE4EC", "#C2185B")
        card("DE", "Desarrollo", de, "#E1F5FE", "#0288D1")
        card("EN", "Engorda", en, "#E0F2F1", "#00796B")
        card("HZ", "Herniados", hz, "#FFEBEE", "#D32F2F")
        card("DS", "Desechos", ds, "#F5F5F5", "#616161")

def mostrar_mapa_táctico(df_lotes):
    # --- 1. CÁLCULO DE BIENESTAR PARA EL MAPA (ESTO FALTA) ---
    # Calculamos m2_por_animal antes de dibujar los cuadros
    df_lotes['m2_por_animal'] = df_lotes.apply(
        lambda x: x['area_m2'] / x['poblacion_actual'] if x['poblacion_actual'] > 0 else 0, 
        axis=1
    )

    # --- 2. REFRESH Y TÍTULO ---
    st_autorefresh(interval=10000, key="mapa_refresh")
    st.title("🗺️ Control Táctico de Instalaciones")

    # ... (El resto de tu código donde dibujas los cuadros) key="admin_refresh")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        raw_types = df_lotes['tipo_animal'].unique()
        tipos_reales = [str(t) for t in raw_types if pd.notna(t) and str(t).lower() != 'none']
        tipos_disp = ["Todos"] + sorted(tipos_reales)
        filtro_tipo = st.selectbox("Filtrar por Etapa Actual:", tipos_disp)
    with col2:
        estado = st.selectbox("Estado:", ["Todos", "Solo Vacíos", "Ocupados", "Excedidos"])

    df_f = df_lotes.copy()
    if filtro_tipo != "Todos": df_f = df_f[df_f['tipo_animal'] == filtro_tipo]
    if estado == "Solo Vacíos": df_f = df_f[df_f['poblacion_actual'] == 0]
    elif estado == "Ocupados": df_f = df_f[df_f['poblacion_actual'] > 0]
    elif estado == "Excedidos": df_f = df_f[df_f['poblacion_actual'] > df_f['capacidad_max']]

    if df_f.empty:
        st.warning("Sin coincidencias.")
        return

    cols = st.columns(3)
    for i, (idx, row) in enumerate(df_f.iterrows()):
        with cols[i % 3]:
            cap = row['capacidad_max'] if row['capacidad_max'] > 0 else 1
            uso = row['poblacion_actual'] / cap
            if row['poblacion_actual'] == 0: color, est = "#D3D3D3", "VACÍO"
            elif cap == 1: color, est = ("#2E7D32", "OCUPADO") if row['poblacion_actual'] == 1 else ("#D32F2F", "EXCEDIDO")
            else:
                if uso > 1.0: color, est = "#D32F2F", "SOBREPOBLADO"
                elif uso >= 0.9: color, est = "#FBC02D", "AL LÍMITE"
                else: color, est = "#2E7D32", "OK"
            
            # Nota adicional si hay fecha de parto
            parto_info = ""
            if pd.notna(row['fecha_parto']):
                parto_info = f"<br><span style='color:orange;'>⏳ Parto: {row['fecha_parto'].strftime('%d/%m')}</span>"

            st.markdown(f"""
            <div style="border:3px solid {color}; padding:10px; border-radius:10px; background:white; text-align:center; margin-bottom:10px;">
                <b>{row['corral']}</b><br><span style="color:{color}; font-size:10px;">● {est}</span><br>
                <span style="font-size:20px; font-weight:bold;">{int(row['poblacion_actual'])}</span>/{int(cap)}<br>
                <div style="font-size:9px; color:gray; border-top:1px solid #eee; margin-top:5px;">
                    {row['tipo_animal'] if row['poblacion_actual'] > 0 else 'Disponible'}{parto_info}<br>
                    {row['area_m2']:.1f}m² | {row['m2_por_animal']}m²/cab
                </div>
            </div>""", unsafe_allow_html=True)

def mostrar_configuracion():
    st.markdown("# ⚙️ Panel de Administración (Dueño)")

    with st.expander("⚽ Fichaje Inicial de Jugadoras (Carga Inicial)", expanded=True):
        df_c = lotes_logic.obtener_lista_chiqueros()
        if not df_c.empty:
            # 1. El Toggle debe estar FUERA del form para que la interfaz cambie al instante
            tienes_fecha = st.toggle("¿Hay fecha de monta?", value=True, key="toggle_monta")
            
            with st.form("form_fichaje_dueño", clear_on_submit=True):
                st.info("Usa este formulario para cargar las puercas que ya están en el rancho.")
                col_f1, col_f2 = st.columns(2)
                sel_corral = col_f1.selectbox("¿En qué corral están?", df_c['nombre'].tolist())
                etapa = col_f2.selectbox("Etapa Actual:", ["Semental", 
    "Pie de Cría", 
    "Gestación", 
    "Próxima a Parir", 
    "Lactante / Parida", 
    "Crías / Lechones", 
    "Desarrollo", 
    "Engorda", 
    "Desecho", 
    "Herniados"])
                
                c1, c2, c3 = st.columns(3)
                cantidad = c1.number_input("¿Cuántas son?", min_value=1, step=1)
                
                # 2. Lógica limpia para la fecha
                fecha_m = None
                if tienes_fecha:
                    fecha_m = c2.date_input("Fecha de Monta/Foto:", value=date.today())
                else:
                    c2.info("📅 Se registrará sin fecha (Sin conteo automático)")
                
                arete = c3.text_input("Arete (S/A):", value="S/A")
                notas = st.text_area("Historia Clínica / Notas:")
                
                if st.form_submit_button("💾 REGISTRAR E INICIAR CONTEO"):
                    id_c = df_c[df_c['nombre'] == sel_corral]['id'].values[0]
                    
                    # Llamada a la lógica
                    exito, f_parto = lotes_logic.registrar_fichaje_inicial(
                        int(id_c), etapa, cantidad, fecha_m, arete, 
                        st.session_state.usuario_nombre, notas
                    )
                    
                    if exito:
                        st.success("✅ Registro cargado exitosamente.")
                        if f_parto:
                            st.warning(f"📅 Parto estimado: {f_parto.strftime('%d/%m/%Y')}")
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ Error al guardar. Revisa la consola o la base de datos.")

    with st.expander("🏗️ Estructura: Nuevo Corral", expanded=False):
        c1, c2 = st.columns(2)
        nom = c1.text_input("Nombre del Corral:")
        tipo = c2.selectbox("Tipo de Uso:", ["Comunal", "Paridera", "Semental"])
        if tipo == "Comunal":
            m1, m2, m3 = st.columns(3)
            l = m1.number_input("Largo (m):", 0.1, value=4.0)
            a = m2.number_input("Ancho (m):", 0.1, value=4.0)
            cap = m3.number_input("Capacidad Max:", value=int(l * a))
        elif tipo == "Paridera": l, a, cap = 2.4, 1.8, 1
        else: l, a, cap = 3.0, 3.0, 1

        if st.button("🚀 Registrar Corral"):
            if nom and lotes_logic.guardar_nuevo_chiquero(nom, tipo, l, a, cap):
                st.toast(f"✅ {nom} registrado", icon='🏗️')
                time.sleep(0.5)
                st.rerun()

    st.markdown("---")
    st.subheader("⚠️ Mantenimiento Nuclear")
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        confirm_inv = st.text_input("Escribe 'BORRAR ANIMALES':", key="borrar_inv")
        if st.button("🗑️ Vaciar Corrales", disabled=confirm_inv != "BORRAR ANIMALES"):
            if lotes_logic.limpiar_solo_animales(): st.rerun()
    with c_m2:
        confirm_all = st.text_input("Escribe 'RESET TOTAL':", key="borrar_all")
        if st.button("☢️ Resetear Todo", disabled=confirm_all != "RESET TOTAL", type="primary"):
            if lotes_logic.resetear_datos_prueba(): st.rerun()

def mostrar_bitacora():
    st.title("📋 Historia Clínica y Bitácora")
    conn = db.get_connection()
    query = "SELECT h.fecha, c.nombre AS corral, h.tipo_animal, h.cantidad, h.tipo_evento, h.notas, h.id_usuario FROM historial_movimientos h JOIN chiqueros c ON h.id_chiquero_destino = c.id ORDER BY h.fecha DESC"
    df_h = pd.read_sql(query, conn)
    conn.close()

    if df_h.empty:
        st.info("Sin registros aún.")
        return

    for _, row in df_h.iterrows():
        nota = row['notas'] if row['notas'] else 'Sin nota'
        st.markdown(f"""<div style="border-left:5px solid #2E7D32; padding:10px; margin-bottom:10px; background-color:#f9f9f9;">
            <small>{row['fecha'].strftime('%d/%m/%Y %H:%M')}</small> | <b>{row['corral']}</b><br>
            <strong>{row['tipo_evento']}:</strong> {row['cantidad']} {row['tipo_animal']}<br>
            <i>"{nota}"</i><br><small>Por: {row['id_usuario']}</small></div>""", unsafe_allow_html=True)
    