import streamlit as st
from utils.database import get_conn, hash_pw, log_auditoria
from utils.auth import usuario_actual

ROLES = ["admin","rrhh","consulta"]
ROL_LABEL = {"admin":"👑 Administrador","rrhh":"👔 RRHH","consulta":"👁️ Consulta"}
ROL_DESC  = {
    "admin":   "Acceso total: puede configurar, aprobar, exportar y ver auditoría.",
    "rrhh":    "Puede importar, cargar novedades, adelantos y exportar el Excel.",
    "consulta":"Solo puede ver el dashboard, colaboradores y novedades. Sin edición.",
}

def show():
    st.markdown('<div class="main-header"><div><h1>🔑 Gestión de Usuarios</h1><span>Alta, baja y permisos de acceso al sistema</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2 = st.tabs(["👥 Usuarios activos", "➕ Nuevo usuario"])

    with tab1:
        conn = get_conn()
        rows = conn.execute("SELECT * FROM usuarios ORDER BY rol, nombre").fetchall()
        conn.close()
        for r in rows:
            activo_ico = "🟢" if r["activo"] else "🔴"
            with st.expander(f"{activo_ico} **{r['nombre']}** (@{r['username']}) — {ROL_LABEL.get(r['rol'],r['rol'])}"):
                c1,c2 = st.columns([3,1])
                with c1:
                    st.write(f"**Rol:** {ROL_LABEL.get(r['rol'],r['rol'])}")
                    st.caption(ROL_DESC.get(r["rol"],""))
                    st.caption(f"Creado: {r['creado_en']}")
                with c2:
                    if r["username"] != u["username"]:
                        nuevo = 0 if r["activo"] else 1
                        if st.button("Baja" if r["activo"] else "Activar", key=f"u_{r['id']}"):
                            conn2 = get_conn()
                            conn2.execute("UPDATE usuarios SET activo=? WHERE id=?",(nuevo,r["id"]))
                            conn2.commit(); conn2.close()
                            log_auditoria(u["username"],"TOGGLE_USUARIO","usuarios",r["id"])
                            st.rerun()
                        nueva_pw = st.text_input("Nueva contraseña",type="password",key=f"pw_{r['id']}")
                        if st.button("Cambiar contraseña",key=f"cpw_{r['id']}") and nueva_pw:
                            conn2 = get_conn()
                            conn2.execute("UPDATE usuarios SET password=? WHERE id=?",(hash_pw(nueva_pw),r["id"]))
                            conn2.commit(); conn2.close()
                            st.success("Contraseña actualizada")

    with tab2:
        st.markdown("#### Crear nuevo usuario")
        col1, col2 = st.columns(2)
        with col1:
            nuevo_nombre = st.text_input("Nombre completo *")
            nuevo_user   = st.text_input("Usuario (sin espacios) *")
        with col2:
            nuevo_rol    = st.selectbox("Rol *", ROLES, format_func=lambda r: ROL_LABEL[r])
            nueva_pw     = st.text_input("Contraseña inicial *", type="password")
            rep_pw       = st.text_input("Repetir contraseña *", type="password")

        st.markdown(f"""
        <div class="alert-info">ℹ️ <strong>{ROL_LABEL.get(nuevo_rol,'')}</strong>: {ROL_DESC.get(nuevo_rol,'')}</div>
        """, unsafe_allow_html=True)

        if st.button("💾 Crear usuario", type="primary"):
            if not nuevo_nombre or not nuevo_user or not nueva_pw:
                st.error("Todos los campos son obligatorios.")
            elif nueva_pw != rep_pw:
                st.error("Las contraseñas no coinciden.")
            else:
                conn = get_conn()
                try:
                    conn.execute("INSERT INTO usuarios (username,nombre,password,rol) VALUES (?,?,?,?)",
                                 (nuevo_user.strip().lower(), nuevo_nombre, hash_pw(nueva_pw), nuevo_rol))
                    conn.commit()
                    log_auditoria(u["username"],"CREAR_USUARIO","usuarios",None,nuevo_user)
                    st.success(f"✅ Usuario @{nuevo_user} creado correctamente")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e} (el usuario puede ya existir)")
                finally:
                    conn.close()
