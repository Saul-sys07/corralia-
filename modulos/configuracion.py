"""
modulos/configuracion.py - Corralia v3
Panel de configuracion: registro de animales, CRUD de chiqueros.
Solo Admin (Saul).
"""

import streamlit as st
import time
import pandas as pd
from datetime import date
from modulos.lotes import registrar_animales
from modulos.chiqueros import get_chiqueros, crear_chiquero
from config import TIPOS_ANIMAL, ESTADOS_PIE_CRIA, TIPOS_CHIQUERO


def mostrar_configuracion():
    st.title("Configuracion")
    st.caption("Panel exclusivo de administracion - Saul")

    tab1, tab2 = st.tabs(["Registrar Animales", "Corrales"])

    with tab1:
        st.subheader("Registro de animales en corral")
        st.info("Usa este formulario para cargar el inventario actual del rancho.")

        chiqueros = get_chiqueros()
        if not chiqueros:
            st.warning("No hay corrales registrados. Crea uno primero en la pestana Corrales.")
            return

        nombres_chiqueros = {c["nombre"]: c for c in chiqueros}

        # Fuera del form para reaccion instantanea
        col1, col2 = st.columns(2)
        corral_sel  = col1.selectbox("Corral:", list(nombres_chiqueros.keys()), key="reg_corral")
        tipo_animal = col2.selectbox("Tipo de animal:", TIPOS_ANIMAL, key="reg_tipo")

        # Estado pie de cria aparece al instante
        estado_pc = None
        if tipo_animal == "Pie de Cría":
            estado_pc = st.selectbox("Estado reproductivo:", ESTADOS_PIE_CRIA, key="reg_estado")

        tiene_fecha = st.toggle("Hay fecha de monta", value=False, key="toggle_fecha")

        with st.form("form_registro", clear_on_submit=True):
            col3, col4, col5 = st.columns(3)
            cantidad    = col3.number_input("Cantidad:", min_value=1, step=1, value=1)
            fecha_monta = None
            if tiene_fecha:
                fecha_monta = col4.date_input("Fecha de monta:", value=date.today())
            arete = col5.text_input("Arete:", value="S/A")
            notas = st.text_area("Notas / Historia clinica:")

            if st.form_submit_button("Registrar", type="primary", use_container_width=True):
                ch = nombres_chiqueros[corral_sel]
                ok, msg, fecha_parto = registrar_animales(
                    id_chiquero     = ch["id"],
                    tipo_animal     = tipo_animal,
                    cantidad        = cantidad,
                    estado_pie_cria = estado_pc,
                    fecha_monta     = fecha_monta,
                    arete           = arete,
                    notas           = notas,
                    usuario         = st.session_state.usuario_nombre,
                )
                if ok:
                    st.success(msg)
                    if fecha_parto:
                        st.warning(f"Parto estimado: {fecha_parto.strftime('%d/%m/%Y')}")
                    time.sleep(1.2)
                    st.rerun()
                else:
                    if "Sin espacio" in msg or "espacio" in msg.lower():
                        st.warning(f"Advertencia de capacidad: {msg}")
                        st.session_state["forzar_datos"] = {
                            "id_chiquero": ch["id"],
                            "tipo_animal": tipo_animal,
                            "cantidad": cantidad,
                            "estado_pie_cria": estado_pc,
                            "fecha_monta": fecha_monta,
                            "arete": arete,
                            "notas": notas,
                        }
                    else:
                        st.error(msg)


        # Boton forzar registro fuera del form
        if st.session_state.get("forzar_datos"):
            d = st.session_state["forzar_datos"]
            st.error("Este corral excede los m2 recomendados — aparecera como EXCEDIDO en el mapa.")
            col_f1, col_f2 = st.columns(2)
            if col_f1.button("Registrar de todas formas", type="primary", key="btn_forzar", use_container_width=True):
                from database import upsert_lote, execute
                upsert_lote(d["id_chiquero"], d["tipo_animal"], d["cantidad"])
                execute(
                    "UPDATE lotes SET arete=%s, notas=%s WHERE id_chiquero=%s AND tipo_animal=%s",
                    (d["arete"], d["notas"], d["id_chiquero"], d["tipo_animal"])
                )
                st.session_state["forzar_datos"] = None
                st.success("Registrado. El corral aparece como EXCEDIDO en el mapa.")
                time.sleep(1.2)
                st.rerun()
            if col_f2.button("Cancelar", key="btn_cancelar_forzar", use_container_width=True):
                st.session_state["forzar_datos"] = None
                st.rerun()

    # ── Zona de mantenimiento ────────────────────────────────────────────────
    with st.expander("Mantenimiento de datos", expanded=False):
        st.warning("Esta accion elimina todos los animales registrados. Los corrales se conservan.")
        confirma = st.text_input("Escribe BORRAR para confirmar:", key="confirma_borrar")
        if st.button("Borrar todos los animales", type="primary", disabled=confirma != "BORRAR"):
            from database import execute
            execute("DELETE FROM lotes")
            execute("DELETE FROM historial_movimientos")
            execute("DELETE FROM alertas_sistema")
            st.success("Datos de animales eliminados. Los corrales siguen intactos.")
            time.sleep(1.5)
            st.rerun()

    with tab2:
        st.subheader("Corrales registrados")
        chiqueros = get_chiqueros()
        if chiqueros:
            df = pd.DataFrame(chiqueros)[["id","nombre","tipo","largo","ancho","capacidad_max","area_m2","poblacion_actual"]]
            df.columns = ["ID","Nombre","Tipo","Largo","Ancho","Cap. Max","m2","Poblacion"]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Sin corrales registrados.")

        st.markdown("---")
        st.subheader("Editar corral")

        if chiqueros:
            nombres_edit = {c["nombre"]: c for c in chiqueros}
            corral_editar = st.selectbox("Selecciona el corral a editar:", list(nombres_edit.keys()), key="sel_editar")
            ch_edit = nombres_edit[corral_editar]

            with st.form("form_editar_corral", clear_on_submit=False):
                e1, e2 = st.columns(2)
                nuevo_nombre = e1.text_input("Nombre:", value=ch_edit["nombre"])
                nuevo_tipo   = e2.selectbox("Tipo:", TIPOS_CHIQUERO,
                    index=TIPOS_CHIQUERO.index(ch_edit["tipo"]) if ch_edit["tipo"] in TIPOS_CHIQUERO else 0)

                zonas_list = ["Parideras", "Gestacion", "Crecimiento"]
                zona_actual = ch_edit.get("zona") or "Crecimiento"
                nueva_zona = st.selectbox("Zona:", zonas_list,
                    index=zonas_list.index(zona_actual) if zona_actual in zonas_list else 0)

                e3, e4 = st.columns(2)
                nuevo_largo = e3.number_input("Largo (m):", min_value=0.1,
                    value=float(ch_edit["largo"] or 1.0), step=0.1)
                nuevo_ancho = e4.number_input("Ancho (m):", min_value=0.1,
                    value=float(ch_edit["ancho"] or 1.0), step=0.1)
                nueva_cap = st.number_input("Capacidad max:", min_value=1,
                    value=int(ch_edit["capacidad_max"] or 1))

                if st.form_submit_button("Guardar cambios", type="primary", use_container_width=True):
                    from database import execute
                    execute("""
                        UPDATE chiqueros
                        SET nombre=%s, tipo=%s, zona=%s, largo=%s, ancho=%s, capacidad_max=%s
                        WHERE id=%s
                    """, (nuevo_nombre, nuevo_tipo, nueva_zona,
                          float(nuevo_largo), float(nuevo_ancho),
                          int(nueva_cap), ch_edit["id"]))
                    st.success(f"Corral actualizado correctamente.")
                    time.sleep(1)
                    st.rerun()

        st.markdown("---")
        st.subheader("Agregar nuevo corral")
        with st.form("form_nuevo_corral", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre:")
            tipo   = c2.selectbox("Tipo:", TIPOS_CHIQUERO)
            if tipo == "Comunal":
                m1, m2 = st.columns(2)
                largo  = m1.number_input("Largo (m):", min_value=0.1, value=4.0, step=0.1)
                ancho  = m2.number_input("Ancho (m):", min_value=0.1, value=4.0, step=0.1)
                cap    = int(largo * ancho / 0.82)
            elif tipo == "Paridera":
                largo, ancho, cap = 2.4, 1.8, 1
                st.info("Paridera estandar: 2.4m x 1.8m - capacidad 1")
            else:
                largo, ancho, cap = 3.0, 3.0, 1
                st.info("Semental estandar: 3.0m x 3.0m - capacidad 1")
            zonas_list = ["Parideras", "Gestacion", "Crecimiento"]
            # Sugerir zona segun tipo pero dejar que Saul confirme
            zona_sugerida = "Parideras" if tipo == "Paridera" else "Gestacion" if tipo == "Semental" else "Crecimiento"
            nueva_zona = st.selectbox("Zona en el mapa:", zonas_list,
                index=zonas_list.index(zona_sugerida), key="zona_nuevo")

            if st.form_submit_button("Crear corral", type="primary"):
                if not nombre:
                    st.error("El nombre es obligatorio.")
                else:
                    from database import execute
                    execute("""
                        INSERT INTO chiqueros (nombre, tipo, zona, largo, ancho, capacidad_max)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (nombre, tipo, nueva_zona, float(largo), float(ancho), int(cap)))
                    st.success(f"Corral '{nombre}' creado en zona {nueva_zona}.")
                    time.sleep(1)
                    st.rerun()