import streamlit as st
from utils.database import get_conn, dict_cursor, log_auditoria
from utils.auth import usuario_actual
from utils.importar import importar_vacaciones
from datetime import date, timedelta

def show():
    st.markdown('<div class="main-header"><div><h1>🏖️ Vacaciones</h1><span>Importá el cuadro o registrá períodos manualmente</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    tab1, tab2, tab3 = st.tabs(["📥 Importar cuadro", "📋 Ver vacaciones", "➕ Cargar manual"])

    with tab1:
        st.markdown("#### Importar desde el cuadro de vacaciones Excel")
        st.markdown("""<div class="alert-info">
          📌 El sistema lee la hoja <strong>Resumen</strong>. Formato: Apellido y nombre · Salida · Reincorp · Días.<br>
          Las vacaciones se importan como novedades <strong>aprobadas automáticamente</strong>.
        </div>""", unsafe_allow_html=True)
        archivo = st.file_uploader("Subí el Excel de vacaciones", type=["xlsx","xls"], label_visibility="collapsed")
        if archivo:
            if st.button("🚀 Importar vacaciones", type="primary", use_container_width=True):
                with st.spinner("Procesando..."):
                    imp, omit, e, errs = importar_vacaciones(archivo.read(), archivo.name, u["username"])
                if e == 0:
                    st.success(f"✅ {imp} períodos importados. {omit} ya existían.")
                else:
                    st.warning(f"⚠️ {imp} importados · {omit} omitidos · {e} errores:")
                    for err in errs[:10]: st.caption(f"· {err}")

    with tab2:
        col1, col2 = st.columns(2)
        with col1: anio = st.number_input("Año", value=date.today().year, min_value=2024, max_value=2030)
        with col2: filtro_sector = st.selectbox("Sector", ["Todos","Administración","Compras","Montecaseros","Local calle San Juan","Logistica"])

        conn = get_conn()
        c = dict_cursor(conn)
        c.execute("""SELECT n.*, c.apellido||' '||c.nombre as nombre, c.sector
                     FROM novedades n JOIN colaboradores c ON c.legajo=n.legajo
                     WHERE n.tipo='Vacaciones' AND (n.fecha_desde LIKE %s OR n.fecha_hasta LIKE %s)
                     ORDER BY n.fecha_desde""", (f"{anio}%", f"{anio}%"))
        rows = c.fetchall()
        conn.close()

        if filtro_sector != "Todos":
            rows = [r for r in rows if r["sector"] == filtro_sector]

        if rows:
            resumen = {}
            for r in rows:
                key = r["nombre"]
                if key not in resumen:
                    resumen[key] = {"sector": r["sector"], "periodos": [], "total": 0}
                desde = date.fromisoformat(r["fecha_desde"])
                hasta = date.fromisoformat(r["fecha_hasta"]) if r["fecha_hasta"] else desde
                dias = (hasta - desde).days + 1
                resumen[key]["periodos"].append((desde, hasta, dias, r["estado"]))
                resumen[key]["total"] += dias

            st.caption(f"{len(resumen)} colaboradores con vacaciones en {anio}")
            for nombre, datos in sorted(resumen.items(), key=lambda x: x[1]["sector"]):
                with st.expander(f"🏖️ **{nombre}** | {datos['sector']} — {datos['total']} días"):
                    for desde, hasta, dias, estado in datos["periodos"]:
                        hoy = date.today()
                        icono = "✅" if hasta < hoy else ("🏖️" if desde <= hoy <= hasta else "📅")
                        st.markdown(f"""<div style="background:white;border-left:3px solid #2E75B6;
                             border:1px solid #eee;padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;">
                          {icono} Desde <strong>{desde.strftime('%d/%m/%Y')}</strong>
                          hasta <strong>{hasta.strftime('%d/%m/%Y')}</strong> — <strong>{dias} días</strong>
                          <span style="float:right;color:#888;">{estado}</span>
                        </div>""", unsafe_allow_html=True)
        else:
            st.info(f"No hay vacaciones registradas para {anio}.")

    with tab3:
        conn = get_conn()
        c = dict_cursor(conn)
        c.execute("SELECT legajo, apellido||' '||nombre as nombre FROM colaboradores WHERE activo=1 ORDER BY apellido")
        colab = {f"{r['legajo']} — {r['nombre']}": r["legajo"] for r in c.fetchall()}
        conn.close()

        col1, col2 = st.columns(2)
        with col1:
            sel = st.selectbox("Colaborador *", list(colab.keys()))
            fecha_sal = st.date_input("Fecha de salida *", value=date.today())
        with col2:
            fecha_rei = st.date_input("Fecha de reincorporación *", value=date.today()+timedelta(days=14))
            obs = st.text_input("Observación (opcional)")

        if fecha_rei > fecha_sal:
            hasta = fecha_rei - timedelta(days=1)
            dias = (hasta - fecha_sal).days + 1
            st.markdown(f'<div class="alert-info">📅 {fecha_sal.strftime("%d/%m/%Y")} al {hasta.strftime("%d/%m/%Y")} — {dias} días aprox.</div>', unsafe_allow_html=True)

        if st.button("💾 Guardar vacaciones", type="primary"):
            if fecha_rei <= fecha_sal:
                st.error("La fecha de reincorporación debe ser posterior a la de salida.")
            else:
                hasta = fecha_rei - timedelta(days=1)
                legajo = colab[sel]
                conn = get_conn(); c = dict_cursor(conn)
                c.execute("""INSERT INTO novedades (legajo,tipo,fecha_desde,fecha_hasta,descripcion,estado,creado_por,aprobado_por)
                            VALUES (%s,'Vacaciones',%s,%s,%s,'aprobado',%s,%s)""",
                          (legajo, fecha_sal.strftime("%Y-%m-%d"), hasta.strftime("%Y-%m-%d"),
                           obs or None, u["username"], u["username"]))
                conn.commit(); conn.close()
                st.success("✅ Vacaciones guardadas"); st.rerun()
