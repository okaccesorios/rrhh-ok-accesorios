import streamlit as st
from utils.database import get_conn, dict_cursor, log_auditoria
from utils.auth import usuario_actual
from utils.importar import importar_solicitudes
from datetime import date

TIPOS = ["adelanto","descuento_mercaderia","sancion","otro"]
TIPOS_LABEL = {"adelanto":"💵 Adelanto de sueldo","descuento_mercaderia":"🛍️ Descuento mercadería",
               "sancion":"⚠️ Sanción","otro":"📝 Otro"}

def show():
    st.markdown('<div class="main-header"><div><h1>💰 Adelantos y Descuentos</h1><span>Importá el formulario o cargá manualmente</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab0, tab1, tab2 = st.tabs(["📥 Importar formulario", "📋 Registros", "➕ Carga manual"])

    with tab0:
        st.markdown("#### Importar desde el Excel de Solicitudes Administrativas")
        st.markdown("""<div class="alert-info">
          📌 Separa automáticamente: <strong>Adelanto de sueldo</strong> → Adelantos |
          <strong>Compra de mercadería</strong> → Descuentos |
          <strong>Avisos de Ausencias</strong> → Novedades pendientes.<br>
          ✅ El sistema <strong>no duplica</strong> — si ya existe un registro igual lo omite.
        </div>""", unsafe_allow_html=True)
        archivo = st.file_uploader("Subí el Excel de Solicitudes", type=["xlsx","xls"],
                                   label_visibility="collapsed")
        if archivo:
            if st.button("🚀 Importar", type="primary", use_container_width=True):
                with st.spinner("Procesando..."):
                    n, a, e, errs = importar_solicitudes(archivo.read(), archivo.name, u["username"])
                if e == 0:
                    st.success(f"✅ {n} novedades y {a} adelantos importados.")
                else:
                    st.warning(f"⚠️ {n} novedades · {a} adelantos · {e} errores:")
                    for err in errs[:10]: st.caption(f"· {err}")

    with tab1:
        col1, col2 = st.columns(2)
        with col1: periodo = st.text_input("Período (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        with col2: filtro_tipo = st.selectbox("Tipo", ["Todos"]+TIPOS)

        conn = get_conn()
        c = dict_cursor(conn)
        sql = """SELECT a.id, a.legajo, a.periodo, a.tipo, a.monto, a.descripcion, a.creado_por, a.creado_en,
                        c.apellido||' '||c.nombre as nombre
                 FROM adelantos a JOIN colaboradores c ON c.legajo=a.legajo
                 WHERE a.periodo=%s"""
        params = [periodo]
        if filtro_tipo != "Todos": sql += " AND a.tipo=%s"; params.append(filtro_tipo)
        sql += " ORDER BY a.creado_en DESC"
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()

        if rows:
            total_adel = sum(float(r["monto"] or 0) for r in rows if r["tipo"]=="adelanto")
            total_merc = sum(float(r["monto"] or 0) for r in rows if r["tipo"]=="descuento_mercaderia")
            total_otro = sum(float(r["monto"] or 0) for r in rows if r["tipo"]=="otro")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Adelantos sueldo", f"${total_adel:,.0f}")
            c2.metric("Descuentos merc.", f"${total_merc:,.0f}")
            c3.metric("Otros gastos", f"${total_otro:,.0f}")
            c4.metric("Registros", len(rows))
            st.markdown("---")

            for r in rows:
                icon = {"adelanto":"💵","descuento_mercaderia":"🛍️","sancion":"⚠️"}.get(r["tipo"],"📝")
                monto_txt = f"${float(r['monto']):,.0f}" if r["monto"] else "-"
                with st.expander(f"{icon} **{r['nombre']}** — {TIPOS_LABEL.get(r['tipo'],r['tipo'])} | {monto_txt}"):
                    col_info, col_del = st.columns([4,1])
                    with col_info:
                        st.write(f"**ID:** {r['id']}  |  **Período:** {r['periodo']}  |  **Por:** {r['creado_por'] or '-'}")
                        st.write(f"**Fecha:** {r['creado_en']}")
                        if r["descripcion"]: st.write(f"**Detalle:** {r['descripcion']}")
                    with col_del:
                        if st.button("🗑️ Eliminar", key=f"del_{r['id']}", type="secondary"):
                            st.session_state[f"confirm_del_{r['id']}"] = True

                    # Confirmación antes de borrar
                    if st.session_state.get(f"confirm_del_{r['id']}"):
                        st.warning(f"⚠️ ¿Eliminás este registro? **{r['nombre']}** — {monto_txt}")
                        col_si, col_no = st.columns(2)
                        with col_si:
                            if st.button("✅ Sí, eliminar", key=f"si_{r['id']}", type="primary"):
                                conn2 = get_conn(); c2 = dict_cursor(conn2)
                                c2.execute("DELETE FROM adelantos WHERE id=%s", (r["id"],))
                                conn2.commit(); conn2.close()
                                log_auditoria(u["username"], "ELIMINAR_ADELANTO", "adelantos", r["id"],
                                              f"{r['nombre']} | {r['tipo']} | ${r['monto']}")
                                st.session_state.pop(f"confirm_del_{r['id']}", None)
                                st.success("✅ Registro eliminado")
                                st.rerun()
                        with col_no:
                            if st.button("❌ Cancelar", key=f"no_{r['id']}"):
                                st.session_state.pop(f"confirm_del_{r['id']}", None)
                                st.rerun()
        else:
            st.info("No hay registros para el período seleccionado.")

    with tab2:
        conn = get_conn()
        c = dict_cursor(conn)
        c.execute("SELECT legajo, apellido||' '||nombre as nombre FROM colaboradores WHERE activo=1 ORDER BY apellido")
        colab_list = c.fetchall()
        conn.close()
        colab = {f"{r['legajo']} — {r['nombre']}": r["legajo"] for r in colab_list}

        col1, col2 = st.columns(2)
        with col1:
            sel      = st.selectbox("Colaborador *", list(colab.keys()))
            tipo     = st.selectbox("Tipo *", TIPOS, format_func=lambda x: TIPOS_LABEL.get(x,x))
            periodo2 = st.text_input("Período *", value=date.today().strftime("%Y-%m"))
        with col2:
            monto   = st.number_input("Monto ($)", min_value=0.0, step=100.0)
            detalle = st.text_area("Descripción", height=100)

        if st.button("💾 Guardar", type="primary"):
            conn = get_conn(); c = dict_cursor(conn)
            # Verificar duplicado antes de insertar
            c.execute("""SELECT id FROM adelantos
                         WHERE legajo=%s AND periodo=%s AND tipo=%s AND monto=%s""",
                      (colab[sel], periodo2, tipo, monto))
            if c.fetchone():
                conn.close()
                st.warning("⚠️ Ya existe un registro igual para este colaborador, período y monto.")
            else:
                c.execute("""INSERT INTO adelantos (legajo,periodo,tipo,monto,descripcion,creado_por)
                             VALUES (%s,%s,%s,%s,%s,%s)""",
                          (colab[sel], periodo2, tipo, monto or None, detalle or None, u["username"]))
                conn.commit(); conn.close()
                log_auditoria(u["username"],"CREAR_ADELANTO","adelantos",None,
                              f"{colab[sel]} | {tipo} | ${monto}")
                st.success("✅ Guardado"); st.rerun()
