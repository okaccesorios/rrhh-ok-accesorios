import streamlit as st
from utils.database import get_conn, dict_cursor, log_auditoria
from utils.auth import usuario_actual, puede

SECTORES = ["Administración","Compras","Montecaseros","Local calle San Juan","Logistica"]


def _qry(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchall()

def _qone(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchone()

def _exec(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>👥 Colaboradores</h1>
      <span>Gestión de la plantilla de personal</span></div>
    </div>""", unsafe_allow_html=True)

    u = usuario_actual()
    tab1, tab2 = st.tabs(["👥 Listado", "➕ Nuevo / Editar"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            filtro_sector = st.selectbox("Sector", ["Todos"] + SECTORES)
        with col2:
            filtro_activo = st.selectbox("Estado", ["Activos","Inactivos","Todos"])

        conn = get_conn()
        q = "SELECT * FROM colaboradores WHERE 1=1"
        p = []
        if filtro_sector != "Todos":
            q += " AND sector=?"; p.append(filtro_sector)
        if filtro_activo == "Activos":
            q += " AND activo=1"
        elif filtro_activo == "Inactivos":
            q += " AND activo=0"
        q += " ORDER BY sector, apellido"
        rows = conn.execute(q, p).fetchall()
        conn.close()

        for r in rows:
            activo_badge = "🟢" if r["activo"] else "🔴"
            rot_txt = " · rotativo" if r["rotativo"] else ""
            tipo_badge = {"externo":"🔗","eventual":"📋"}.get(r["tipo"] or "efectivo", "👔")
            with st.expander(f"{activo_badge} {tipo_badge} **{r['legajo']}** — {r['apellido']} {r['nombre']} | {r['sector']}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**Legajo:** {r['legajo']}")
                    st.markdown(f"**Sector:** {r['sector']}")
                    st.markdown(f"**Turno:** {r['turno'] or 'Fijo'}{rot_txt}")
                with c2:
                    st.markdown(f"**Entrada:** {r['entrada']}  |  **Salida:** {r['salida']}")
                    st.markdown(f"**Sábado:** {r['entrada_sab']} — {r['salida_sab']}")
                    st.markdown(f"**Break:** {r['break_min']}min  |  **Almuerzo:** {r['almuerzo_min']}min")
                with c3:
                    if puede("colaboradores") and u["rol"] in ("admin","rrhh"):
                        nuevo_estado = 0 if r["activo"] else 1
                        label = "🔴 Dar de baja" if r["activo"] else "🟢 Reactivar"
                        if st.button(label, key=f"baja_{r['id']}"):
                            conn2 = get_conn()
                            conn2.execute("UPDATE colaboradores SET activo=? WHERE id=?",
                                          (nuevo_estado, r["id"]))
                            conn2.commit(); conn2.close()
                            log_auditoria(u["username"],"TOGGLE_ACTIVO","colaboradores",r["id"])
                            st.rerun()

    with tab2:
        st.markdown("#### Nuevo colaborador o modificar existente")
        conn = get_conn()
        legs = ["(Nuevo)"] + [f"{r['legajo']} — {r['apellido']} {r['nombre']}"
                               for r in conn.execute(
                                   "SELECT legajo,apellido,nombre FROM colaboradores ORDER BY apellido"
                               ).fetchall()]
        conn.close()
        sel = st.selectbox("Seleccionar colaborador para editar (o dejar 'Nuevo')", legs)

        datos = {}
        if sel != "(Nuevo)":
            leg = sel.split(" — ")[0]
            conn = get_conn()
            datos = dict(conn.execute("SELECT * FROM colaboradores WHERE legajo=?", (leg,)).fetchone() or {})
            conn.close()

        col1, col2 = st.columns(2)
        with col1:
            legajo   = st.text_input("Legajo *", value=datos.get("legajo",""))
            apellido = st.text_input("Apellido *", value=datos.get("apellido",""))
            nombre   = st.text_input("Nombre *", value=datos.get("nombre",""))
            sector   = st.selectbox("Sector *", SECTORES,
                                    index=SECTORES.index(datos["sector"]) if datos.get("sector") in SECTORES else 0)
            tipo_col = st.selectbox("Tipo de relación *",
                                    ["efectivo","externo","eventual"],
                                    index=["efectivo","externo","eventual"].index(datos["tipo"]) if datos.get("tipo") in ["efectivo","externo","eventual"] else 0,
                                    format_func=lambda x: {"efectivo":"👔 Efectivo","externo":"🔗 Externo / Proveedor","eventual":"📋 Eventual"}.get(x,x))
        with col2:
            entrada  = st.text_input("Entrada (HH:MM)", value=datos.get("entrada","09:00"))
            salida   = st.text_input("Salida (HH:MM)", value=datos.get("salida","18:00"))
            ent_sab  = st.text_input("Entrada sábado", value=datos.get("entrada_sab","09:00"))
            sal_sab  = st.text_input("Salida sábado", value=datos.get("salida_sab","13:00"))
            alm_min  = st.number_input("Almuerzo (min)", value=int(datos.get("almuerzo_min",60)), min_value=0)
            brk_min  = st.number_input("Break (min)", value=int(datos.get("break_min",0)), min_value=0)
            rotativo = st.checkbox("Turno rotativo", value=bool(datos.get("rotativo",0)))

        obs = st.text_area("Observaciones", value=datos.get("observaciones","") or "")

        if st.button("💾 Guardar", type="primary"):
            if not legajo or not apellido or not nombre:
                st.error("Legajo, Apellido y Nombre son obligatorios.")
            else:
                conn = get_conn()
                if sel == "(Nuevo)":
                    conn.execute("""INSERT OR REPLACE INTO colaboradores
                        (legajo,apellido,nombre,sector,tipo,entrada,salida,entrada_sab,salida_sab,
                         almuerzo_min,break_min,rotativo,observaciones)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                        (legajo,apellido,nombre,sector,tipo_col,entrada,salida,ent_sab,sal_sab,
                         alm_min,brk_min,int(rotativo),obs))
                    log_auditoria(u["username"],"CREAR_COLABORADOR","colaboradores",None,f"Legajo {legajo}")
                else:
                    conn.execute("""UPDATE colaboradores SET apellido=?,nombre=?,sector=?,tipo=?,
                        entrada=?,salida=?,entrada_sab=?,salida_sab=?,almuerzo_min=?,
                        break_min=?,rotativo=?,observaciones=? WHERE legajo=?""",
                        (apellido,nombre,sector,tipo_col,entrada,salida,ent_sab,sal_sab,
                         alm_min,brk_min,int(rotativo),obs,legajo))
                    log_auditoria(u["username"],"EDITAR_COLABORADOR","colaboradores",None,f"Legajo {legajo}")
                conn.commit(); conn.close()
                st.success("✅ Guardado correctamente")
                st.rerun()
