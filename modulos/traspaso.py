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

    # Alertas de verificacion de celo
    _mostrar_alertas_celo()

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

    origen_nombre = st.selectbox(
        "Corral de origen:",
        df_con_stock["corral"].unique().tolist(),
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