import streamlit as st
from utils.importar import importar_excel
from utils.auth import usuario_actual
from utils.database import get_conn
from datetime import date

SECTORES = ["Administración","Compras","Montecaseros","Local calle San Juan","Logistica","Todos / General"]

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>⏱️ Importar marcaciones del reloj</h1>
      <span>Subí el Excel de cada sector. El sistema acumula los datos automáticamente.</span></div>
    </div>""", unsafe_allow_html=True)

    u = usuario_actual()

    tab1, tab2 = st.tabs(["📥 Importar archivo", "📋 Ver marcaciones"])

    with tab1:
        st.markdown("#### Subir archivo de marcaciones")
        st.markdown("""
        <div class="alert-info">
          📌 <strong>Formato esperado:</strong> Excel con columnas No-Acceso · Nombre · Departamento · Fecha · Hora<br>
          Podés subir varios archivos (uno por sector). El sistema identifica el sector automáticamente.
        </div>""", unsafe_allow_html=True)

        col1, col2 = st.columns([2,1])
        with col1:
            archivos = st.file_uploader(
                "Arrastrá o seleccioná los archivos Excel",
                type=["xlsx","xls"],
                accept_multiple_files=True,
                label_visibility="collapsed"
            )
        with col2:
            sector_forzar = st.selectbox(
                "Sector (opcional — si querés forzar uno)",
                ["Detectar automáticamente"] + SECTORES
            )

        if archivos:
            if st.button("🚀 Importar archivos", type="primary", use_container_width=True):
                sector = None if sector_forzar == "Detectar automáticamente" else sector_forzar

                total_n = total_a = total_e = 0
                for archivo in archivos:
                    with st.spinner(f"Procesando {archivo.name}..."):
                        n, a, e, errs = importar_excel(
                            archivo.read(), archivo.name,
                            u["username"], sector
                        )
                        total_n += n; total_a += a; total_e += e

                        if e == 0:
                            st.success(f"✅ **{archivo.name}** — {n} nuevas · {a} actualizadas")
                        else:
                            st.warning(f"⚠️ **{archivo.name}** — {n} nuevas · {a} actualizadas · {e} errores")
                            for err in errs[:5]:
                                st.caption(f"   · {err}")

                st.markdown(f"""
                <div class="alert-ok" style="margin-top:1rem;">
                  ✅ Importación completada: <strong>{total_n}</strong> registros nuevos,
                  <strong>{total_a}</strong> actualizados, <strong>{total_e}</strong> errores.
                </div>""", unsafe_allow_html=True)

    with tab2:
        st.markdown("#### Marcaciones almacenadas")
        col1, col2, col3 = st.columns(3)
        with col1:
            periodo = st.text_input("Período (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        with col2:
            sector_filter = st.selectbox("Sector", ["Todos"] + SECTORES[:-1])
        with col3:
            legajo_filter = st.text_input("Legajo (opcional)")

        conn = get_conn()
        query = "SELECT m.*, c.apellido||' '||c.nombre as nombre_col FROM marcaciones m LEFT JOIN colaboradores c ON c.legajo=m.legajo WHERE m.fecha LIKE ?"
        params = [f"{periodo}%"]
        if sector_filter != "Todos":
            query += " AND m.sector=?"; params.append(sector_filter)
        if legajo_filter.strip():
            query += " AND m.legajo=?"; params.append(legajo_filter.strip())
        query += " ORDER BY m.legajo, m.fecha LIMIT 500"

        rows = conn.execute(query, params).fetchall()
        conn.close()

        if rows:
            st.caption(f"{len(rows)} registros (máx 500 mostrados)")
            import pandas as pd
            df = pd.DataFrame([dict(r) for r in rows])
            cols_show = ["legajo","nombre_col","sector","fecha","ingreso","egreso","horas_raw","fuente"]
            cols_show = [c for c in cols_show if c in df.columns]
            st.dataframe(df[cols_show], use_container_width=True, height=400)
        else:
            st.info("No hay marcaciones para los filtros seleccionados.")
