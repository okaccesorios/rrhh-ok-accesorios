import streamlit as st
from utils.database import get_conn, log_auditoria
from utils.auth import usuario_actual, puede
from datetime import date, datetime

TIPOS = ["Viaje / visita clientes","Licencia por enfermedad","Vacaciones",
         "ART","Home office autorizado","Licencia sin goce de sueldo","Otro"]
ESTADOS = ["pendiente","aprobado","rechazado","enviado"]

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>📋 Bandeja de Novedades</h1>
      <span>Registrá, revisá y aprobá las novedades de los colaboradores</span></div>
    </div>""", unsafe_allow_html=True)

    u = usuario_actual()
    tab1, tab2 = st.tabs(["📋 Ver y aprobar", "➕ Nueva novedad"])

    # ── TAB 1: Listado ────────────────────────────────────────
    with tab1:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            periodo = st.text_input("Período", value=date.today().strftime("%Y-%m"))
        with col2:
            filtro_estado = st.selectbox("Estado", ["Todos"] + ESTADOS)
        with col3:
            filtro_tipo = st.selectbox("Tipo", ["Todos"] + TIPOS)
        with col4:
            filtro_leg = st.text_input("Legajo")

        conn = get_conn()
        query = """SELECT n.*, c.apellido||' '||c.nombre as nombre
                   FROM novedades n JOIN colaboradores c ON c.legajo=n.legajo
                   WHERE (n.fecha_desde LIKE ? OR n.fecha_hasta LIKE ?)"""
        params = [f"{periodo}%", f"{periodo}%"]
        if filtro_estado != "Todos":
            query += " AND n.estado=?"; params.append(filtro_estado)
        if filtro_tipo != "Todos":
            query += " AND n.tipo=?"; params.append(filtro_tipo)
        if filtro_leg.strip():
            query += " AND n.legajo=?"; params.append(filtro_leg.strip())
        query += " ORDER BY n.creado_en DESC"

        novedades = conn.execute(query, params).fetchall()
        conn.close()

        BADGE = {"pendiente":"🟡","aprobado":"🟢","rechazado":"🔴","enviado":"🔵"}

        if not novedades:
            st.info("No hay novedades para los filtros seleccionados.")
        else:
            st.caption(f"{len(novedades)} novedades encontradas")
            for nov in novedades:
                badge = BADGE.get(nov["estado"],"⚪")
                with st.expander(
                    f"{badge} **{nov['nombre']}** — {nov['tipo']} "
                    f"| Desde: {nov['fecha_desde']} "
                    f"{'| Hasta: '+nov['fecha_hasta'] if nov['fecha_hasta'] else ''}"
                ):
                    c1, c2 = st.columns([3,1])
                    with c1:
                        st.markdown(f"**Legajo:** {nov['legajo']}  |  **Estado:** `{nov['estado']}`")
                        st.markdown(f"**Tipo:** {nov['tipo']}")
                        if nov["descripcion"]:
                            st.markdown(f"**Observación:** {nov['descripcion']}")
                        st.caption(f"Creado por {nov['creado_por'] or '-'} el {nov['creado_en']}")
                        if nov["aprobado_por"]:
                            st.caption(f"Aprobado/gestionado por {nov['aprobado_por']}")

                    with c2:
                        if nov["estado"] == "pendiente" and puede("novedades"):
                            if st.button("✅ Aprobar", key=f"apr_{nov['id']}"):
                                _cambiar_estado(nov["id"], "aprobado", u["username"])
                                st.rerun()
                            if st.button("❌ Rechazar", key=f"rec_{nov['id']}"):
                                _cambiar_estado(nov["id"], "rechazado", u["username"])
                                st.rerun()
                        if nov["estado"] == "aprobado" and puede("novedades"):
                            if st.button("📤 Marcar enviada", key=f"env_{nov['id']}"):
                                _cambiar_estado(nov["id"], "enviado", u["username"])
                                st.rerun()

    # ── TAB 2: Nueva novedad ──────────────────────────────────
    with tab2:
        st.markdown("#### Registrar nueva novedad")

        conn = get_conn()
        colab_list = conn.execute(
            "SELECT legajo, apellido||' '||nombre as nombre, sector FROM colaboradores WHERE activo=1 ORDER BY apellido"
        ).fetchall()
        conn.close()

        opciones = {f"{r['legajo']} — {r['nombre']} ({r['sector']})": r["legajo"] for r in colab_list}

        col1, col2 = st.columns(2)
        with col1:
            seleccion = st.selectbox("Colaborador *", list(opciones.keys()))
            tipo      = st.selectbox("Tipo de novedad *", TIPOS)
            fecha_desde = st.date_input("Fecha desde *", value=date.today())
        with col2:
            es_rango = st.checkbox("Es un rango de fechas (varios días)")
            fecha_hasta = None
            if es_rango:
                fecha_hasta = st.date_input("Fecha hasta *", value=date.today())
            descripcion = st.text_area("Observación / detalle", height=100,
                                       placeholder="Descripción opcional de la novedad...")
            auto_aprobar = st.checkbox("Aprobar automáticamente al guardar",
                                       value=True if u["rol"] == "admin" else False)

        if st.button("💾 Guardar novedad", type="primary"):
            legajo = opciones[seleccion]
            estado_inicial = "aprobado" if auto_aprobar else "pendiente"
            aprobado_por   = u["username"] if auto_aprobar else None

            conn = get_conn()
            conn.execute("""INSERT INTO novedades
                (legajo, tipo, fecha_desde, fecha_hasta, descripcion, estado, creado_por, aprobado_por)
                VALUES (?,?,?,?,?,?,?,?)""",
                (legajo, tipo,
                 fecha_desde.strftime("%Y-%m-%d"),
                 fecha_hasta.strftime("%Y-%m-%d") if fecha_hasta else None,
                 descripcion or None, estado_inicial,
                 u["username"], aprobado_por))
            conn.commit()
            nid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.close()
            log_auditoria(u["username"], "CREAR_NOVEDAD", "novedades", nid,
                          f"{legajo} | {tipo} | {fecha_desde}")
            st.success(f"✅ Novedad guardada correctamente ({estado_inicial})")
            st.rerun()

def _cambiar_estado(nov_id, nuevo_estado, usuario):
    conn = get_conn()
    conn.execute("""UPDATE novedades SET estado=?, aprobado_por=?,
                    modificado_en=datetime('now','localtime') WHERE id=?""",
                 (nuevo_estado, usuario, nov_id))
    conn.commit()
    conn.close()
    log_auditoria(usuario, f"NOVEDAD_{nuevo_estado.upper()}", "novedades", nov_id)
