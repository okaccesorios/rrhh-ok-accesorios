import streamlit as st
from utils.database import get_conn, log_auditoria
from utils.auth import usuario_actual
from datetime import date

def show():
    st.markdown('<div class="main-header"><div><h1>📅 Feriados</h1><span>Gestión de feriados nacionales y provinciales</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2 = st.tabs(["📅 Listado", "➕ Agregar"])

    with tab1:
        anio = st.number_input("Año", value=date.today().year, min_value=2024, max_value=2030)
        conn = get_conn()
        rows = conn.execute("SELECT * FROM feriados WHERE fecha LIKE ? ORDER BY fecha", (f"{anio}%",)).fetchall()
        conn.close()
        if rows:
            for r in rows:
                c1, c2, c3 = st.columns([2,3,1])
                c1.write(r["fecha"])
                c2.write(r["descripcion"])
                c3.write(r["tipo"])
        else:
            st.info(f"No hay feriados cargados para {anio}.")

    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            fecha_f = st.date_input("Fecha del feriado")
            desc_f  = st.text_input("Descripción")
        with col2:
            tipo_f  = st.selectbox("Tipo", ["nacional","provincial","no_laborable"])
        if st.button("💾 Agregar feriado", type="primary"):
            conn = get_conn()
            conn.execute("INSERT OR IGNORE INTO feriados (fecha,descripcion,tipo) VALUES (?,?,?)",
                         (fecha_f.strftime("%Y-%m-%d"), desc_f, tipo_f))
            conn.commit(); conn.close()
            log_auditoria(u["username"],"CREAR_FERIADO","feriados",None,str(fecha_f))
            st.success("✅ Feriado agregado")
            st.rerun()
