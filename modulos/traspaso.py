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
    # Si viene desde tarjeta, guardar accion en estado persistente
    if "tab_presel" in st.session_state:
        st.session_state["accion_activa"] = st.session_state.pop("tab_presel")

    accion = st.session_state.get("accion_activa", None)

    titulos = {"muerte": "Registrar Muerte", "etapa": "Cambiar Etapa", "venta": "Registrar Venta", "parto": "Registrar Parto"}
    st.title(titulos.get(accion, "Traspasos"))
    st.write(f"Operador: **{st.session_state.usuario_nombre}** — {pd.Timestamp.now().strftime('%d/%m/%Y')}")

    if accion == "muerte":
        mostrar_registro_muerte()
        return
    elif accion == "etapa":
        mostrar_cambio_etapa()
        return
    elif accion == "venta":
        from modulos.ventas import mostrar_registro_venta
        mostrar_registro_venta()
        return
    elif accion == "parto":
        mostrar_registro_parto()
        return

    # Sin accion — wizard de traspasos directo
    _mostrar_alertas_celo()
    _mostrar_wizard_traspaso()


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

    if "traspaso_origen_fijo" not in st.session_state:
        if presel and presel in corrales_disponibles:
            st.session_state.traspaso_origen_fijo = presel
        else:
            st.session_state.traspaso_origen_fijo = None
    
    if st.session_state.traspaso_origen_fijo:
        origen_nombre = st.session_state.traspaso_origen_fijo
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
    # Enriquecer corrales_validos con zona desde BD
    from database import fetch_all as _fa2
    zonas_map = {r["id"]: r["zona"] for r in _fa2("SELECT id, zona FROM chiqueros")}
    corrales_validos = get_chiqueros_disponibles_para(tipo_destino)
    corrales_validos = [c for c in corrales_validos if c["id"] != id_origen]
    # Asignar zona a cada corral
    for c in corrales_validos:
        if not c.get("zona"):
            c["zona"] = zonas_map.get(c["id"], "")

    # Candados por zona — solo para encargados de zona
    rol = st.session_state.get("usuario_rol", "admin")
    if rol == "gestacion":
        corrales_validos = [c for c in corrales_validos if c.get("zona") == "Parideras"]
    elif rol == "parideras":
        if tipo_destino == "Pie de Cría":
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Gestacion"]
        elif tipo_destino == "Crías":
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Crecimiento"]
    elif rol == "crecimiento":
        if tipo_destino not in ("Pie de Cría", "Semental"):
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Crecimiento"]
        else:
            corrales_validos = [c for c in corrales_validos if c.get("zona") == "Gestacion"]

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
                st.session_state.pop("traspaso_origen_fijo", None)
                st.session_state.pop("accion_activa", None)
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
    if "muerte_corral_fijo" not in st.session_state:
        presel_m = st.session_state.pop("corral_presel", None)
        if presel_m and presel_m in corrales_m:
            st.session_state.muerte_corral_fijo = presel_m
        else:
            st.session_state.muerte_corral_fijo = None
    else:
        st.session_state.pop("corral_presel", None)

    if st.session_state.muerte_corral_fijo:
        corral_sel = st.session_state.muerte_corral_fijo
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

        st.cache_data.clear()
        st.session_state.pop("muerte_corral_fijo", None)
        st.session_state.pop("accion_activa", None)
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
    # Usar session_state para persistir el corral seleccionado entre reruns
    if "etapa_corral_fijo" not in st.session_state:
        presel_e = st.session_state.pop("corral_presel", None)
        if presel_e and presel_e in corrales_e:
            st.session_state.etapa_corral_fijo = presel_e
        else:
            st.session_state.etapa_corral_fijo = None
    else:
        st.session_state.pop("corral_presel", None)

    if st.session_state.etapa_corral_fijo:
        corral_sel = st.session_state.etapa_corral_fijo
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

        st.session_state.pop("etapa_corral_fijo", None)
        st.session_state.pop("accion_activa", None)
        st.success(f"{cantidad} animales cambiados de {etapa_actual} a {nueva_etapa} en {corral_sel}.")
        time.sleep(1.5)
        st.session_state.pagina = "mapa"
        st.rerun()


def mostrar_registro_parto():
    """Registra un parto: crias vivas al inventario, no logradas como muerte."""
    st.markdown("---")
    st.markdown("### 🍼 Registrar Parto")

    from modulos.lotes import get_inventario_completo, get_lote
    from database import execute
    import time

    df_inv = pd.DataFrame(get_inventario_completo())
    df_parideras = df_inv[
        (df_inv["poblacion_actual"] > 0) &
        (df_inv["tipo_animal"].str.contains("Pie de Cr", na=False))
    ]

    if df_parideras.empty:
        st.info("No hay Pie de Cría registrado en parideras.")
        return

    corrales_p = df_parideras["corral"].unique().tolist()
    presel_p = st.session_state.pop("corral_presel", None)

    if presel_p and presel_p in corrales_p:
        corral_sel = presel_p
        st.info(f"📍 **{corral_sel}**")
    else:
        corral_sel = st.selectbox("Paridera:", corrales_p, key="parto_corral")

    datos_corral = df_parideras[df_parideras["corral"] == corral_sel].iloc[0]
    id_corral = int(datos_corral["id"])

    st.markdown("---")
    col1, col2 = st.columns(2)
    crias_vivas = col1.number_input("Crías nacidas vivas:", min_value=0, step=1, key="parto_vivas")
    no_logradas = col2.number_input("No logradas:", min_value=0, step=1, key="parto_muertas")

    total_nacidos = crias_vivas + no_logradas
    if total_nacidos > 0:
        st.info(f"Total nacidos: {total_nacidos} | Vivos: {crias_vivas} | No logrados: {no_logradas}")

    if st.button("Registrar parto", type="primary", use_container_width=True, key="btn_parto"):
        if total_nacidos == 0:
            st.error("Registra al menos una cría.")
            return

        # Agregar crias vivas al inventario del corral
        if crias_vivas > 0:
            execute(
                """INSERT INTO lotes (id_chiquero, tipo_animal, poblacion_actual)
                   VALUES (%s, 'Crías', %s)
                   ON DUPLICATE KEY UPDATE
                   poblacion_actual = poblacion_actual + VALUES(poblacion_actual)""",
                (id_corral, crias_vivas)
            )
            execute(
                """INSERT INTO historial_movimientos
                   (id_chiquero_destino, tipo_animal, cantidad, tipo_evento, id_usuario, notas)
                   VALUES (%s, 'Crías', %s, 'PARTO', %s, %s)""",
                (id_corral, crias_vivas, st.session_state.usuario_nombre,
                 f"Parto en {corral_sel}: {crias_vivas} crías vivas")
            )

        # Registrar no logradas como muerte
        if no_logradas > 0:
            execute(
                """INSERT INTO historial_movimientos
                   (id_chiquero_destino, tipo_animal, cantidad, tipo_evento, id_usuario, notas)
                   VALUES (%s, 'Crías', %s, 'MUERTE', %s, %s)""",
                (id_corral, no_logradas, st.session_state.usuario_nombre,
                 f"Parto en {corral_sel}: {no_logradas} no logradas")
            )

        # Cambiar estado de la pie de cria a Parida
        execute(
            """UPDATE lotes SET estado_pie_cria = 'Parida'
               WHERE id_chiquero = %s AND tipo_animal = 'Pie de Cría'""",
            (id_corral,)
        )

        st.cache_data.clear()
        st.success(f"Parto registrado en {corral_sel}: {crias_vivas} crías vivas" +
                   (f", {no_logradas} no logradas" if no_logradas > 0 else ""))
        time.sleep(1.5)
        st.session_state.pop("accion_activa", None)
        st.session_state.pagina = "mapa"
        st.rerun()