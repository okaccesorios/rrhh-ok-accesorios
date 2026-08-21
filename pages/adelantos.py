import streamlit as st
from utils.database import get_conn, dict_cursor, log_auditoria
from utils.auth import usuario_actual
from utils.importar import importar_solicitudes
from datetime import date

TIPOS = ["adelanto","descuento_mercaderia","sancion","otro"]
TIPOS_LABEL = {"adelanto":"💵 Adelanto de sueldo","descuento_mercaderia":"🛍️ Descuento mercadería",
               "sancion":"⚠️ Sanción","otro":"📝 Otro"}


def _qry(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchall()

def _qone(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchone()

def _exec(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)

def show():
    st.markdown('<div class="main-header"><div><h1>💰 Adelantos y Descuentos</h1><span>Importá el formulario o cargá manualmente</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab0, tab1, tab2 = st.tabs(["📥 Importar formulario", "📋 Registros", "➕ Carga manual"])

    with tab0:
        st.markdown("#### Importar desde el Excel de Solicitudes Administrativas")
        st.markdown("""
        <div class="alert-info">
          📌 Este importador lee el Excel que descargás de JotForm y lo separa automáticamente:<br>
          <strong>Adelanto de sueldo</strong> → Adelantos &nbsp;|&nbsp;
          <strong>Compra de mercadería</strong> → Descuentos &nbsp;|&nbsp;
          <strong>Avisos de Ausencias</strong> → Novedades (pendiente de aprobación)
        </div>""", unsafe_allow_html=True)

        archivo = st.file_uploader("Subí el Excel de Solicitudes", type=["xlsx","xls"],
                                   label_visibility="collapsed")
        if archivo:
            if st.button("🚀 Importar", type="primary", use_container_width=True):
                with st.spinner("Procesando..."):
                    n, a, e, errs = importar_solicitudes(archivo.read(), archivo.name, u["username"])
                if e == 0:
                    st.success(f"✅ {n} novedades y {a} adelantos importados correctamente.")
                else:
                    st.warning(f"⚠️ {n} novedades · {a} adelantos · {e} filas con errores:")
                    for err in errs[:10]:
                        st.caption(f"· {err}")

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
            total_adel = sum(r["monto"] or 0 for r in rows if r["tipo"]=="adelanto")
            total_merc = sum(r["monto"] or 0 for r in rows if r["tipo"]=="descuento_mercaderia")
            total_otro = sum(r["monto"] or 0 for r in rows if r["tipo"]=="otro")
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Adelantos sueldo", f"${total_adel:,.0f}")
            c2.metric("Descuentos merc.", f"${total_merc:,.0f}")
            c3.metric("Otros gastos", f"${total_otro:,.0f}")
            c4.metric("Registros totales", len(rows))
            st.markdown("---")
            for r in rows:
                icon = {"adelanto":"💵","descuento_mercaderia":"🛍️","sancion":"⚠️"}.get(r["tipo"],"📝")
                monto_txt = f"${r['monto']:,.0f}" if r["monto"] else "-"
                with st.expander(f"{icon} **{r['nombre']}** — {TIPOS_LABEL.get(r['tipo'],r['tipo'])} | {monto_txt}"):
                    st.write(f"**Período:** {r['periodo']}  |  **Registrado por:** {r['creado_por'] or '-'}")
                    if r["descripcion"]:
                        st.write(f"**Detalle:** {r['descripcion']}")
        else:
            st.info("No hay registros para el período seleccionado.")

    with tab2:
        st.markdown("#### Carga manual")
        conn = get_conn()
        colab = {f"{r['legajo']} — {r['apellido']} {r['nombre']}": r["legajo"]
                 for r in conn.execute("SELECT legajo,apellido,nombre FROM colaboradores WHERE activo=1 ORDER BY apellido").fetchall()}
        conn.close()

        col1, col2 = st.columns(2)
        with col1:
            sel      = st.selectbox("Colaborador *", list(colab.keys()))
            tipo     = st.selectbox("Tipo *", TIPOS, format_func=lambda x: TIPOS_LABEL.get(x,x))
            periodo2 = st.text_input("Período *", value=date.today().strftime("%Y-%m"))
        with col2:
            monto   = st.number_input("Monto ($)", min_value=0.0, step=100.0)
            detalle = st.text_area("Descripción", height=100)

        if st.button("💾 Guardar", type="primary"):
            conn = get_conn()
            conn.execute("""INSERT INTO adelantos (legajo,periodo,tipo,monto,descripcion,creado_por)
                           VALUES (%s,%s,%s,%s,%s,%s)""",
                         (colab[sel], periodo2, tipo, monto or None, detalle or None, u["username"]))
            conn.commit(); conn.close()
            log_auditoria(u["username"],"CREAR_ADELANTO","adelantos",None,f"{colab[sel]} | {tipo} | ${monto}")
            st.success("✅ Guardado correctamente")
            st.rerun()
