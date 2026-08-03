"""Autenticación y control de sesión."""
import streamlit as st
from utils.database import get_conn, hash_pw, log_auditoria

PERMISOS = {
    "admin":   ["dashboard","colaboradores","marcaciones","novedades","adelantos","documentos","usuarios","auditoria","feriados","exportar","backup"],
    "rrhh":    ["dashboard","colaboradores","marcaciones","novedades","adelantos","documentos","exportar"],
    "consulta":["dashboard","colaboradores","novedades"],
}

def login(username: str, password: str):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM usuarios WHERE username=? AND activo=1",
        (username,)
    ).fetchone()
    conn.close()
    if row and row["password"] == hash_pw(password):
        st.session_state["usuario"] = dict(row)
        log_auditoria(username, "LOGIN")
        return True
    return False

def logout():
    if "usuario" in st.session_state:
        log_auditoria(st.session_state["usuario"]["username"], "LOGOUT")
    for k in ["usuario"]:
        st.session_state.pop(k, None)

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
