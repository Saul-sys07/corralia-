"""
modulos/usuarios.py - Corralia v3
Gestion de usuarios. Solo Admin (Saul).
"""

import streamlit as st
import time
import pandas as pd
from database import fetch_all, execute

ROLES = {
    "admin":             "Administrador",
    "encargado_general": "Encargado General",
    "parideras":         "Parideras",
    "crecimiento":       "Crecimiento",
    "gestacion":         "Gestacion",
    "ayudante_general":  "Ayudante General",
}

def mostrar_usuarios():
    st.title("Usuarios")
    st.caption("Gestion de accesos — solo Admin")

    tab1, tab2 = st.tabs(["Usuarios activos", "Agregar usuario"])

    with tab1:
        usuarios = fetch_all("""
            SELECT id, nombre, rol, primer_acceso, activo,
                   ultimo_acceso, fecha_registro
            FROM usuarios ORDER BY fecha_registro
        """)

        if not usuarios:
            st.info("No hay usuarios registrados.")
        else:
            for u in usuarios:
                col1, col2, col3, col4 = st.columns([2, 2, 1, 2])
                col1.markdown(f"**{u['nombre']}**")
                col2.caption(ROLES.get(u['rol'], u['rol']))

                if u['primer_acceso']:
                    col3.warning("Pendiente")
                else:
                    col3.success("Activo")

                ultimo = u['ultimo_acceso']
                if ultimo:
                    col4.caption(f"Ultimo acceso: {ultimo.strftime('%d/%m/%Y %H:%M')}")
                else:
                    col4.caption("Nunca ha ingresado")

                # Opciones
                with st.expander(f"Opciones de {u['nombre']}", expanded=False):
                    c1, c2 = st.columns(2)

                    # Resetear PIN
                    if c1.button(f"Resetear PIN", key=f"reset_{u['id']}",
                                 use_container_width=True):
                        execute(
                            "UPDATE usuarios SET pin = %s, pin_temporal = %s, primer_acceso = 1 WHERE id = %s",
                            ("0000", "0000", u['id'])
                        )
                        st.success(f"PIN de {u['nombre']} reseteado a 0000. Debe crear uno nuevo al entrar.")
                        time.sleep(1)
                        st.rerun()

                    # Desactivar/Activar
                    if u['activo']:
                        if c2.button(f"Desactivar", key=f"desact_{u['id']}",
                                     use_container_width=True):
                            execute("UPDATE usuarios SET activo = 0 WHERE id = %s", (u['id'],))
                            st.warning(f"{u['nombre']} desactivado.")
                            time.sleep(1)
                            st.rerun()
                    else:
                        if c2.button(f"Reactivar", key=f"react_{u['id']}",
                                     use_container_width=True, type="primary"):
                            execute("UPDATE usuarios SET activo = 1 WHERE id = %s", (u['id'],))
                            st.success(f"{u['nombre']} reactivado.")
                            time.sleep(1)
                            st.rerun()

                st.divider()

    with tab2:
        st.subheader("Nuevo usuario")
        st.info("El usuario entrara con PIN temporal 0000 y creara su propio PIN en su primer acceso.")

        with st.form("form_nuevo_usuario", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre:")
            rol    = c2.selectbox("Rol / Zona:", list(ROLES.keys()),
                                  format_func=lambda x: ROLES[x])

            if st.form_submit_button("Crear usuario", type="primary",
                                     use_container_width=True):
                if not nombre:
                    st.error("El nombre es obligatorio.")
                else:
                    execute(
                        "INSERT INTO usuarios (nombre, pin, pin_temporal, rol, primer_acceso) VALUES (%s, '0000', '0000', %s, 1)",
                        (nombre, rol)
                    )
                    st.success(f"Usuario '{nombre}' creado. PIN temporal: 0000")
                    time.sleep(1)
                    st.rerun()