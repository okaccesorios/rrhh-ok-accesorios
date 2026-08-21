import streamlit as st
from utils.database import get_conn, dict_cursor, log_auditoria
from utils.auth import usuario_actual, puede
from datetime import date

TIPOS = ["Viaje / visita clientes","Licencia por enfermedad","Vacaciones",
         "ART","Home office autorizado","Licencia sin goce de sueldo","Otro"]

def _qry(conn, sql, p=()):
    c = dict_cursor(conn); c.execute(sql, p); return c.fetchall()
def _qone(conn, sql, p=()):
    c = dict_cursor(conn); c.execute(sql, p); return c.fetchone()

def show():
    st.markdown('<div class="main-header"><div><h1>📋 Bandeja de Novedades</h1><span>Registrá, revisá y aprobá novedades</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2 = st.tabs(["📋 Ver y aprobar", "➕ Nueva novedad"])

    with tab1:
        col1,col2,col3,col4 = st.columns(4)
        with col1: periodo = st.text_input("Período", value=date.today().strftime("%Y-%m"))
        with col2: filtro_estado = st.selectbox("Estado", ["Todos","pendiente","aprobado","rechazado","enviado"])
        with col3: filtro_tipo = st.selectbox("Tipo", ["Todos"]+TIPOS)
        with col4: filtro_leg = st.text_input("Legajo")

        conn = get_conn()
        sql = """SELECT n.*, c.apellido||' '||c.nombre as nombre
                 FROM novedades n JOIN colaboradores c ON c.legajo=n.legajo
                 WHERE (n.fecha_desde LIKE %s OR n.fecha_hasta LIKE %s)"""
        params = [f"{periodo}%", f"{periodo}%"]
        if filtro_estado != "Todos": sql += " AND n.estado=%s"; params.append(filtro_estado)
        if filtro_tipo != "Todos": sql += " AND n.tipo=%s"; params.append(filtro_tipo)
        if filtro_leg.strip(): sql += " AND n.legajo=%s"; params.append(filtro_leg.strip())
        sql += " ORDER BY n.creado_en DESC"
        novedades = _qry(conn, sql, params)

        BADGE = {"pendiente":"🟡","aprobado":"🟢","rechazado":"🔴","enviado":"🔵"}
        if not novedades:
            st.info("No hay novedades para los filtros seleccionados.")
        else:
            st.caption(f"{len(novedades)} novedades")
            for nov in novedades:
                badge = BADGE.get(nov["estado"],"⚪")
                with st.expander(f"{badge} **{nov['nombre']}** — {nov['tipo']} | {nov['fecha_desde']}"):
                    c1,c2 = st.columns([3,1])
                    with c1:
                        st.markdown(f"**Legajo:** {nov['legajo']}  |  **Estado:** `{nov['estado']}`")
                        st.markdown(f"**Tipo:** {nov['tipo']}")
                        if nov["descripcion"]: st.markdown(f"**Obs:** {nov['descripcion']}")
                        st.caption(f"Creado: {nov['creado_en']}")
                    with c2:
                        if nov["estado"] == "pendiente" and puede("novedades"):
                            if st.button("✅ Aprobar", key=f"apr_{nov['id']}"):
                                _cambiar_estado(nov["id"],"aprobado",u["username"]); st.rerun()
                            if st.button("❌ Rechazar", key=f"rec_{nov['id']}"):
                                _cambiar_estado(nov["id"],"rechazado",u["username"]); st.rerun()
                        if nov["estado"] == "aprobado" and puede("novedades"):
                            if st.button("📤 Enviada", key=f"env_{nov['id']}"):
                                _cambiar_estado(nov["id"],"enviado",u["username"]); st.rerun()
        conn.close()

    with tab2:
        st.markdown("#### Registrar nueva novedad")
        conn = get_conn()
        colab_list = _qry(conn, "SELECT legajo, apellido||' '||nombre as nombre, sector FROM colaboradores WHERE activo=1 ORDER BY apellido")
        conn.close()
        opciones = {f"{r['legajo']} — {r['nombre']} ({r['sector']})": r["legajo"] for r in colab_list}
        col1,col2 = st.columns(2)
        with col1:
            seleccion = st.selectbox("Colaborador *", list(opciones.keys()))
            tipo = st.selectbox("Tipo *", TIPOS)
            fecha_desde = st.date_input("Fecha desde *", value=date.today())
        with col2:
            es_rango = st.checkbox("Rango de fechas")
            fecha_hasta = None
            if es_rango: fecha_hasta = st.date_input("Fecha hasta *", value=date.today())
            descripcion = st.text_area("Observación", height=100)
            auto_aprobar = st.checkbox("Aprobar automáticamente", value=u["rol"]=="admin")

        if st.button("💾 Guardar novedad", type="primary"):
            legajo = opciones[seleccion]
            estado = "aprobado" if auto_aprobar else "pendiente"
            aprobado_por = u["username"] if auto_aprobar else None
            conn = get_conn()
            c = dict_cursor(conn)
            c.execute("""INSERT INTO novedades (legajo,tipo,fecha_desde,fecha_hasta,descripcion,estado,creado_por,aprobado_por)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                      (legajo,tipo,fecha_desde.strftime("%Y-%m-%d"),
                       fecha_hasta.strftime("%Y-%m-%d") if fecha_hasta else None,
                       descripcion or None,estado,u["username"],aprobado_por))
            conn.commit(); conn.close()
            st.success("✅ Guardado"); st.rerun()

def _cambiar_estado(nov_id, nuevo_estado, usuario):
    conn = get_conn()
    c = dict_cursor(conn)
    c.execute("UPDATE novedades SET estado=%s, aprobado_por=%s WHERE id=%s",
              (nuevo_estado, usuario, nov_id))
    conn.commit(); conn.close()
    log_auditoria(usuario, f"NOVEDAD_{nuevo_estado.upper()}", "novedades", nov_id)
