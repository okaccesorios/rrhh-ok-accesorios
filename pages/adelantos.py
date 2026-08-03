import streamlit as st
from utils.database import get_conn, log_auditoria
from utils.auth import usuario_actual
from datetime import date

TIPOS = ["adelanto","descuento_mercaderia","sancion","otro"]
TIPOS_LABEL = {"adelanto":"💵 Adelanto de sueldo","descuento_mercaderia":"🛍️ Descuento mercadería",
               "sancion":"⚠️ Sanción","otro":"📝 Otro"}

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>💰 Adelantos y Descuentos</h1>
      <span>Registrá adelantos, descuentos de mercadería y sanciones</span></div>
    </div>""", unsafe_allow_html=True)

    u = usuario_actual()
    tab1, tab2 = st.tabs(["📋 Registros", "➕ Nuevo"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            periodo = st.text_input("Período (YYYY-MM)", value=date.today().strftime("%Y-%m"))
        with col2:
            filtro_tipo = st.selectbox("Tipo", ["Todos"] + TIPOS)

        conn = get_conn()
        q = """SELECT a.*, c.apellido||' '||c.nombre as nombre
               FROM adelantos a JOIN colaboradores c ON c.legajo=a.legajo
               WHERE a.periodo=?"""
        p = [periodo]
        if filtro_tipo != "Todos":
            q += " AND a.tipo=?"; p.append(filtro_tipo)
        q += " ORDER BY a.creado_en DESC"
        rows = conn.execute(q, p).fetchall()
        conn.close()

        if rows:
            total_adelantos = sum(r["monto"] or 0 for r in rows if r["tipo"]=="adelanto")
            total_desc      = sum(r["monto"] or 0 for r in rows if r["tipo"]=="descuento_mercaderia")
            c1,c2,c3 = st.columns(3)
            c1.metric("Total adelantos", f"${total_adelantos:,.0f}")
            c2.metric("Total descuentos merc.", f"${total_desc:,.0f}")
            c3.metric("Registros", len(rows))
            st.markdown("---")
            for r in rows:
                icon = {"adelanto":"💵","descuento_mercaderia":"🛍️","sancion":"⚠️"}.get(r["tipo"],"📝")
                with st.expander(f"{icon} **{r['nombre']}** — {TIPOS_LABEL.get(r['tipo'],r['tipo'])} | ${r['monto']:,.0f}" if r["monto"] else f"{icon} **{r['nombre']}** — {r['tipo']}"):
                    st.write(f"**Período:** {r['periodo']}  |  **Registrado por:** {r['creado_por'] or '-'}")
                    if r["descripcion"]:
                        st.write(f"**Detalle:** {r['descripcion']}")
        else:
            st.info("No hay registros para el período seleccionado.")

    with tab2:
        st.markdown("#### Nuevo registro")
        conn = get_conn()
        colab = {f"{r['legajo']} — {r['apellido']} {r['nombre']}": r["legajo"]
                 for r in conn.execute("SELECT legajo,apellido,nombre FROM colaboradores WHERE activo=1 ORDER BY apellido").fetchall()}
        conn.close()

        col1, col2 = st.columns(2)
        with col1:
            sel     = st.selectbox("Colaborador *", list(colab.keys()))
            tipo    = st.selectbox("Tipo *", TIPOS, format_func=lambda x: TIPOS_LABEL.get(x,x))
            periodo2 = st.text_input("Período *", value=date.today().strftime("%Y-%m"))
        with col2:
            monto   = st.number_input("Monto ($)", min_value=0.0, step=100.0)
            detalle = st.text_area("Descripción / detalle", height=100)

        if st.button("💾 Guardar", type="primary"):
            conn = get_conn()
            conn.execute("""INSERT INTO adelantos (legajo,periodo,tipo,monto,descripcion,creado_por)
                           VALUES (?,?,?,?,?,?)""",
                         (colab[sel], periodo2, tipo, monto or None, detalle or None, u["username"]))
            conn.commit(); conn.close()
            log_auditoria(u["username"],"CREAR_ADELANTO","adelantos",None,f"{colab[sel]} | {tipo} | ${monto}")
            st.success("✅ Guardado correctamente")
            st.rerun()
