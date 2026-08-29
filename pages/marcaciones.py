import streamlit as st
from utils.importar import importar_excel
from utils.auth import usuario_actual
from utils.database import get_conn, dict_cursor, log_auditoria
from datetime import date

SECTORES = ["Administración","Compras","Montecaseros","Local calle San Juan","Logistica"]

def show():
    st.markdown('<div class="main-header"><div><h1>⏱️ Importar marcaciones del reloj</h1><span>Subí el Excel de cada sector. El sistema acumula automáticamente sin duplicar.</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2 = st.tabs(["📥 Importar archivo", "📋 Ver y eliminar marcaciones"])

    with tab1:
        st.markdown("#### Subir archivo de marcaciones")
        st.markdown("""<div class="alert-info">
          📌 <strong>Formato:</strong> Excel con columnas No-Acceso · Nombre · Departamento · Fecha · Hora<br>
          ✅ Si ya existe una marcación para ese legajo y fecha, la <strong>actualiza</strong> (no duplica).
        </div>""", unsafe_allow_html=True)
        col1, col2 = st.columns([2,1])
        with col1:
            archivos = st.file_uploader("Arrastrá o seleccioná los archivos Excel",
                                        type=["xlsx","xls"], accept_multiple_files=True,
                                        label_visibility="collapsed")
        with col2:
            sector_forzar = st.selectbox("Sector (opcional)", ["Detectar automáticamente"]+SECTORES)

        if archivos:
            if st.button("🚀 Importar archivos", type="primary", use_container_width=True):
                sector = None if sector_forzar == "Detectar automáticamente" else sector_forzar
                for archivo in archivos:
                    with st.spinner(f"Procesando {archivo.name}..."):
                        n, a, e, errs = importar_excel(archivo.read(), archivo.name, u["username"], sector)
                    if e == 0:
                        st.success(f"✅ **{archivo.name}** — {n} nuevas · {a} actualizadas")
                    else:
                        st.warning(f"⚠️ **{archivo.name}** — {n} nuevas · {a} actualizadas · {e} errores")
                        for err in errs[:5]: st.caption(f"   · {err}")

    with tab2:
        st.markdown("#### Ver y eliminar marcaciones")
        col1, col2, col3 = st.columns(3)
        with col1: periodo = st.text_input("Período (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        with col2: sector_filter = st.selectbox("Sector", ["Todos"]+SECTORES)
        with col3: legajo_filter = st.text_input("Legajo (opcional)")

        conn = get_conn()
        c = dict_cursor(conn)
        sql = """SELECT m.id, m.legajo, m.fecha, m.ingreso, m.egreso, m.horas_raw,
                        m.sector, m.fuente, c.apellido||' '||c.nombre as nombre
                 FROM marcaciones m LEFT JOIN colaboradores c ON c.legajo=m.legajo
                 WHERE m.fecha LIKE %s"""
        params = [f"{periodo}%"]
        if sector_filter != "Todos": sql += " AND m.sector=%s"; params.append(sector_filter)
        if legajo_filter.strip(): sql += " AND m.legajo=%s"; params.append(legajo_filter.strip())
        sql += " ORDER BY m.legajo, m.fecha LIMIT 300"
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()

        if rows:
            st.caption(f"{len(rows)} registros — usá el filtro de legajo para buscar uno específico")

            # Opción de eliminar todas las marcaciones de un período/sector
            with st.expander("🗑️ Eliminar marcaciones en lote (por período y sector)"):
                st.warning("⚠️ Esta acción elimina TODAS las marcaciones del filtro aplicado arriba.")
                if st.button("🗑️ Eliminar todas las marcaciones filtradas", type="secondary"):
                    st.session_state["confirm_del_lote"] = True

                if st.session_state.get("confirm_del_lote"):
                    st.error(f"¿Confirmás eliminar {len(rows)} marcaciones de {periodo}?")
                    col_si, col_no = st.columns(2)
                    with col_si:
                        if st.button("✅ Sí, eliminar todo", type="primary", key="si_lote"):
                            conn2 = get_conn(); c2 = dict_cursor(conn2)
                            sql_del = "DELETE FROM marcaciones WHERE fecha LIKE %s"
                            params_del = [f"{periodo}%"]
                            if sector_filter != "Todos": sql_del += " AND sector=%s"; params_del.append(sector_filter)
                            if legajo_filter.strip(): sql_del += " AND legajo=%s"; params_del.append(legajo_filter.strip())
                            c2.execute(sql_del, params_del)
                            deleted = c2.rowcount
                            conn2.commit(); conn2.close()
                            log_auditoria(u["username"], "ELIMINAR_MARCACIONES_LOTE", "marcaciones",
                                          detalle=f"{deleted} registros eliminados — {periodo}")
                            st.session_state.pop("confirm_del_lote", None)
                            st.success(f"✅ {deleted} marcaciones eliminadas")
                            st.rerun()
                    with col_no:
                        if st.button("❌ Cancelar", key="no_lote"):
                            st.session_state.pop("confirm_del_lote", None)
                            st.rerun()

            st.markdown("---")
            # Tabla con opción de eliminar por fila
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in rows])
            cols_show = [c for c in ["legajo","nombre","sector","fecha","ingreso","egreso","fuente"] if c in df.columns]
            st.dataframe(df[cols_show], use_container_width=True, height=300)

            st.markdown("#### Eliminar una marcación específica")
            col_leg, col_fec = st.columns(2)
            with col_leg: del_legajo = st.text_input("Legajo a eliminar")
            with col_fec: del_fecha  = st.date_input("Fecha a eliminar", value=date.today())

            if del_legajo.strip():
                if st.button("🗑️ Eliminar esta marcación", type="secondary"):
                    st.session_state["confirm_del_uno"] = True

                if st.session_state.get("confirm_del_uno"):
                    st.warning(f"⚠️ ¿Eliminás la marcación del legajo **{del_legajo}** del **{del_fecha.strftime('%d/%m/%Y')}**?")
                    col_si2, col_no2 = st.columns(2)
                    with col_si2:
                        if st.button("✅ Sí, eliminar", type="primary", key="si_uno"):
                            conn2 = get_conn(); c2 = dict_cursor(conn2)
                            c2.execute("DELETE FROM marcaciones WHERE legajo=%s AND fecha=%s",
                                       (del_legajo.strip(), del_fecha.strftime("%Y-%m-%d")))
                            deleted = c2.rowcount
                            conn2.commit(); conn2.close()
                            log_auditoria(u["username"], "ELIMINAR_MARCACION", "marcaciones",
                                          detalle=f"Legajo {del_legajo} | {del_fecha}")
                            st.session_state.pop("confirm_del_uno", None)
                            if deleted:
                                st.success("✅ Marcación eliminada")
                            else:
                                st.warning("No se encontró esa marcación")
                            st.rerun()
                    with col_no2:
                        if st.button("❌ Cancelar", key="no_uno"):
                            st.session_state.pop("confirm_del_uno", None)
                            st.rerun()
        else:
            st.info("No hay marcaciones para los filtros seleccionados.")
