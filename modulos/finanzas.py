"""
modulos/finanzas.py - Corralia v3
Registro de depósitos del papá y sueldos semanales.
"""

import streamlit as st
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from database import fetch_all, execute, fetch_one

def hora_mexico():
    return datetime.now(ZoneInfo("America/Mexico_City")).replace(tzinfo=None)


def mostrar_finanzas():
    st.title("Finanzas")
    st.caption("Depósitos, sueldos y resumen — solo Admin")

    tab1, tab2, tab3, tab4 = st.tabs(["Depósitos", "Nómina", "Config. Sueldos", "Resumen"])

    with tab1:
        _registrar_deposito()
    with tab2:
        _registrar_nomina()
    with tab3:
        _configurar_sueldos()
    with tab4:
        _mostrar_resumen()


def _registrar_deposito():
    st.subheader("Registrar depósito")
    st.caption("Dinero que manda el papá a Beyin")

    monto = st.number_input("Monto ($):", min_value=0.0, step=100.0, key="dep_monto")
    notas = st.text_input("Notas (opcional):", key="dep_notas", 
                           placeholder="Ej: Para compra de alimento semana 3")

    if st.button("Registrar depósito", type="primary", use_container_width=True, key="btn_dep"):
        if monto <= 0:
            st.error("El monto debe ser mayor a $0")
            return
        execute(
            """INSERT INTO finanzas (tipo, concepto, monto, notas, usuario_id, fecha)
               VALUES ('deposito', 'Depósito papá', %s, %s, %s, %s)""",
            (monto, notas, st.session_state.usuario_nombre, hora_mexico())
        )
        st.success(f"Depósito registrado: ${monto:,.2f}")
        time.sleep(1)
        st.rerun()

    # Historial de depósitos
    st.markdown("---")
    st.markdown("**Depósitos recientes:**")
    depositos = fetch_all("""
        SELECT fecha, monto, notas, usuario_id FROM finanzas
        WHERE tipo = 'deposito'
        ORDER BY fecha DESC LIMIT 10
    """)
    if not depositos:
        st.info("Sin depósitos registrados.")
    else:
        total = sum(d["monto"] for d in depositos)
        st.metric("Total depositado", f"${total:,.2f}")
        for d in depositos:
            fecha = d["fecha"].strftime("%d/%m/%Y") if d["fecha"] else "?"
            st.markdown(f"""
            <div style="border-left:4px solid #1976D2;padding:6px 12px;
                        background:#f9f9f9;border-radius:3px;margin-bottom:4px;">
                <strong>${d['monto']:,.2f}</strong> — {fecha}
                {'<br><small><i>' + d['notas'] + '</i></small>' if d['notas'] else ''}
            </div>
            """, unsafe_allow_html=True)


def _configurar_sueldos():
    """Solo Saul — configura el sueldo diario de cada trabajador."""
    st.subheader("Configuración de sueldos")
    st.caption("Solo visible para el administrador")

    trabajadores = fetch_all("""
        SELECT id, nombre, rol, sueldo_diario FROM usuarios
        WHERE activo = 1 AND rol != 'admin'
        ORDER BY nombre
    """)

    if not trabajadores:
        st.info("Sin trabajadores registrados.")
        return

    for t in trabajadores:
        col1, col2, col3 = st.columns([3, 2, 1])
        col1.markdown(f"**{t['nombre']}** — {t['rol']}")
        nuevo_sueldo = col2.number_input(
            "Sueldo diario ($):",
            min_value=0.0,
            value=float(t["sueldo_diario"] or 0),
            step=50.0,
            key=f"sue_cfg_{t['id']}"
        )
        if col3.button("💾", key=f"btn_sue_{t['id']}", help="Guardar"):
            execute(
                "UPDATE usuarios SET sueldo_diario = %s WHERE id = %s",
                (nuevo_sueldo, t["id"])
            )
            st.success(f"Sueldo de {t['nombre']} actualizado: ${nuevo_sueldo:,.2f}/día")
            time.sleep(1)
            st.rerun()


def _registrar_nomina():
    """Calcula automáticamente la nómina basada en asistencias del checador."""
    st.subheader("Nómina semanal")
    st.caption("Basada en días trabajados según el checador")

    from datetime import date, timedelta

    # Semana actual — lunes a domingo
    hoy = date.today()
    lunes = hoy - timedelta(days=hoy.weekday())
    domingo = lunes + timedelta(days=6)

    st.info(f"Semana: {lunes.strftime('%d/%m/%Y')} al {domingo.strftime('%d/%m/%Y')}")

    # Banner viernes
    if hoy.weekday() == 4:  # Viernes
        st.warning("⚠️ Hoy es viernes — verifica asistencias antes de pagar sueldos")

    # Calcular dias trabajados por trabajador esta semana
    asistencias = fetch_all("""
        SELECT u.id, u.nombre, u.sueldo_diario,
               COUNT(DISTINCT DATE(a.fecha_entrada)) AS dias_trabajados
        FROM usuarios u
        LEFT JOIN asistencia a ON a.usuario_id = u.id
            AND DATE(a.fecha_entrada) BETWEEN %s AND %s
        WHERE u.activo = 1 AND u.rol != 'admin'
        GROUP BY u.id
        ORDER BY u.nombre
    """, (lunes, domingo))

    if not asistencias:
        st.info("Sin trabajadores registrados.")
        return

    st.markdown("**Resumen de la semana:**")
    total_nomina = 0

    if "carrito_nomina" not in st.session_state:
        st.session_state.carrito_nomina = []
        # Pre-cargar con cálculo automático
        for a in asistencias:
            sueldo = float(a["sueldo_diario"] or 0)
            dias = int(a["dias_trabajados"] or 0)
            monto = sueldo * dias
            st.session_state.carrito_nomina.append({
                "nombre": a["nombre"],
                "dias": dias,
                "sueldo_diario": sueldo,
                "monto": monto
            })

    for i, item in enumerate(st.session_state.carrito_nomina):
        col1, col2, col3 = st.columns([3, 2, 2])
        col1.markdown(f"**{item['nombre']}** — {item['dias']} días × ${item['sueldo_diario']:,.2f}/día")
        # Permitir ajuste manual del monto
        monto_ajustado = col2.number_input(
            "Monto ($):",
            min_value=0.0,
            value=float(item["monto"]),
            step=50.0,
            key=f"nom_{i}"
        )
        st.session_state.carrito_nomina[i]["monto"] = monto_ajustado
        col3.metric("", f"${monto_ajustado:,.2f}")
        total_nomina += monto_ajustado

    st.markdown("---")
    st.metric("Total nómina", f"${total_nomina:,.2f}")

    col_conf, col_reset = st.columns(2)
    if col_conf.button("✅ Confirmar nómina", type="primary",
                       use_container_width=True, key="btn_conf_nom"):
        fecha = hora_mexico()
        usuario = st.session_state.usuario_nombre
        for item in st.session_state.carrito_nomina:
            if item["monto"] > 0:
                execute(
                    """INSERT INTO finanzas (tipo, concepto, monto, notas, usuario_id, fecha)
                       VALUES ('sueldo', %s, %s, %s, %s, %s)""",
                    (f"Sueldo {item['nombre']}",
                     item["monto"],
                     f"{item['dias']} días trabajados — semana {lunes.strftime('%d/%m/%Y')}",
                     usuario, fecha)
                )
        st.session_state.carrito_nomina = []
        st.success(f"Nómina registrada — Total: ${total_nomina:,.2f}")
        time.sleep(1.5)
        st.rerun()

    if col_reset.button("🔄 Recalcular", use_container_width=True, key="btn_reset_nom"):
        st.session_state.carrito_nomina = []
        st.rerun()


def _mostrar_resumen():
    st.subheader("Resumen financiero")

    # Depósitos
    dep = fetch_one("SELECT IFNULL(SUM(monto),0) AS total FROM finanzas WHERE tipo='deposito'")
    total_depositos = float(dep["total"]) if dep else 0

    # Sueldos
    sue = fetch_one("SELECT IFNULL(SUM(monto),0) AS total FROM finanzas WHERE tipo='sueldo'")
    total_sueldos = float(sue["total"]) if sue else 0

    # Ventas
    ven = fetch_one("SELECT IFNULL(SUM(total_rancho),0) AS total FROM ventas")
    total_ventas = float(ven["total"]) if ven else 0

    # Gastos almacén
    alm = fetch_one("SELECT IFNULL(SUM(costo),0) AS total FROM almacen WHERE tipo='entrada' AND costo IS NOT NULL")
    total_almacen = float(alm["total"]) if alm else 0

    # Calculos
    total_ingresos = total_depositos + total_ventas
    total_gastos   = total_sueldos + total_almacen
    saldo          = total_ingresos - total_gastos

    st.markdown("**Ingresos:**")
    c1, c2 = st.columns(2)
    c1.metric("Depósitos del papá", f"${total_depositos:,.2f}")
    c2.metric("Ventas del rancho", f"${total_ventas:,.2f}")

    st.markdown("**Gastos:**")
    c3, c4 = st.columns(2)
    c3.metric("Almacén / Insumos", f"${total_almacen:,.2f}")
    c4.metric("Sueldos", f"${total_sueldos:,.2f}")

    st.markdown("---")
    color = "normal" if saldo >= 0 else "inverse"
    st.metric("Saldo disponible", f"${saldo:,.2f}", delta_color=color)

    if saldo < 0:
        st.error(f"⚠️ Los gastos superan los ingresos por ${abs(saldo):,.2f}")
    else:
        st.success(f"✅ Hay ${saldo:,.2f} disponibles")