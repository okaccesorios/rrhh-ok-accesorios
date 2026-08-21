import streamlit as st
from utils.database import get_conn, dict_cursor, log_auditoria
from utils.auth import usuario_actual
from datetime import date

def show():
    st.markdown('<div class="main-header"><div><h1>📅 Feriados</h1></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2 = st.tabs(["📅 Listado", "➕ Agregar"])
    with tab1:
        anio = st.number_input("Año", value=date.today().year, min_value=2024, max_value=2030)
        conn = get_conn()
        c = dict_cursor(conn)
        c.execute("SELECT * FROM feriados WHERE fecha LIKE %s ORDER BY fecha", (f"{anio}%",))
        rows = c.fetchall()
        conn.close()
        for r in rows:
            col1,col2,col3 = st.columns([2,3,1])
            col1.write(r["fecha"]); col2.write(r["descripcion"]); col3.write(r["tipo"])
        if not rows: st.info(f"Sin feriados para {anio}.")
    with tab2:
        col1,col2 = st.columns(2)
        with col1:
            fecha_f = st.date_input("Fecha")
            desc_f = st.text_input("Descripción")
        with col2:
            tipo_f = st.selectbox("Tipo", ["nacional","provincial","no_laborable"])
        if st.button("💾 Agregar", type="primary"):
            conn = get_conn()
            c = dict_cursor(conn)
            c.execute("INSERT INTO feriados (fecha,descripcion,tipo) VALUES (%s,%s,%s) ON CONFLICT (fecha) DO NOTHING",
                      (fecha_f.strftime("%Y-%m-%d"),desc_f,tipo_f))
            conn.commit(); conn.close()
            log_auditoria(u["username"],"CREAR_FERIADO")
            st.success("✅ Agregado"); st.rerun()
