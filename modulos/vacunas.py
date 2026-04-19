"""
modulos/vacunas.py - Corralia v3
Registro de vacunaciones y castraciones por lote.
"""

import streamlit as st
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from database import fetch_all, execute

def hora_mexico():
    return datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)

# Esquema de vacunas por tipo de animal
VACUNAS_POR_TIPO = {
    "Crías": [
        "E. coli y Clostridium (7-10 días)",
        "Circovirus PCV2 y Mycoplasma (14-21 días)",
        "Peste Porcina Clásica (45-60 días)",
    ],
    "Destete": [
        "Peste Porcina Clásica (45-60 días)",
        "Neumonía Actinobacillus (entrada cebo)",
    ],
    "Desarrollo": [
        "Neumonía Actinobacillus",
        "Peste Porcina Clásica",
    ],
    "Engorda": [
        "Neumonía Actinobacillus",
        "Peste Porcina Clásica",
    ],
    "Pie de Cría": [
        "Parvovirus + Leptospirosis + Erisipela (dosis 1 — primerizas)",
        "Parvovirus + Leptospirosis + Erisipela (dosis 2 — primerizas)",
        "Refuerzo PPL + Rinitis Atrófica (4-6 sem antes parto)",
        "Peste Porcina Clásica",
    ],
    "Semental": [
        "Parvovirus + Leptospirosis + Erisipela (semestral)",
        "Peste Porcina Clásica (semestral)",
    ],
}

EVENTOS_ESPECIALES = ["Castración (lechones 7-14 días)"]


def mostrar_vacunas():
    st.title("Vacunas y Castraciones")
    st.caption("Registro por lote — Beyin y encargado de zona")

    tab1, tab2 = st.tabs(["Registrar", "Historial"])

    with tab1:
        _registrar_vacuna()
    with tab2:
        _mostrar_historial()


def _registrar_vacuna():
    st.subheader("Registrar vacuna o castración")

    # Obtener corrales con animales
    corrales = fetch_all("""
        SELECT c.id, c.nombre, c.zona,
               GROUP_CONCAT(DISTINCT l.tipo_animal SEPARATOR ' / ') AS tipos,
               SUM(l.poblacion_actual) AS total
        FROM chiqueros c
        JOIN lotes l ON l.id_chiquero = c.id AND l.poblacion_actual > 0
        GROUP BY c.id
        ORDER BY c.zona, c.nombre
    """)

    if not corrales:
        st.info("No hay animales registrados.")
        return

    # Filtrar por zona segun rol
    rol = st.session_state.get("usuario_rol", "admin")
    zona_map = {"gestacion": "Gestacion", "parideras": "Parideras", "crecimiento": "Crecimiento"}
    zona_rol = zona_map.get(rol)
    if zona_rol:
        corrales = [c for c in corrales if c["zona"] == zona_rol]

    nombres_corrales = [f"{c['nombre']} — {c['tipos']} ({int(c['total'])} animales)" 
                        for c in corrales]
    mapa_corrales = {f"{c['nombre']} — {c['tipos']} ({int(c['total'])} animales)": c 
                     for c in corrales}

    sel_corral = st.radio("Corral:", nombres_corrales, key="vac_corral", horizontal=False)
    corral = mapa_corrales[sel_corral]

    # Tipos de animal en ese corral
    tipos = [t.strip() for t in str(corral["tipos"]).split("/") if t.strip()]
    tipo_animal = st.radio("Tipo de animal:", tipos, horizontal=True, key="vac_tipo")

    st.markdown("---")

    # Vacunas sugeridas + castración si aplica
    vacunas_sugeridas = VACUNAS_POR_TIPO.get(tipo_animal, [])
    if tipo_animal == "Crías":
        vacunas_sugeridas = vacunas_sugeridas + EVENTOS_ESPECIALES

    todas_opciones = vacunas_sugeridas + ["Otra (especificar)"]
    vacuna_sel = st.radio("Vacuna / Procedimiento:", todas_opciones,
                          horizontal=False, key="vac_tipo_vac")

    nombre_comercial = ""
    if vacuna_sel == "Otra (especificar)":
        vacuna_sel = st.text_input("Especifica:", key="vac_otra")
        nombre_comercial = st.text_input("Nombre comercial:", key="vac_nombre_com_otra")
    else:
        nombre_comercial = st.text_input("Nombre comercial (opcional):",
                                          key="vac_nombre_com",
                                          placeholder="Ej: Porcilis PCV, Calvenza, etc.")

    cantidad = st.number_input("Animales tratados:", min_value=1,
                                max_value=int(corral["total"]),
                                value=int(corral["total"]),
                                step=1, key="vac_cantidad")

    notas = st.text_input("Notas (opcional):", key="vac_notas")

    if st.button("Registrar", type="primary", use_container_width=True, key="btn_vac"):
        if not vacuna_sel:
            st.error("Especifica la vacuna o procedimiento.")
            return
        execute(
            """INSERT INTO vacunaciones
               (id_chiquero, tipo_animal, vacuna, nombre_comercial, cantidad, notas, usuario_id, fecha)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (corral["id"], tipo_animal, vacuna_sel, nombre_comercial or None,
             cantidad, notas or None, st.session_state.usuario_nombre, hora_mexico())
        )
        st.success(f"Registrado: {vacuna_sel} — {cantidad} {tipo_animal} en {corral['nombre']}")
        time.sleep(1.5)
        st.rerun()


def _mostrar_historial():
    st.subheader("Historial de vacunaciones")

    registros = fetch_all("""
        SELECT v.fecha, c.nombre AS corral, v.tipo_animal,
               v.vacuna, v.nombre_comercial, v.cantidad, v.notas, v.usuario_id
        FROM vacunaciones v
        JOIN chiqueros c ON c.id = v.id_chiquero
        ORDER BY v.fecha DESC
        LIMIT 50
    """)

    if not registros:
        st.info("Sin vacunaciones registradas.")
        return

    for r in registros:
        fecha = r["fecha"].strftime("%d/%m/%Y") if r["fecha"] else "?"
        nombre_com = f" ({r['nombre_comercial']})" if r["nombre_comercial"] else ""
        st.markdown(f"""
        <div style="border-left:4px solid #1976D2;padding:8px 12px;
                    background:#f9f9f9;border-radius:3px;margin-bottom:6px;">
            <small style="color:#888;">{fecha} — {r['usuario_id']} — {r['corral']}</small><br>
            <strong>{r['vacuna']}{nombre_com}</strong><br>
            {r['cantidad']} {r['tipo_animal']}
            {'<br><small><i>' + r['notas'] + '</i></small>' if r['notas'] else ''}
        </div>
        """, unsafe_allow_html=True)