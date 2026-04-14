"""
modulos/checador.py - Corralia v3
Checador de entrada/salida para todos los trabajadores.
Admin (Saul) esta exento.
"""

import streamlit as st
import time
import os
from datetime import date, datetime
from database import fetch_all, fetch_one, execute


def ya_checo_hoy(usuario_id: int) -> bool:
    row = fetch_one(
        "SELECT id FROM asistencia WHERE usuario_id = %s AND DATE(fecha_entrada) = %s",
        (usuario_id, date.today())
    )
    return row is not None


def ya_registro_salida(usuario_id: int) -> bool:
    row = fetch_one(
        "SELECT id FROM asistencia WHERE usuario_id = %s AND DATE(fecha_entrada) = %s AND fecha_salida IS NOT NULL",
        (usuario_id, date.today())
    )
    return row is not None


def mostrar_checador_entrada():
    nombre     = st.session_state.usuario_nombre
    usuario_id = st.session_state.usuario_id
    hoy        = date.today()

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown(f"## Hola, **{nombre}** 👋")
        st.markdown(f"**{hoy.strftime('%d/%m/%Y')}**")
        st.markdown("---")
        st.info("Registra tu entrada para comenzar tu jornada.")

        # Camara solo se activa cuando el usuario presiona el boton
        if "camara_entrada_activa" not in st.session_state:
            st.session_state.camara_entrada_activa = False

        if not st.session_state.camara_entrada_activa:
            if st.button("Tomar foto de entrada", type="primary",
                         use_container_width=True):
                st.session_state.camara_entrada_activa = True
                st.rerun()
        else:
            foto = st.camera_input("Toma tu foto:")
            if foto:
                os.makedirs("fotos_asistencia", exist_ok=True)
                nombre_foto = f"fotos_asistencia/{nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_entrada.jpg"
                with open(nombre_foto, "wb") as f:
                    f.write(foto.getbuffer())
                execute(
                    "INSERT INTO asistencia (usuario_id, nombre, fecha_entrada, foto_entrada) VALUES (%s, %s, NOW(), %s)",
                    (usuario_id, nombre, nombre_foto)
                )
                st.session_state.camara_entrada_activa = False
                st.success(f"Entrada registrada a las {datetime.now().strftime('%H:%M')} — Bienvenido.")
                time.sleep(1.5)
                st.rerun()
            if st.button("Cancelar", key="cancel_cam_entrada"):
                st.session_state.camara_entrada_activa = False
                st.rerun()

        st.markdown("---")
        if st.button("Cerrar sesion", use_container_width=True):
            for key in ["autenticado","usuario_id","usuario_nombre","usuario_rol","pagina"]:
                st.session_state[key] = False if key == "autenticado" else ""
            st.rerun()


def mostrar_registro_salida():
    nombre     = st.session_state.usuario_nombre
    usuario_id = st.session_state.usuario_id
    hoy        = date.today()

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown(f"## Registrar salida")
        st.markdown(f"**{nombre}** — {hoy.strftime('%d/%m/%Y')}")
        st.markdown("---")

        registro = fetch_one(
            "SELECT * FROM asistencia WHERE usuario_id = %s AND DATE(fecha_entrada) = %s",
            (usuario_id, hoy)
        )

        if not registro:
            st.error("No hay registro de entrada hoy.")
            return

        entrada = registro["fecha_entrada"]
        st.info(f"Entrada registrada a las **{entrada.strftime('%H:%M')}**")

        if "camara_salida_activa" not in st.session_state:
            st.session_state.camara_salida_activa = False

        if not st.session_state.camara_salida_activa:
            if st.button("Tomar foto de salida", type="primary",
                         use_container_width=True):
                st.session_state.camara_salida_activa = True
                st.rerun()
        else:
            foto = st.camera_input("Toma tu foto:")
            if foto:
                os.makedirs("fotos_asistencia", exist_ok=True)
                nombre_foto = f"fotos_asistencia/{nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_salida.jpg"
                with open(nombre_foto, "wb") as f:
                    f.write(foto.getbuffer())
                execute(
                    "UPDATE asistencia SET fecha_salida = NOW(), foto_salida = %s WHERE id = %s",
                    (nombre_foto, registro["id"])
                )
                st.session_state.camara_salida_activa = False
                st.success(f"Salida registrada a las {datetime.now().strftime('%H:%M')}. Hasta manana.")
                time.sleep(1.5)
                st.session_state.pagina = "mapa"
                st.rerun()

            if st.button("Cancelar", use_container_width=True):
                st.session_state.camara_salida_activa = False
                st.session_state.pagina = "mapa"
                st.rerun()


def mostrar_checador():
    """Vista para ayudantes generales — solo entrada/salida."""
    nombre     = st.session_state.usuario_nombre
    usuario_id = st.session_state.usuario_id
    hoy        = date.today()

    st.markdown(f"## {nombre}")
    st.caption(hoy.strftime("%d/%m/%Y"))
    st.markdown("---")

    registro = fetch_one(
        "SELECT * FROM asistencia WHERE usuario_id = %s AND DATE(fecha_entrada) = %s",
        (usuario_id, hoy)
    )

    ya_salio = registro and registro.get("fecha_salida") is not None

    if registro and not ya_salio:
        entrada = registro["fecha_entrada"]
        st.success(f"Entrada registrada a las **{entrada.strftime('%H:%M')}**")
        st.markdown("---")
        st.markdown("### Registrar salida")
        if "camara_salida_ay" not in st.session_state:
            st.session_state.camara_salida_ay = False

        if not st.session_state.camara_salida_ay:
            if st.button("Tomar foto de salida", type="primary",
                         use_container_width=True):
                st.session_state.camara_salida_ay = True
                st.rerun()
        else:
            foto = st.camera_input("Toma tu foto:")
            if foto:
                os.makedirs("fotos_asistencia", exist_ok=True)
                nombre_foto = f"fotos_asistencia/{nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_salida.jpg"
                with open(nombre_foto, "wb") as f:
                    f.write(foto.getbuffer())
                execute(
                    "UPDATE asistencia SET fecha_salida = NOW(), foto_salida = %s WHERE id = %s",
                    (nombre_foto, registro["id"])
                )
                st.session_state.camara_salida_ay = False
                st.success(f"Salida registrada — {datetime.now().strftime('%H:%M')}. Hasta manana.")
                time.sleep(1.5)
                st.rerun()
    elif ya_salio:
        entrada = registro["fecha_entrada"]
        salida  = registro["fecha_salida"]
        st.success(f"Entrada: **{entrada.strftime('%H:%M')}**")
        st.success(f"Salida: **{salida.strftime('%H:%M')}**")
        st.info("Jornada completa. Hasta manana.")