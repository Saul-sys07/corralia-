import streamlit as st
from datetime import date
import time
import modulos.lotes as lotes_logic  
from streamlit_autorefresh import st_autorefresh

def mostrar_interfaz_campo():
    st_autorefresh(interval=30000, key="beyin_refresh")
    st.markdown("# 📲 Control de Traspasos")
    st.write(f"Operador: **{st.session_state.usuario_nombre}** | {date.today().strftime('%d/%m/%Y')}")
    st.markdown("---")

    # 1. CARGA DE DATOS
    df_inv = lotes_logic.obtener_inventario_lotes()
    corrales_con_stock = df_inv[df_inv['poblacion_actual'] > 0]
    
    if not corrales_con_stock.empty:
        # --- PASO 1: SELECCIONAR CORRAL ---
        origen_nombre = st.selectbox("1. ¿De qué corral salen?", corrales_con_stock['corral'].unique().tolist())
        
        # --- PASO 2: SELECCIONAR ETAPA ---
        etapas_en_corral = corrales_con_stock[corrales_con_stock['corral'] == origen_nombre]
        opciones_etapa = etapas_en_corral['tipo_animal'].tolist()
        etapa_a_mover = st.selectbox("2. ¿Qué etapa vas a mover?", opciones_etapa)
        
        # Datos de la etapa seleccionada
        datos_sel = etapas_en_corral[etapas_en_corral['tipo_animal'] == etapa_a_mover].iloc[0]
        id_origen = int(datos_sel['id']) 
        total_disponible = int(datos_sel['poblacion_actual'])
        
        st.warning(f"📍 Hay **{total_disponible}** {etapa_a_mover} en este corral.")

        # --- PASO 3: CARRITO DE DESTINOS ---
        if 'destinos_temp' not in st.session_state:
            st.session_state.destinos_temp = []

        st.markdown("### 3. ¿A dónde van?")
        c_dest, c_cant = st.columns([2, 1])
        
        df_c = lotes_logic.obtener_lista_chiqueros()
        dest_opciones = df_c[df_c['nombre'] != origen_nombre]['nombre'].tolist()
        
        nuevo_dest = c_dest.selectbox("Seleccionar Destino:", dest_opciones)
        nueva_cant = c_cant.number_input("Cantidad:", min_value=1, max_value=total_disponible, step=1)

        if st.button("➕ Agregar al movimiento"):
            suma_actual = sum(d['cant'] for d in st.session_state.destinos_temp)
            if suma_actual + nueva_cant <= total_disponible:
                id_d = df_c[df_c['nombre'] == nuevo_dest]['id'].values[0]
                st.session_state.destinos_temp.append({
                    "dest": nuevo_dest, 
                    "cant": nueva_cant, 
                    "id_dest": id_d
                })
            else:
                st.error("No puedes mover más de lo que hay.")

        # --- PASO 4: CONFIRMACIÓN ---
        st.markdown("---")
        suma_u = 0
        for item in st.session_state.destinos_temp:
            st.write(f"✅ {item['cant']} van a **{item['dest']}**")
            suma_u += item['cant']

        if suma_u == total_disponible:
            st.success("🎯 ¡Lote completo ubicado! Listo para confirmar.")
            if st.button("🔓 APLICAR TRASPASO TOTAL", use_container_width=True):
                for mov in st.session_state.destinos_temp:
                    lotes_logic.mover_etapa_de_corral(
                        id_chiquero_origen=id_origen, 
                        id_chiquero_destino=int(mov['id_dest']),
                        tipo_animal=etapa_a_mover,
                        cantidad=int(mov['cant']),
                        usuario=st.session_state.usuario_nombre
                    )
                
                st.session_state.destinos_temp = []
                st.success("🔥 ¡Movimiento aplicado con éxito!")
                time.sleep(1.5)
                st.rerun()
        
        elif suma_u > 0:
            st.info(f"Faltan ubicar **{total_disponible - suma_u}** animales.")

        if st.button("🗑️ Limpiar lista", type="secondary"):
            st.session_state.destinos_temp = []
            st.rerun()

    else:
        st.info("No hay animales registrados. Registra en el Panel de Admin.")

    st.markdown("---")
    if st.sidebar.button("📴 Cerrar Sesión", key="logout_simple"):
        st.session_state.autenticado = False
        st.rerun()