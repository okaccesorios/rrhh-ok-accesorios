"""Autenticación y control de sesión — PostgreSQL version."""
import streamlit as st
from utils.database import get_conn, dict_cursor, hash_pw, log_auditoria

PERMISOS = {
    "admin":   ["dashboard","colaboradores","marcaciones","novedades","adelantos",
                "vacaciones","documentos","usuarios","auditoria","feriados","exportar","backup"],
    "rrhh":    ["dashboard","colaboradores","marcaciones","novedades","adelantos",
                "vacaciones","documentos","exportar"],
    "consulta":["dashboard","colaboradores","novedades","vacaciones"],
}

def login(username: str, password: str):
    try:
        conn = get_conn()
        c = dict_cursor(conn)
        c.execute("SELECT * FROM usuarios WHERE username=%s AND activo=1", (username,))
        row = c.fetchone()
        conn.close()
        if row and row["password"] == hash_pw(password):
            st.session_state["usuario"] = dict(row)
            log_auditoria(username, "LOGIN")
            return True
    except Exception as e:
        st.error(f"Error de conexión: {e}")
    return False

def logout():
    if "usuario" in st.session_state:
        log_auditoria(st.session_state["usuario"]["username"], "LOGOUT")
    st.session_state.pop("usuario", None)

def require_login():
    if "usuario" not in st.session_state:
        st.stop()

def puede(modulo: str) -> bool:
    u = st.session_state.get("usuario")
    if not u:
        return False
    return modulo in PERMISOS.get(u["rol"], [])

def usuario_actual():
    return st.session_state.get("usuario", {})
