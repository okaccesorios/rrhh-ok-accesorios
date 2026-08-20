"""
OK Accesorios — Sistema de Gestión RRHH
Aplicación principal Streamlit
"""
import streamlit as st
from utils.database import init_db
from utils.auth import login, logout, usuario_actual, puede

st.set_page_config(
    page_title="OK Accesorios — RRHH",
    page_icon="👔",
    layout="wide",
    initial_sidebar_state="expanded",
)

# CSS global
st.markdown("""
<style>
  /* Paleta */
  :root {
    --dark:  #1F3864;
    --blue:  #2E75B6;
    --lblue: #D6E4F0;
    --green: #375623;
    --lgrn:  #E2EFDA;
    --yel:   #FFF2CC;
    --red:   #C00000;
  }
  /* Header superior */
  .main-header {
    background: linear-gradient(135deg, var(--dark) 0%, var(--blue) 100%);
    color: white;
    padding: 1rem 1.5rem;
    border-radius: 8px;
    margin-bottom: 1.2rem;
    display: flex;
    align-items: center;
    gap: 1rem;
  }
  .main-header h1 { margin:0; font-size:1.5rem; font-weight:700; }
  .main-header span { font-size:0.85rem; opacity:0.8; }

  /* Tarjetas métricas */
  .metric-card {
    background: white;
    border: 1px solid #e0e0e0;
    border-left: 4px solid var(--blue);
    border-radius: 6px;
    padding: 1rem 1.2rem;
    margin-bottom: 0.5rem;
  }
  .metric-card.green { border-left-color: var(--green); }
  .metric-card.red   { border-left-color: var(--red); }
  .metric-card.yel   { border-left-color: #E6AC00; }
  .metric-card h3 { margin:0; font-size:1.8rem; font-weight:700; color: var(--dark); }
  .metric-card p  { margin:0; font-size:0.78rem; color:#666; }

  /* Badges de estado */
  .badge {
    display:inline-block; padding:2px 10px; border-radius:12px;
    font-size:0.75rem; font-weight:600;
  }
  .badge-pendiente { background:#FFF2CC; color:#7D4000; }
  .badge-aprobado  { background:#E2EFDA; color:#375623; }
  .badge-rechazado { background:#FCE4D6; color:#C00000; }
  .badge-enviado   { background:#D6E4F0; color:#1F3864; }

  /* Sidebar */
  [data-testid="stSidebar"] { background: #F8FAFB; }
  .sidebar-logo {
    text-align:center; padding:1rem 0 0.5rem;
    font-weight:700; font-size:1.1rem; color: var(--dark);
    border-bottom: 2px solid var(--lblue); margin-bottom: 0.5rem;
  }
  .sidebar-user {
    background: var(--lblue); border-radius:6px;
    padding: 0.5rem 0.8rem; font-size:0.8rem; margin-bottom:0.5rem;
  }

  /* Tablas */
  .stDataFrame { border-radius: 6px; overflow: hidden; }

  /* Botones */
  .stButton > button {
    border-radius: 6px; font-weight: 600;
  }

  /* Inputs */
  .stTextInput > div > div > input,
  .stSelectbox > div > div > div {
    border-radius: 6px;
  }

  /* Alertas personalizadas */
  .alert-info { background:#D6E4F0; border-left:4px solid #2E75B6; padding:0.7rem 1rem; border-radius:4px; margin:0.5rem 0; }
  .alert-ok   { background:#E2EFDA; border-left:4px solid #375623; padding:0.7rem 1rem; border-radius:4px; margin:0.5rem 0; }
  .alert-warn { background:#FFF2CC; border-left:4px solid #E6AC00; padding:0.7rem 1rem; border-radius:4px; margin:0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# Inicializar BD
init_db()

# ── LOGIN ─────────────────────────────────────────────────────────
if "usuario" not in st.session_state:
    col1, col2, col3 = st.columns([1,1.2,1])
    with col2:
        st.markdown("""
        <div style="text-align:center; padding:2rem 0 1rem;">
          <div style="font-size:3rem;">👔</div>
          <h2 style="color:#1F3864; margin:0.3rem 0 0.1rem;">OK Accesorios</h2>
          <p style="color:#666; font-size:0.9rem; margin:0;">Sistema de Gestión RRHH</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown("#### Iniciar sesión")
            username = st.text_input("Usuario", placeholder="tu.usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

        if submitted:
            if login(username, password):
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")

        st.markdown("<p style='text-align:center;font-size:0.75rem;color:#aaa;margin-top:2rem;'>v3.0 · Recursos Humanos</p>", unsafe_allow_html=True)
    st.stop()

# ── SIDEBAR ───────────────────────────────────────────────────────
u = usuario_actual()
with st.sidebar:
    st.markdown(f"""
    <div class="sidebar-logo">👔 OK Accesorios<br>
    <span style="font-size:0.7rem;font-weight:400;color:#666;">Sistema RRHH v3.0</span></div>
    <div class="sidebar-user">
      👤 <strong>{u['nombre']}</strong><br>
      <span style="color:#555;">{u['rol'].upper()}</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("**Navegación**")
    paginas = []
    if puede("dashboard"):       paginas.append(("📊 Dashboard",       "dashboard"))
    if puede("marcaciones"):     paginas.append(("⏱️ Importar reloj",  "marcaciones"))
    if puede("novedades"):       paginas.append(("📋 Novedades",        "novedades"))
    if puede("colaboradores"):   paginas.append(("👥 Colaboradores",    "colaboradores"))
    if puede("adelantos"):       paginas.append(("💰 Adelantos",        "adelantos"))
    if puede("novedades"):       paginas.append(("🏖️ Vacaciones",       "vacaciones"))
    if puede("exportar"):        paginas.append(("📤 Exportar Excel",   "exportar"))
    if puede("feriados"):        paginas.append(("📅 Feriados",         "feriados"))
    if puede("usuarios"):        paginas.append(("🔑 Usuarios",         "usuarios"))
    if puede("auditoria"):       paginas.append(("🔍 Auditoría",        "auditoria"))
    if puede("backup"):          paginas.append(("💾 Backup",           "backup"))

    pagina_labels = [p[0] for p in paginas]
    pagina_keys   = [p[1] for p in paginas]

    if "pagina" not in st.session_state:
        st.session_state["pagina"] = "dashboard"

    for label, key in paginas:
        active = st.session_state["pagina"] == key
        if st.button(label, use_container_width=True,
                     type="primary" if active else "secondary"):
            st.session_state["pagina"] = key
            st.rerun()

    st.markdown("---")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        logout()
        st.rerun()

# ── PÁGINAS ───────────────────────────────────────────────────────
pag = st.session_state.get("pagina","dashboard")

if pag == "dashboard":
    from pages import dashboard; dashboard.show()
elif pag == "marcaciones":
    from pages import marcaciones; marcaciones.show()
elif pag == "novedades":
    from pages import novedades; novedades.show()
elif pag == "colaboradores":
    from pages import colaboradores; colaboradores.show()
elif pag == "adelantos":
    from pages import adelantos; adelantos.show()
elif pag == "exportar":
    from pages import exportar; exportar.show()
elif pag == "feriados":
    from pages import feriados; feriados.show()
elif pag == "usuarios":
    from pages import usuarios; usuarios.show()
elif pag == "auditoria":
    from pages import auditoria; auditoria.show()
elif pag == "backup":
    from pages import backup; backup.show()
    elif pag == "vacaciones":
    from pages import vacaciones; vacaciones.show()
