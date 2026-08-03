import streamlit as st
from utils.database import hacer_backup, DB_PATH, log_auditoria
from utils.auth import usuario_actual
from pathlib import Path
from datetime import datetime

def show():
    st.markdown('<div class="main-header"><div><h1>💾 Backup de la base de datos</h1><span>Respaldo y descarga de toda la información</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()

    st.markdown("""
    <div class="alert-info">
      🔒 <strong>¿Qué hace el backup?</strong> Guarda una copia exacta de toda la base de datos
      (colaboradores, marcaciones, novedades, adelantos, auditoría). Se conservan los últimos 10 backups automáticamente.
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Crear backup ahora")
        if st.button("💾 Generar backup", type="primary", use_container_width=True):
            ruta = hacer_backup()
            log_auditoria(u["username"],"BACKUP",detalle=ruta)
            st.success(f"✅ Backup creado: {Path(ruta).name}")

        # Descargar la BD actual directamente
        if DB_PATH.exists():
            with open(str(DB_PATH), "rb") as f:
                st.download_button(
                    "⬇️ Descargar base de datos actual",
                    data=f.read(),
                    file_name=f"rrhh_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db",
                    mime="application/octet-stream",
                    use_container_width=True,
                )

    with col2:
        st.markdown("#### Backups anteriores")
        backup_dir = DB_PATH.parent.parent / "backups"
        if backup_dir.exists():
            backups = sorted(backup_dir.glob("rrhh_backup_*.db"), reverse=True)
            if backups:
                for b in backups[:10]:
                    size_kb = b.stat().st_size // 1024
                    st.markdown(f"""
                    <div style="background:white;border:1px solid #eee;padding:0.4rem 0.8rem;
                         border-radius:4px;margin-bottom:0.3rem;font-size:0.82rem;">
                      💾 <strong>{b.name}</strong><br>
                      <span style="color:#888;">{size_kb} KB</span>
                    </div>""", unsafe_allow_html=True)
            else:
                st.info("No hay backups anteriores.")
        else:
            st.info("Aún no se generó ningún backup.")
