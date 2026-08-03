import streamlit as st
from utils.database import get_conn
from datetime import date

def show():
    st.markdown('<div class="main-header"><div><h1>🔍 Auditoría</h1><span>Registro de todas las acciones realizadas en el sistema</span></div></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        desde = st.date_input("Desde", value=date.today().replace(day=1))
    with col2:
        hasta = st.date_input("Hasta", value=date.today())
    with col3:
        filtro_user = st.text_input("Usuario (opcional)")

    conn = get_conn()
    q = "SELECT * FROM auditoria WHERE DATE(fecha) BETWEEN ? AND ?"
    p = [str(desde), str(hasta)]
    if filtro_user.strip():
        q += " AND usuario=?"; p.append(filtro_user.strip())
    q += " ORDER BY fecha DESC LIMIT 500"
    rows = conn.execute(q, p).fetchall()
    conn.close()

    ACCION_ICON = {
        "LOGIN":"🔑","LOGOUT":"🚪","IMPORTAR_MARCACIONES":"📥",
        "CREAR_NOVEDAD":"📋","NOVEDAD_APROBADO":"✅","NOVEDAD_RECHAZADO":"❌",
        "EXPORTAR_EXCEL":"📤","CREAR_COLABORADOR":"👤","EDITAR_COLABORADOR":"✏️",
        "CREAR_ADELANTO":"💰","CREAR_USUARIO":"🆕","TOGGLE_USUARIO":"🔄",
        "CREAR_FERIADO":"📅","BACKUP":"💾",
    }

    st.caption(f"{len(rows)} registros (máx 500)")
    for r in rows:
        icon = ACCION_ICON.get(r["accion"],"📌")
        det  = f" — {r['detalle']}" if r["detalle"] else ""
        tab  = f" | {r['tabla']}" if r["tabla"] else ""
        st.markdown(f"""
        <div style="background:white;border:1px solid #eee;border-left:3px solid #2E75B6;
             padding:0.35rem 0.8rem;border-radius:4px;margin-bottom:0.2rem;font-size:0.82rem;">
          {icon} <strong>{r['usuario']}</strong> · <code>{r['accion']}</code>{tab}{det}
          <span style="float:right;color:#aaa;">{r['fecha']}</span>
        </div>""", unsafe_allow_html=True)
