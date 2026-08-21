import streamlit as st
from utils.database import get_conn, dict_cursor
from datetime import date

def show():
    st.markdown('<div class="main-header"><div><h1>🔍 Auditoría</h1></div></div>', unsafe_allow_html=True)
    col1,col2,col3 = st.columns(3)
    with col1: desde = st.date_input("Desde", value=date.today().replace(day=1))
    with col2: hasta = st.date_input("Hasta", value=date.today())
    with col3: filtro_user = st.text_input("Usuario")
    conn = get_conn()
    c = dict_cursor(conn)
    sql = "SELECT * FROM auditoria WHERE fecha::date BETWEEN %s AND %s"
    params = [str(desde), str(hasta)]
    if filtro_user.strip(): sql += " AND usuario=%s"; params.append(filtro_user.strip())
    sql += " ORDER BY fecha DESC LIMIT 500"
    c.execute(sql, params)
    rows = c.fetchall()
    conn.close()
    ICON = {"LOGIN":"🔑","LOGOUT":"🚪","IMPORTAR_MARCACIONES":"📥","CREAR_NOVEDAD":"📋",
            "EXPORTAR_EXCEL":"📤","CREAR_COLABORADOR":"👤","CREAR_ADELANTO":"💰"}
    st.caption(f"{len(rows)} registros")
    for r in rows:
        icon = ICON.get(r["accion"],"📌")
        det = f" — {r['detalle']}" if r.get("detalle") else ""
        st.markdown(f"""
        <div style="background:white;border:1px solid #eee;border-left:3px solid #2E75B6;
             padding:0.35rem 0.8rem;border-radius:4px;margin-bottom:0.2rem;font-size:0.82rem;">
          {icon} <strong>{r['usuario']}</strong> · <code>{r['accion']}</code>{det}
          <span style="float:right;color:#aaa;">{r['fecha']}</span>
        </div>""", unsafe_allow_html=True)
