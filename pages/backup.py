import streamlit as st
from utils.database import hacer_backup, log_auditoria
from utils.auth import usuario_actual
from datetime import datetime

def show():
    st.markdown('<div class="main-header"><div><h1>💾 Backup</h1><span>Respaldo de la base de datos</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    st.markdown('<div class="alert-info">🔒 El backup descarga un archivo SQL con todos los datos del sistema.</div>', unsafe_allow_html=True)
    if st.button("💾 Generar y descargar backup", type="primary", use_container_width=True):
        with st.spinner("Generando backup..."):
            sql_content = hacer_backup()
            nombre = f"rrhh_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            log_auditoria(u["username"],"BACKUP")
            st.download_button("⬇️ Descargar backup SQL", data=sql_content,
                               file_name=nombre, mime="text/plain", use_container_width=True)
            st.success("✅ Backup generado correctamente.")
