import streamlit as st
from utils.importar import importar_excel
from utils.auth import usuario_actual
from utils.database import get_conn, dict_cursor
from datetime import date

SECTORES = ["Administración","Compras","Montecaseros","Local calle San Juan","Logistica","Todos / General"]

def show():
    st.markdown('<div class="main-header"><div><h1>⏱️ Importar marcaciones del reloj</h1><span>Subí el Excel de cada sector. El sistema acumula los datos automáticamente.</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2 = st.tabs(["📥 Importar archivo", "📋 Ver marcaciones"])

    with tab1:
        st.markdown("#### Subir archivo de marcaciones")
        st.markdown("""<div class="alert-info">
          📌 <strong>Formato esperado:</strong> Excel con columnas No-Acceso · Nombre · Departamento · Fecha · Hora
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
        col1, col2, col3 = st.columns(3)
        with col1: periodo = st.text_input("Período (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        with col2: sector_filter = st.selectbox("Sector", ["Todos"]+SECTORES[:-1])
        with col3: legajo_filter = st.text_input("Legajo (opcional)")

        conn = get_conn()
        c = dict_cursor(conn)
        sql = """SELECT m.legajo, m.fecha, m.ingreso, m.egreso, m.horas_raw, m.sector, m.fuente,
                        c.apellido||' '||c.nombre as nombre
                 FROM marcaciones m LEFT JOIN colaboradores c ON c.legajo=m.legajo
                 WHERE m.fecha LIKE %s"""
        params = [f"{periodo}%"]
        if sector_filter != "Todos": sql += " AND m.sector=%s"; params.append(sector_filter)
        if legajo_filter.strip(): sql += " AND m.legajo=%s"; params.append(legajo_filter.strip())
        sql += " ORDER BY m.legajo, m.fecha LIMIT 500"
        c.execute(sql, params)
        rows = c.fetchall()
        conn.close()

        if rows:
            st.caption(f"{len(rows)} registros (máx 500)")
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in rows])
            st.dataframe(df, use_container_width=True, height=400)
        else:
            st.info("No hay marcaciones para los filtros seleccionados.")
