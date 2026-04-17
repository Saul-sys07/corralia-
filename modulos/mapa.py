import streamlit as st
import pandas as pd
from modulos.chiqueros import get_alertas_capacidad
from modulos.movimientos import get_resumen_criticos
from database import fetch_all

ZONAS = [
    {"key": "Parideras",   "icono": "🐷"},
    {"key": "Gestacion",   "icono": "🔄"},
    {"key": "Crecimiento", "icono": "📈"},
]

ZONA_POR_ROL = {
    "parideras":  ["Parideras"],
    "gestacion":  ["Gestacion"],
    "crecimiento":["Crecimiento"],
}

def mostrar_mapa():
    rol = st.session_state.get("usuario_rol", "admin")
    if rol == "ayudante_general":
        from modulos.checador import mostrar_checador
        mostrar_checador()
        return

    col_titulo, col_refresh = st.columns([5, 1])
    col_titulo.title("Mapa de Corrales")
    if col_refresh.button("🔄 Actualizar", use_container_width=True):
        st.rerun()

    zonas_visibles = ZONA_POR_ROL.get(rol)

    criticos = get_resumen_criticos()
    msgs = []
    if criticos.get("Herniados", 0) > 0:
        msgs.append(f"🔴 {criticos['Herniados']} Herniados")
    if criticos.get("Desecho", 0) > 0:
        msgs.append(f"⚪ {criticos['Desecho']} en Desecho")
    if msgs:
        st.error("  ·  ".join(msgs))

    alertas_cap = get_alertas_capacidad()
    rojos     = [a for a in alertas_cap if a["nivel"] == "rojo"]
    amarillos = [a for a in alertas_cap if a["nivel"] == "amarillo"]
    if rojos:
        st.error("🚨 Excedidos: " + ", ".join(a["nombre"] for a in rojos))
    if amarillos:
        st.warning("⚠️ Al limite: " + ", ".join(a["nombre"] for a in amarillos))

    st.markdown("---")

    todos = fetch_all("""
        SELECT c.id, c.capacidad_max,
               IFNULL(SUM(l.poblacion_actual),0) AS pob
        FROM chiqueros c
        LEFT JOIN lotes l ON c.id = l.id_chiquero AND l.poblacion_actual > 0
        GROUP BY c.id
    """)
    total_animales = sum(int(r["pob"]) for r in todos)
    ocupados_total = sum(1 for r in todos if r["pob"] > 0)

    c1, c2, c3 = st.columns(3)
    c1.metric("Total animales", total_animales)
    c2.metric("Corrales ocupados", f"{ocupados_total} / {len(todos)}")
    c3.metric("Corrales vacios", len(todos) - ocupados_total)

    st.markdown("---")

    for zona in ZONAS:
        if zonas_visibles and zona["key"] not in zonas_visibles:
            continue
        _renderizar_zona(zona)


def _renderizar_zona(zona):
    sql = """
        SELECT
            c.id, c.nombre, c.tipo, c.zona,
            c.capacidad_max,
            IFNULL(c.area_m2, c.largo * c.ancho) AS area_m2,
            IFNULL(SUM(l.poblacion_actual), 0)   AS poblacion_actual,
            IFNULL(GROUP_CONCAT(
                DISTINCT l.tipo_animal ORDER BY l.tipo_animal SEPARATOR ' / '
            ), 'VACIO') AS tipo_animal,
            MAX(l.fecha_parto_estimada) AS fecha_parto,
            GROUP_CONCAT(
                DISTINCT l.estado_pie_cria ORDER BY l.estado_pie_cria SEPARATOR ', '
            ) AS estado_pie_cria
        FROM chiqueros c
        LEFT JOIN lotes l ON c.id = l.id_chiquero AND l.poblacion_actual > 0
        WHERE c.zona = %s
        GROUP BY c.id
        ORDER BY c.nombre
    """
    rows = fetch_all(sql, (zona["key"],))
    if not rows:
        return

    total    = len(rows)
    ocupados = sum(1 for r in rows if r["poblacion_actual"] > 0)
    animales = sum(r["poblacion_actual"] for r in rows)

    with st.expander(
        f"{zona['icono']} **{zona['key']}** — {ocupados}/{total} ocupados · {int(animales)} animales",
        expanded=True
    ):
        cols = st.columns(4)
        for i, row in enumerate(rows):
            with cols[i % 4]:
                _tarjeta(row)


def _tarjeta(row):
    cap  = max(int(row["capacidad_max"] or 1), 1)
    pob  = int(row["poblacion_actual"] or 0)
    area = float(row["area_m2"] or 0)
    pct  = pob / cap

    es_exclusivo = any(t in str(row.get("tipo_animal", ""))
                       for t in ["Semental", "Pie de Cr"])
    if pob == 0:
        color_hex   = "#9E9E9E"
        color_barra = "#E0E0E0"
        estado      = "VACÍO"
        emoji       = "⚫"
    elif es_exclusivo and pob <= cap:
        color_hex   = "#2E7D32"
        color_barra = "#4CAF50"
        estado      = "OCUPADO"
        emoji       = "🟢"
    elif pct >= 1.0:
        color_hex   = "#C62828"
        color_barra = "#EF5350"
        estado      = "EXCEDIDO"
        emoji       = "🔴"
    elif pct >= 0.9:
        color_hex   = "#F57F17"
        color_barra = "#FFC107"
        estado      = "AL LÍMITE"
        emoji       = "🟡"
    else:
        color_hex   = "#2E7D32"
        color_barra = "#4CAF50"
        estado      = "OK"
        emoji       = "🟢"

    pct_barra = min(pct * 100, 100)

    parto_html = ""
    if row.get("fecha_parto") and str(row["fecha_parto"]) not in ("None", "NaT", ""):
        try:
            parto_html = f"<div style='color:#E65100;font-size:11px;margin-top:4px;'>🗓 Parto: {row['fecha_parto'].strftime('%d/%m/%Y')}</div>"
        except Exception:
            pass

    estado_pc = ""
    val = row.get("estado_pie_cria")
    if val and str(val) not in ("None", "", "nan", "NaN"):
        estado_pc = f"<div style='color:#7B1FA2;font-size:11px;margin-top:2px;'>🔘 {val}</div>"

    area_str = f"{area:.1f} m²" if area > 0 else ""

    tipo_animal_raw = str(row.get("tipo_animal", ""))
    tipo_badge = tipo_animal_raw if (pob > 0 and tipo_animal_raw != "VACIO") else ""

    label_expander = f"{emoji} {row['nombre']}  —  {pob}/{cap}  {tipo_badge}"

    with st.expander(label_expander, expanded=False):
        st.markdown(f"""
        <div style="
            border: 2px solid {color_hex};
            border-radius: 12px;
            padding: 14px 12px 10px;
            background: #fafafa;
            text-align: center;
            margin-bottom: 10px;
        ">
            <div style="font-size:11px;color:{color_hex};font-weight:700;letter-spacing:1px;margin-bottom:6px;">
                {emoji} {estado}
            </div>
            <div style="font-size:36px;font-weight:800;color:#111;line-height:1;">
                {pob}
            </div>
            <div style="font-size:12px;color:#888;margin-bottom:10px;">
                de {cap} {'lugar' if cap == 1 else 'lugares'}
            </div>
            <div style="background:#e0e0e0;border-radius:20px;height:10px;overflow:hidden;margin:0 8px 8px;">
                <div style="
                    width:{pct_barra:.0f}%;
                    height:100%;
                    background:{color_barra};
                    border-radius:20px;
                "></div>
            </div>
            <div style="font-size:11px;color:#aaa;">{area_str}</div>
            <div style="font-size:12px;font-weight:600;color:#444;margin-top:4px;">{tipo_badge}</div>
            {estado_pc}
            {parto_html}
        </div>
        """, unsafe_allow_html=True)

        if pob > 0:
            tipos_en_corral = [t.strip() for t in tipo_animal_raw.split("/")
                               if t.strip() and t.strip() != "VACIO"]
            if len(tipos_en_corral) > 1:
                st.selectbox("Tipo:", tipos_en_corral, key=f"tipo_acc_{row['id']}")

            rol_actual = st.session_state.get("usuario_rol", "admin")
            mostrar_venta = rol_actual in ("admin", "encargado_general")

            # Fila 1 — Traslado y Muerte
            b1, b2 = st.columns(2)
            if b1.button("🔄 Traslado", key=f"tras_{row['id']}", use_container_width=True):
                st.session_state.pagina = "traspaso"
                st.session_state.corral_presel = row['nombre']
                st.rerun()
            if b2.button("💀 Muerte", key=f"muer_{row['id']}", use_container_width=True):
                st.session_state.pagina = "traspaso"
                st.session_state.tab_presel = "muerte"
                st.session_state.corral_presel = row['nombre']
                st.rerun()

            # Fila 2 — Etapa y Venta
            if mostrar_venta:
                b3, b4 = st.columns(2)
                if b3.button("📦 Etapa", key=f"etap_{row['id']}", use_container_width=True):
                    st.session_state.pagina = "traspaso"
                    st.session_state.tab_presel = "etapa"
                    st.session_state.corral_presel = row['nombre']
                    st.rerun()
                if b4.button("💰 Venta", key=f"vent_{row['id']}", use_container_width=True):
                    st.session_state.pagina = "traspaso"
                    st.session_state.tab_presel = "venta"
                    st.session_state.corral_presel = row['nombre']
                    st.rerun()
            else:
                b3, = st.columns(1)
                if b3.button("📦 Etapa", key=f"etap_{row['id']}", use_container_width=True):
                    st.session_state.pagina = "traspaso"
                    st.session_state.tab_presel = "etapa"
                    st.session_state.corral_presel = row['nombre']
                    st.rerun()