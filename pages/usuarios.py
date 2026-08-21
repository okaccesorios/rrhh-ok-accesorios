import streamlit as st
from utils.database import get_conn, dict_cursor, hash_pw, log_auditoria
from utils.auth import usuario_actual

ROLES = ["admin","rrhh","consulta"]
ROL_LABEL = {"admin":"👑 Administrador","rrhh":"👔 RRHH","consulta":"👁️ Consulta"}
ROL_DESC = {"admin":"Acceso total.","rrhh":"Importar, cargar y exportar.","consulta":"Solo lectura."}

def show():
    st.markdown('<div class="main-header"><div><h1>🔑 Usuarios</h1></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2 = st.tabs(["👥 Usuarios activos", "➕ Nuevo usuario"])

    with tab1:
        conn = get_conn()
        c = dict_cursor(conn)
        c.execute("SELECT * FROM usuarios ORDER BY rol, nombre")
        rows = c.fetchall(); conn.close()
        for r in rows:
            ico = "🟢" if r["activo"] else "🔴"
            with st.expander(f"{ico} **{r['nombre']}** (@{r['username']}) — {ROL_LABEL.get(r['rol'],r['rol'])}"):
                c1,c2 = st.columns([3,1])
                with c1:
                    st.write(f"**Rol:** {ROL_LABEL.get(r['rol'],r['rol'])}")
                    st.caption(ROL_DESC.get(r["rol"],""))
                with c2:
                    if r["username"] != u["username"]:
                        nuevo = 0 if r["activo"] else 1
                        if st.button("Baja" if r["activo"] else "Activar", key=f"u_{r['id']}"):
                            conn2 = get_conn(); c2b = dict_cursor(conn2)
                            c2b.execute("UPDATE usuarios SET activo=%s WHERE id=%s",(nuevo,r["id"]))
                            conn2.commit(); conn2.close(); st.rerun()
                        nueva_pw = st.text_input("Nueva contraseña",type="password",key=f"pw_{r['id']}")
                        if st.button("Cambiar",key=f"cpw_{r['id']}") and nueva_pw:
                            conn2 = get_conn(); c2b = dict_cursor(conn2)
                            c2b.execute("UPDATE usuarios SET password=%s WHERE id=%s",(hash_pw(nueva_pw),r["id"]))
                            conn2.commit(); conn2.close(); st.success("✅ Contraseña actualizada")

    with tab2:
        col1,col2 = st.columns(2)
        with col1:
            nuevo_nombre = st.text_input("Nombre completo *")
            nuevo_user = st.text_input("Usuario *")
        with col2:
            nuevo_rol = st.selectbox("Rol *", ROLES, format_func=lambda r: ROL_LABEL[r])
            nueva_pw = st.text_input("Contraseña *", type="password")
            rep_pw = st.text_input("Repetir contraseña *", type="password")

        if st.button("💾 Crear usuario", type="primary"):
            if not nuevo_nombre or not nuevo_user or not nueva_pw:
                st.error("Todos los campos son obligatorios.")
            elif nueva_pw != rep_pw:
                st.error("Las contraseñas no coinciden.")
            else:
                conn = get_conn(); c = dict_cursor(conn)
                try:
                    c.execute("INSERT INTO usuarios (username,nombre,password,rol) VALUES (%s,%s,%s,%s)",
                              (nuevo_user.strip().lower(),nuevo_nombre,hash_pw(nueva_pw),nuevo_rol))
                    conn.commit()
                    log_auditoria(u["username"],"CREAR_USUARIO",None,None,nuevo_user)
                    st.success(f"✅ Usuario @{nuevo_user} creado")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error: el usuario puede ya existir.")
                finally:
                    conn.close()
