"""
modulos/traspaso.py — Corralia v3
Wizard de 3 pasos para mover animales entre corrales.
Beyin lo usa en campo desde el celular.
"""

import streamlit as st
import time
import pandas as pd
from modulos.lotes import get_inventario_completo, mover_animales
from modulos.chiqueros import get_chiqueros_disponibles_para
from config import TIPOS_ANIMAL


def mostrar_traspaso():
    st.title("Traspasos")
    st.write(f"Operador: **{st.session_state.usuario_nombre}** — {pd.Timestamp.now().strftime('%d/%m/%Y')}")





    # Leer tab preseleccionado desde tarjeta del mapa
    tab_presel = st.session_state.get("tab_presel", None)

    # Si viene desde tarjeta, mostrar solo esa accion
    if tab_presel == "muerte":
        st.session_state.pop("tab_presel", None)
        mostrar_registro_muerte()
        return
    elif tab_presel == "etapa":
        st.session_state.pop("tab_presel", None)
        mostrar_cambio_etapa()
        return
    elif tab_presel == "venta":
        st.session_state.pop("tab_presel", None)
        from modulos.ventas import mostrar_registro_venta
        mostrar_registro_venta()
        return

    # Sin preseleccion — mostrar todos los tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Traspasos", "Registrar Muerte", "Cambiar Etapa", "Venta"])

    with tab1:
        _mostrar_alertas_celo()
        _mostrar_wizard_traspaso()

    with tab2:
        mostrar_registro_muerte()

    with tab3:
        mostrar_cambio_etapa()

    with tab4:
        from modulos.ventas import mostrar_registro_venta
        mostrar_registro_venta()


# Zonas permitidas como destino segun rol
DESTINOS_POR_ROL = {
    "gestacion":  ["Parideras"],
    "parideras":  ["Gestacion", "Crecimiento"],
    "crecimiento":["Crecimiento", "Gestacion"],
}

def _filtrar_destinos_por_rol(corrales: list, rol: str) -> list:
    """Filtra corrales destino segun zona del encargado."""
    zonas_permitidas = DESTINOS_POR_ROL.get(rol)
    if not zonas_permitidas:
        return corrales  # Admin y encargado_general ven todo
    from database import fetch_all
    corrales_zona = fetch_all(
        "SELECT nombre FROM chiqueros WHERE zona IN ({})".format(
            ",".join(["%s"] * len(zonas_permitidas))
        ),
        tuple(zonas_permitidas)
    )
    nombres_permitidos = {c["nombre"] for c in corrales_zona}
    return [c for c in corrales if c["nombre"] in nombres_permitidos]


def _mostrar_wizard_traspaso():







    st.markdown("---")

    # Inicializar carrito
    if "destinos_temp" not in st.session_state:
        st.session_state.destinos_temp = []

    # ── PASO 1: Origen ────────────────────────────────────────────────────────
    st.markdown("### 1. ¿De dónde salen?")
    df_inv = pd.DataFrame(get_inventario_completo())
    df_con_stock = df_inv[df_inv["poblacion_actual"] > 0]

    if df_con_stock.empty:
        st.info("No hay animales registrados. Ve a Configuración para registrar el inventario.")
        return

    # Si viene preseleccionado desde tarjeta del mapa
    rol = st.session_state.get("usuario_rol", "admin")
    ZONAS_DESTINO_POR_ROL = {
        "gestacion":  ["Parideras"],
        "parideras":  ["Gestacion", "Crecimiento"],
        "crecimiento":["Crecimiento", "Gestacion"],
    }
    zonas_destino_permitidas = ZONAS_DESTINO_POR_ROL.get(rol)  # None = sin restriccion

    # Filtrar corrales de origen segun zona del encargado
    from database import fetch_all as _fa
    if zonas_destino_permitidas and rol in ["gestacion","parideras","crecimiento"]:
        zona_origen = {"gestacion":"Gestacion","parideras":"Parideras","crecimiento":"Crecimiento"}.get(rol)
        ids_zona = [r["id"] for r in _fa("SELECT id FROM chiqueros WHERE zona = %s", (zona_origen,))]
        df_con_stock = df_con_stock[df_con_stock["id"].isin(ids_zona)]

    corrales_disponibles = df_con_stock["corral"].unique().tolist()
    presel = st.session_state.pop("corral_presel", None)

    if presel and presel in corrales_disponibles:
        # Viene desde tarjeta — origen bloqueado
        origen_nombre = presel
        st.info(f"📍 Origen: **{origen_nombre}**")
    else:
        origen_nombre = st.selectbox(
            "Corral de origen:",
            corrales_disponibles,
            key="origen_sel"
        )
    datos_origen = df_con_stock[df_con_stock["corral"] == origen_nombre].iloc[0]
    id_origen    = int(datos_origen["id"])

    # Tipos presentes en ese corral
    tipos_en_corral = [t.strip() for t in str(datos_origen["tipo_animal"]).split("/") if t.strip() and t.strip() != "VACÍO"]

    if not tipos_en_corral:
        st.warning("Este corral no tiene animales.")
        return

    # ── PASO 2: Qué se mueve ──────────────────────────────────────────────────
    st.markdown("### 2. ¿Qué se mueve?")
    col_tipo, col_cant = st.columns(2)

    tipo_a_mover = col_tipo.selectbox("Tipo de animal:", tipos_en_corral, key="tipo_sel")

    # Buscar población disponible de ese tipo específico
    from modulos.lotes import get_lote
    lote_sel = get_lote(id_origen, tipo_a_mover)
    disponible = int(lote_sel["poblacion_actual"]) if lote_sel else 0

    col_tipo.caption(f"Disponibles: **{disponible}** {tipo_a_mover}")

    cantidad = col_cant.number_input(
        "Cantidad a mover:",
        min_value=1,
        max_value=disponible,
        step=1,
        key="cant_sel"
    )

    # ── Cambio de etapa ───────────────────────────────────────────────────────
    st.markdown("### 3. ¿Avanzan de etapa o se quedan igual?")
    cambiar_etapa = st.toggle("Cambian de etapa en el destino", value=False, key="toggle_etapa")

    tipo_destino = tipo_a_mover
    if cambiar_etapa:
        idx_actual = TIPOS_ANIMAL.index(tipo_a_mover) if tipo_a_mover in TIPOS_ANIMAL else 0
        opciones_avance = TIPOS_ANIMAL[idx_actual:]
        tipo_destino = st.selectbox("Nueva etapa en destino:", opciones_avance, key="etapa_dest")

    # ── PASO 4: Destino ───────────────────────────────────────────────────────
    st.markdown("### 4. ¿A dónde van?")
    corrales_validos = get_chiqueros_disponibles_para(tipo_destino)
    corrales_validos = [c for c in corrales_validos if c["id"] != id_origen]

    # Candados por zona — solo para encargados de zona, no para admin ni encargado_general
    rol = st.session_state.get("usuario_rol", "admin")
    if rol == "gestacion":
        # Gestacion solo puede trasladar a Parideras
        corrales_validos = [c for c in corrales_validos if c.get("zona") == "Parideras"]
    elif rol == "parideras":
        # Parideras: Pie de Cria va a Gestacion, Crias van a Crecimiento
        if tipo_destino == "Pie de Cría":
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Gestacion"]
        elif tipo_destino == "Crías":
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Crecimiento"]
    elif rol == "crecimiento":
        # Crecimiento: entre corrales de Crecimiento, o a Gestacion si es sustituto
        if tipo_destino not in ("Pie de Cría", "Semental"):
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Crecimiento"]
        else:
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Gestacion"]
    # Aplicar candado por zona si es encargado de zona
    rol_actual = st.session_state.get("usuario_rol", "admin")
    corrales_validos = _filtrar_destinos_por_rol(corrales_validos, rol_actual)

    if not corrales_validos:
        st.warning(f"No hay corrales disponibles para {tipo_destino}.")
        return

    nombres_destino = [c["nombre"] for c in corrales_validos]
    col_dest, col_add = st.columns([3, 1])
    dest_nombre = col_dest.selectbox("Corral destino:", nombres_destino, key="dest_sel")
    id_destino  = next(c["id"] for c in corrales_validos if c["nombre"] == dest_nombre)

    # Info del destino seleccionado
    dest_info = next(c for c in corrales_validos if c["nombre"] == dest_nombre)
    col_dest.caption(
        f"Ocupación: {int(dest_info['poblacion_actual'])}/{dest_info['capacidad_max']} · "
        f"Estado: {dest_info['estado_capacidad'].upper()}"
    )

    if col_add.button("➕ Agregar", use_container_width=True, key="btn_add"):
        suma_actual = sum(d["cant"] for d in st.session_state.destinos_temp)
        if suma_actual + cantidad > disponible:
            st.error(f"No puedes mover más de {disponible} animales.")
        else:
            st.session_state.destinos_temp.append({
                "dest":       dest_nombre,
                "id_dest":    id_destino,
                "cant":       cantidad,
                "tipo_dest":  tipo_destino,
            })

    # ── Carrito ───────────────────────────────────────────────────────────────
    if st.session_state.destinos_temp:
        st.markdown("---")
        st.markdown("### Resumen del movimiento")
        suma_total = 0
        for item in st.session_state.destinos_temp:
            etapa_info = f" → **{item['tipo_dest']}**" if item["tipo_dest"] != tipo_a_mover else ""
            st.write(f"✅ **{item['cant']}** van a **{item['dest']}**{etapa_info}")
            suma_total += item["cant"]

        st.write(f"Total a mover: **{suma_total}** / {disponible} disponibles")

        col_conf, col_limpiar = st.columns(2)

        if suma_total == disponible:
            st.success("🎯 Lote completo distribuido — listo para confirmar")

        if col_conf.button(
            "🔓 APLICAR TRASPASO",
            use_container_width=True,
            type="primary",
            disabled=suma_total == 0
        ):
            errores = []
            for mov in st.session_state.destinos_temp:
                ok, msg = mover_animales(
                    id_chiquero_origen  = id_origen,
                    id_chiquero_destino = int(mov["id_dest"]),
                    tipo_animal         = tipo_a_mover,
                    cantidad            = int(mov["cant"]),
                    nuevo_tipo_destino  = mov["tipo_dest"] if mov["tipo_dest"] != tipo_a_mover else None,
                    usuario             = st.session_state.usuario_nombre,
                )
                if not ok:
                    errores.append(msg)

            if errores:
                for e in errores:
                    st.error(e)
            else:
                st.session_state.destinos_temp = []
                st.success("✅ Traspaso aplicado correctamente.")
                time.sleep(1.5)
                st.session_state.pagina = "mapa"
                st.rerun()

        if col_limpiar.button("🗑️ Limpiar", use_container_width=True):
            st.session_state.destinos_temp = []
            st.rerun()


def _mostrar_alertas_celo():
    """Muestra alertas de verificacion de celo pendientes a los 21 dias."""
    from modulos.movimientos import (
        get_verificaciones_celo_pendientes,
        confirmar_gestacion,
        cancelar_monta,
    )
    import time

    pendientes = get_verificaciones_celo_pendientes()
    if not pendientes:
        return

    st.warning(f"Verificacion de celo pendiente: {len(pendientes)} puerca(s)")

    for p in pendientes:
        dias = int(p["dias_desde_monta"])
        fecha_str = p["fecha_monta"].strftime("%d/%m/%Y") if p["fecha_monta"] else "?"
        parto_str = p["fecha_parto_estimada"].strftime("%d/%m/%Y") if p["fecha_parto_estimada"] else "?"
        arete = p["arete"] or "S/A"

        with st.container():
            st.markdown(f"""
            <div style="border:2px solid #F57F17; border-radius:10px;
                        padding:12px; background:#FFFDE7; margin-bottom:10px;">
                <b>{p['corral']}</b> — Arete: {arete}<br>
                <span style="font-size:12px;color:#555;">
                    Monta: {fecha_str} · Han pasado <b>{dias} dias</b><br>
                    Parto estimado si quedo gestante: {parto_str}
                </span>
            </div>
            """, unsafe_allow_html=True)

            col_si, col_no = st.columns(2)
            if col_si.button(
                "No regreso al celo",
                key=f"gestante_{p['id_chiquero']}",
                use_container_width=True,
                type="primary"
            ):
                ok, msg = confirmar_gestacion(
                    p["id_chiquero"],
                    st.session_state.usuario_nombre
                )
                if ok:
                    st.success(f"Gestacion confirmada — parto estimado {parto_str}")
                    time.sleep(1.5)
                    st.rerun()

            if col_no.button(
                "Si regreso al celo",
                key=f"cancela_{p['id_chiquero']}",
                use_container_width=True
            ):
                ok, msg = cancelar_monta(
                    p["id_chiquero"],
                    st.session_state.usuario_nombre
                )
                if ok:
                    st.info("Regresada a Disponible — monta cancelada")
                    time.sleep(1.5)
                    st.rerun()


def mostrar_registro_muerte():
    """Formulario para registrar muertes de animales."""
    st.markdown("---")
    st.markdown("### Registrar muerte")

    from modulos.lotes import get_inventario_completo, get_lote
    from database import execute, fetch_all
    import cloudinary
    import cloudinary.uploader
    from config import CLOUDINARY_CONFIG
    from datetime import datetime

    cloudinary.config(
        cloud_name=CLOUDINARY_CONFIG["cloud_name"],
        api_key=CLOUDINARY_CONFIG["api_key"],
        api_secret=CLOUDINARY_CONFIG["api_secret"],
    )

    CAUSAS = [
        "Hernia",
        "Aplastamiento", 
        "Enfermedad",
        "No logrado",
        "Causa desconocida",
        "Otro",
    ]

    df_inv = pd.DataFrame(get_inventario_completo())
    df_con_stock = df_inv[df_inv["poblacion_actual"] > 0]

    if df_con_stock.empty:
        st.info("No hay animales registrados.")
        return

    col1, col2 = st.columns(2)
    corrales_m = df_con_stock["corral"].unique().tolist()
    presel_m = st.session_state.pop("corral_presel", None) if "corral_presel" in st.session_state else None

    if presel_m and presel_m in corrales_m:
        corral_sel = presel_m
        col1.info(f"📍 **{corral_sel}**")
    else:
        corral_sel = col1.selectbox("Corral:", corrales_m, key="muerte_corral")

    datos_corral = df_con_stock[df_con_stock["corral"] == corral_sel].iloc[0]
    id_corral = int(datos_corral["id"])

    tipos_en_corral = [t.strip() for t in str(datos_corral["tipo_animal"]).split("/") 
                       if t.strip() and t.strip() != "VACIO"]

    tipo_animal = col2.selectbox(
        "Tipo de animal:",
        tipos_en_corral,
        key="muerte_tipo"
    )

    lote = get_lote(id_corral, tipo_animal)
    disponible = int(lote["poblacion_actual"]) if lote else 0
    col2.caption(f"Disponibles: {disponible}")

    col3, col4 = st.columns(2)
    cantidad = col3.number_input(
        "Cantidad muerta:",
        min_value=1,
        max_value=disponible,
        step=1,
        key="muerte_cantidad"
    )

    causa = col4.selectbox("Causa:", CAUSAS, key="muerte_causa")

    notas = ""
    if causa == "Otro":
        notas = st.text_input("Especifica la causa:", key="muerte_notas")

    # Foto opcional
    if "camara_muerte_activa" not in st.session_state:
        st.session_state.camara_muerte_activa = False

    foto_url = None
    if not st.session_state.camara_muerte_activa:
        if st.button("Tomar foto (opcional)", key="btn_cam_muerte"):
            st.session_state.camara_muerte_activa = True
            st.rerun()
    else:
        foto = st.camera_input("Foto de evidencia:", key="cam_muerte")
        if foto:
            nombre_foto = f"corralia/muertes/{st.session_state.usuario_nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            resultado = cloudinary.uploader.upload(
                foto.getbuffer(),
                public_id=nombre_foto,
                overwrite=True,
            )
            foto_url = resultado["secure_url"]
            st.session_state.camara_muerte_activa = False
            st.success("Foto guardada.")
            st.rerun()
        if st.button("Sin foto", key="btn_sin_foto_muerte"):
            st.session_state.camara_muerte_activa = False
            st.rerun()

    if st.button("Registrar muerte", type="primary", use_container_width=True, key="btn_muerte"):
        if disponible < cantidad:
            st.error(f"Solo hay {disponible} animales en ese corral.")
            return

        # Restar del inventario
        execute(
            """UPDATE lotes 
               SET poblacion_actual = GREATEST(poblacion_actual - %s, 0)
               WHERE id_chiquero = %s AND tipo_animal = %s""",
            (cantidad, id_corral, tipo_animal)
        )

        # Registrar en historial
        nota_final = f"Causa: {causa}"
        if notas:
            nota_final += f" — {notas}"

        execute(
            """INSERT INTO historial_movimientos 
               (id_chiquero_destino, tipo_animal, cantidad, tipo_evento, id_usuario, notas, foto_evidencia)
               VALUES (%s, %s, %s, 'MUERTE', %s, %s, %s)""",
            (id_corral, tipo_animal, cantidad,
             st.session_state.usuario_nombre, nota_final, foto_url)
        )

        st.success(f"{cantidad} {tipo_animal} registrados como muerte. Causa: {causa}")
        import time
        time.sleep(1.5)
        st.session_state.pagina = "mapa"
        st.rerun()


def mostrar_cambio_etapa():
    """
    Cambia la etapa de animales en un corral sin moverlos fisicamente.
    Ejemplo: Crias que crecieron y pasan a Destete en el mismo corral.
    """
    st.markdown("### Cambiar etapa sin mover animales")
    st.info("Usa esto cuando los animales avanzan de etapa pero se quedan en el mismo corral.")

    from modulos.lotes import get_inventario_completo, get_lote
    from database import execute
    from config import TIPOS_ANIMAL
    import time

    df_inv = pd.DataFrame(get_inventario_completo())
    df_con_stock = df_inv[df_inv["poblacion_actual"] > 0]

    if df_con_stock.empty:
        st.info("No hay animales registrados.")
        return

    col1, col2 = st.columns(2)
    corrales_e = df_con_stock["corral"].unique().tolist()
    presel_e = st.session_state.pop("corral_presel", None) if "corral_presel" in st.session_state else None

    if presel_e and presel_e in corrales_e:
        corral_sel = presel_e
        col1.info(f"📍 **{corral_sel}**")
    else:
        corral_sel = col1.selectbox("Corral:", corrales_e, key="etapa_corral")

    datos_corral = df_con_stock[df_con_stock["corral"] == corral_sel].iloc[0]
    id_corral = int(datos_corral["id"])

    tipos_en_corral = [t.strip() for t in str(datos_corral["tipo_animal"]).split("/")
                       if t.strip() and t.strip() != "VACIO"]

    etapa_actual = col2.selectbox(
        "Etapa actual:",
        tipos_en_corral,
        key="etapa_actual"
    )

    lote = get_lote(id_corral, etapa_actual)
    disponible = int(lote["poblacion_actual"]) if lote else 0
    col2.caption(f"Animales en esta etapa: {disponible}")

    # Etapas posibles hacia adelante
    if etapa_actual in TIPOS_ANIMAL:
        idx = TIPOS_ANIMAL.index(etapa_actual)
        etapas_destino = TIPOS_ANIMAL[idx + 1:] if idx + 1 < len(TIPOS_ANIMAL) else []
    else:
        etapas_destino = TIPOS_ANIMAL

    if not etapas_destino:
        st.warning("Esta etapa no tiene avance posible.")
        return

    col3, col4 = st.columns(2)
    nueva_etapa = col3.selectbox(
        "Nueva etapa:",
        etapas_destino,
        key="etapa_nueva"
    )

    cantidad = col4.number_input(
        "Cantidad:",
        min_value=1,
        max_value=disponible,
        step=1,
        key="etapa_cantidad"
    )

    notas = st.text_input("Notas (opcional):", key="etapa_notas")

    if st.button("Cambiar etapa", type="primary", use_container_width=True, key="btn_cambiar_etapa"):
        # Restar de etapa actual
        execute(
            """UPDATE lotes
               SET poblacion_actual = GREATEST(poblacion_actual - %s, 0)
               WHERE id_chiquero = %s AND tipo_animal = %s""",
            (cantidad, id_corral, etapa_actual)
        )

        # Agregar a nueva etapa en el mismo corral
        execute(
            """INSERT INTO lotes (id_chiquero, tipo_animal, poblacion_actual)
               VALUES (%s, %s, %s)
               ON DUPLICATE KEY UPDATE
               poblacion_actual = poblacion_actual + VALUES(poblacion_actual)""",
            (id_corral, nueva_etapa, cantidad)
        )

        # Historial
        nota_final = notas or f"Cambio de etapa: {etapa_actual} -> {nueva_etapa} sin traspaso fisico"
        execute(
            """INSERT INTO historial_movimientos
               (id_chiquero_destino, tipo_animal, cantidad, tipo_evento, id_usuario, notas)
               VALUES (%s, %s, %s, 'CAMBIO_ESTADO', %s, %s)""",
            (id_corral, nueva_etapa, cantidad,
             st.session_state.usuario_nombre, nota_final)
        )

        st.success(f"{cantidad} animales cambiados de {etapa_actual} a {nueva_etapa} en {corral_sel}.")
        time.sleep(1.5)
        st.session_state.pagina = "mapa"
        st.rerun()