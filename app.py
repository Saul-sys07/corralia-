"""
app.py - Corralia v3
Punto de entrada. Login desde base de datos, primer acceso con PIN propio,
y routing de paginas segun rol.
"""

import streamlit as st
import time

try:
    from database import fetch_one, execute, test_connection
except Exception as e:
    st.error(f"Error importando database: {e}")
    st.stop()

try:
    from config import DB_CONFIG
except Exception as e:
    st.error(f"Error importando config: {e}")
    st.stop()

st.set_page_config(
    page_title="Corralia v3",
    page_icon="🐖",
    layout="wide",
    initial_sidebar_state="expanded",
)

def _init_session():
    defaults = {
        "autenticado": False,
        "usuario_id": None,
        "usuario_nombre": "",
        "usuario_rol": "",
        "pagina": "mapa",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()

def _buscar_usuario(pin: str):
    return fetch_one("SELECT * FROM usuarios WHERE pin = %s AND activo = 1", (pin,))

def _es_primer_acceso(usuario: dict) -> bool:
    return bool(usuario.get("primer_acceso"))

def _activar_usuario(usuario_id: int, nuevo_pin: str):
    execute(
        "UPDATE usuarios SET pin = %s, pin_temporal = NULL, primer_acceso = 0 WHERE id = %s",
        (nuevo_pin, usuario_id)
    )

def _registrar_acceso(usuario_id: int):
    execute(
        "UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = %s",
        (usuario_id,)
    )

def mostrar_login():
    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("## 🐖 Corralia v3")
        st.markdown("**Rancho Yanez — Atlacomulco, Edo. Mex.**")
        st.markdown("---")
        pin = st.text_input("PIN de acceso:", type="password",
                            placeholder="••••", autocomplete="off")
        if st.button("Ingresar", use_container_width=True, type="primary"):
            if not pin:
                st.error("Ingresa tu PIN.")
                return
            usuario = _buscar_usuario(pin)
            if not usuario:
                st.error("PIN incorrecto.")
                return
            if _es_primer_acceso(usuario):
                st.session_state["activar_usuario"] = usuario
                st.rerun()
            else:
                _registrar_acceso(usuario["id"])
                st.session_state.autenticado    = True
                st.session_state.usuario_id     = usuario["id"]
                st.session_state.usuario_nombre = usuario["nombre"]
                st.session_state.usuario_rol    = usuario["rol"]
                st.session_state.pagina         = "mapa"
                st.rerun()

def mostrar_primer_acceso():
    usuario = st.session_state.get("activar_usuario")
    if not usuario:
        st.session_state.pop("activar_usuario", None)
        st.rerun()
        return

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("## 🐖 Bienvenido a Corralia")
        st.markdown(f"Hola **{usuario['nombre']}** — es tu primer acceso.")
        st.info("Crea tu PIN personal. Solo tu lo vas a saber — si lo compartes y pasa algo, el sistema registra tu nombre.")
        st.markdown("---")

        nuevo_pin    = st.text_input("Crea tu PIN personal:", type="password",
                                     placeholder="Minimo 4 digitos", autocomplete="off")
        confirma_pin = st.text_input("Confirma tu PIN:", type="password",
                                     placeholder="Repite tu PIN", autocomplete="off")

        zonas_disponibles = {
            "parideras":         "Parideras",
            "crecimiento":       "Crecimiento",
            "gestacion":         "Gestacion",
            "encargado_general": "Encargado General",
            "admin":             "Administrador",
        }
        zona_actual = usuario.get("rol", "crecimiento")
        zona_label  = zonas_disponibles.get(zona_actual, zona_actual)
        st.markdown(f"**Tu zona asignada:** {zona_label}")

        if st.button("Activar mi acceso", type="primary", use_container_width=True):
            if not nuevo_pin or len(nuevo_pin) < 4:
                st.error("El PIN debe tener al menos 4 digitos.")
                return
            if nuevo_pin != confirma_pin:
                st.error("Los PINes no coinciden.")
                return
            existente = fetch_one("SELECT id FROM usuarios WHERE pin = %s AND id != %s",
                                  (nuevo_pin, usuario["id"]))
            if existente:
                st.error("Ese PIN ya lo usa otra persona. Elige otro.")
                return

            _activar_usuario(usuario["id"], nuevo_pin)
            _registrar_acceso(usuario["id"])
            st.session_state.pop("activar_usuario", None)
            st.session_state.autenticado    = True
            st.session_state.usuario_id     = usuario["id"]
            st.session_state.usuario_nombre = usuario["nombre"]
            st.session_state.usuario_rol    = usuario["rol"]
            st.session_state.pagina         = "mapa"
            st.success("Acceso activado. Bienvenido.")
            time.sleep(1)
            st.rerun()

        if st.button("Cancelar", use_container_width=True):
            st.session_state.pop("activar_usuario", None)
            st.rerun()

def mostrar_sidebar():
    rol = st.session_state.usuario_rol

    with st.sidebar:
        st.markdown("### 🐖 Corralia v3")
        st.markdown(f"**{st.session_state.usuario_nombre}**")
        st.caption(_label_rol(rol))

        ok, _ = test_connection()
        if ok:
            st.success("DB conectada", icon="✅")
        else:
            st.error("Sin conexion DB", icon="❌")

        st.markdown("---")
        st.markdown("**Navegacion**")

        if st.button("🗺️ Mapa de corrales", use_container_width=True):
            st.session_state.pagina = "mapa"
            st.rerun()

        # Traspasos solo para Admin y Encargado General
        # Encargados de zona usan los botones de las tarjetas del mapa
        if rol in ("admin", "encargado_general"):
            if st.button("🔄 Traspasos", use_container_width=True):
                st.session_state.pagina = "traspaso"
                st.rerun()

        if rol == "admin":
            if st.button("📊 Reportes", use_container_width=True):
                st.session_state.pagina = "reportes"
                st.rerun()
            if st.button("⚙️ Configuracion", use_container_width=True):
                st.session_state.pagina = "configuracion"
                st.rerun()
            if st.button("👥 Usuarios", use_container_width=True):
                st.session_state.pagina = "usuarios"
                st.rerun()
            if st.button("💰 Ventas", use_container_width=True):
                st.session_state.pagina = "ventas"
                st.rerun()

        st.markdown("---")

        if rol != "admin":
            from modulos.checador import ya_checo_hoy, ya_registro_salida
            if ya_checo_hoy(st.session_state.usuario_id):
                if not ya_registro_salida(st.session_state.usuario_id):
                    if st.button("🕐 Registrar salida", use_container_width=True, type="primary"):
                        st.session_state.pagina = "salida"
                        st.rerun()
                else:
                    st.success("Salida registrada hoy", icon="✅")

        if st.button("🚪 Cerrar sesion", use_container_width=True):
            for key in ["autenticado","usuario_id","usuario_nombre","usuario_rol","pagina"]:
                st.session_state[key] = False if key == "autenticado" else ""
            st.session_state.pagina = "mapa"
            st.rerun()

def _label_rol(rol: str) -> str:
    labels = {
        "admin":             "Administrador",
        "encargado_general": "Encargado General",
        "parideras":         "Encargado Parideras",
        "crecimiento":       "Encargado Crecimiento",
        "gestacion":         "Encargado Gestacion",
        "ayudante_general":  "Ayudante General",
    }
    return labels.get(rol, rol)

def routear_pagina():
    rol    = st.session_state.usuario_rol
    pagina = st.session_state.pagina

    if pagina == "mapa":
        from modulos.mapa import mostrar_mapa
        mostrar_mapa()

    elif pagina == "traspaso":
        if rol not in ("admin", "encargado_general", "parideras", "crecimiento", "gestacion"):
            st.error("Acceso restringido.")
            return
        # Boton regresar al mapa
        if st.button("← Regresar al mapa"):
            st.session_state.pagina = "mapa"
            st.session_state.pop("corral_presel", None)
            st.session_state.pop("tab_presel", None)
            st.rerun()
        from modulos.traspaso import mostrar_traspaso
        mostrar_traspaso()

    elif pagina == "reportes":
        if rol != "admin":
            st.error("Acceso restringido.")
            return
        from modulos.reportes import mostrar_reportes
        mostrar_reportes()

    elif pagina == "configuracion":
        if rol != "admin":
            st.error("Acceso restringido.")
            return
        from modulos.configuracion import mostrar_configuracion
        mostrar_configuracion()

    elif pagina == "usuarios":
        if rol != "admin":
            st.error("Acceso restringido.")
            return
        from modulos.usuarios import mostrar_usuarios
        mostrar_usuarios()

    elif pagina == "ventas":
        if rol != "admin":
            st.error("Acceso restringido.")
            return
        if st.button("← Regresar al mapa"):
            st.session_state.pagina = "mapa"
            st.rerun()
        from modulos.ventas import mostrar_historial_ventas
        mostrar_historial_ventas()

    elif pagina == "salida":
        from modulos.checador import mostrar_registro_salida
        mostrar_registro_salida()

def main():
    if "activar_usuario" in st.session_state and st.session_state["activar_usuario"]:
        mostrar_primer_acceso()
        return

    if not st.session_state.autenticado:
        mostrar_login()
        return

    mostrar_sidebar()

    if st.session_state.usuario_rol != "admin":
        from modulos.checador import ya_checo_hoy
        if not ya_checo_hoy(st.session_state.usuario_id):
            from modulos.checador import mostrar_checador_entrada
            mostrar_checador_entrada()
            return

    routear_pagina()

if __name__ == "__main__":
    main()