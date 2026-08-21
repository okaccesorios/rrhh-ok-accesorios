import streamlit as st
from utils.database import get_conn, log_auditoria
from utils.auth import usuario_actual
from utils.importar import importar_vacaciones
from datetime import date, timedelta

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>🏖️ Vacaciones</h1>
      <span>Importá el cuadro de vacaciones o registrá períodos manualmente</span></div>
    </div>""", unsafe_allow_html=True)

    u = usuario_actual()
    tab1, tab2, tab3 = st.tabs(["📥 Importar cuadro", "📋 Ver vacaciones", "➕ Cargar manual"])

    # ── TAB 1: Importar ───────────────────────────────────────
    with tab1:
        st.markdown("#### Importar desde el cuadro de vacaciones Excel")
        st.markdown("""
        <div class="alert-info">
          📌 El sistema lee la hoja <strong>Resumen</strong> del Excel de vacaciones.<br>
          Formato: Apellido y nombre · Salida · Reincorp · Días · (Salida2 · Reincorp2 si hay segunda tanda)<br>
          Las vacaciones se importan como novedades <strong>aprobadas automáticamente</strong>.
        </div>""", unsafe_allow_html=True)

        archivo = st.file_uploader("Subí el Excel de vacaciones", type=["xlsx","xls"],
                                   label_visibility="collapsed")
        if archivo:
            if st.button("🚀 Importar vacaciones", type="primary", use_container_width=True):
                with st.spinner("Procesando..."):
                    imp, omit, e, errs = importar_vacaciones(
                        archivo.read(), archivo.name, u["username"]
                    )
                if e == 0:
                    st.success(f"✅ {imp} períodos de vacaciones importados. {omit} ya existían.")
                else:
                    st.warning(f"⚠️ {imp} importados · {omit} omitidos · {e} con errores:")
                    for err in errs[:10]:
                        st.caption(f"· {err}")

    # ── TAB 2: Ver vacaciones ─────────────────────────────────
    with tab2:
        col1, col2 = st.columns(2)
        with col1:
            anio = st.number_input("Año", value=date.today().year, min_value=2024, max_value=2030)
        with col2:
            filtro_sector = st.selectbox("Sector", ["Todos","Administración","Compras",
                                                     "Montecaseros","Local calle San Juan","Logistica"])
        conn = get_conn()
        q = """
            SELECT n.*, c.apellido||' '||c.nombre as nombre, c.sector
            FROM novedades n JOIN colaboradores c ON c.legajo=n.legajo
            WHERE n.tipo='Vacaciones'
            AND (n.fecha_desde LIKE %s OR n.fecha_hasta LIKE %s)
            ORDER BY n.fecha_desde
        """
        rows = conn.execute(q, (f"{anio}%", f"{anio}%")).fetchall()

        if filtro_sector != "Todos":
            rows = [r for r in rows if r["sector"] == filtro_sector]

        conn.close()

        if rows:
            # Resumen por colaborador
            resumen = {}
            for r in rows:
                key = r["nombre"]
                if key not in resumen:
                    resumen[key] = {"sector": r["sector"], "periodos": [], "total_dias": 0}
                desde = date.fromisoformat(r["fecha_desde"])
                hasta = date.fromisoformat(r["fecha_hasta"]) if r["fecha_hasta"] else desde
                dias = (hasta - desde).days + 1
                resumen[key]["periodos"].append((desde, hasta, dias, r["estado"]))
                resumen[key]["total_dias"] += dias

            st.caption(f"{len(resumen)} colaboradores con vacaciones en {anio}")
            st.markdown("---")

            for nombre, datos in sorted(resumen.items(), key=lambda x: x[1]["sector"]):
                estado_badge = "🟢" if all(p[3]=="aprobado" for p in datos["periodos"]) else "🟡"
                with st.expander(f"{estado_badge} **{nombre}** | {datos['sector']} — {datos['total_dias']} días totales"):
                    for desde, hasta, dias, estado in datos["periodos"]:
                        hoy = date.today()
                        if hasta < hoy:
                            icono = "✅ Tomadas"
                        elif desde <= hoy <= hasta:
                            icono = "🏖️ En curso"
                        else:
                            icono = "📅 Programadas"
                        st.markdown(f"""
                        <div style="background:white;border-left:3px solid #2E75B6;border:1px solid #eee;
                             padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;font-size:0.85rem;">
                          {icono} — Desde <strong>{desde.strftime('%d/%m/%Y')}</strong>
                          hasta <strong>{hasta.strftime('%d/%m/%Y')}</strong>
                          — <strong>{dias} días</strong>
                          <span style="float:right;color:#888;">{estado}</span>
                        </div>""", unsafe_allow_html=True)
        else:
            st.info(f"No hay vacaciones registradas para {anio}.")

    # ── TAB 3: Manual ─────────────────────────────────────────
    with tab3:
        st.markdown("#### Cargar vacaciones manualmente")
        conn = get_conn()
        colab = {f"{r['legajo']} — {r['apellido']} {r['nombre']}": r["legajo"]
                 for r in conn.execute(
                     "SELECT legajo,apellido,nombre FROM colaboradores WHERE activo=1 ORDER BY apellido"
                 ).fetchall()}
        conn.close()

        col1, col2 = st.columns(2)
        with col1:
            sel       = st.selectbox("Colaborador *", list(colab.keys()))
            fecha_sal = st.date_input("Fecha de salida *", value=date.today())
        with col2:
            fecha_rei = st.date_input("Fecha de reincorporación *",
                                      value=date.today() + timedelta(days=14))
            obs       = st.text_input("Observación (opcional)")

        if fecha_rei > fecha_sal:
            hasta = fecha_rei - timedelta(days=1)
            dias  = (hasta - fecha_sal).days + 1
            st.markdown(f"""
            <div class="alert-info">
              📅 Período: <strong>{fecha_sal.strftime('%d/%m/%Y')}</strong> al
              <strong>{hasta.strftime('%d/%m/%Y')}</strong> — <strong>{dias} días hábiles aprox.</strong>
            </div>""", unsafe_allow_html=True)

        if st.button("💾 Guardar vacaciones", type="primary"):
            if fecha_rei <= fecha_sal:
                st.error("La fecha de reincorporación debe ser posterior a la de salida.")
            else:
                hasta = fecha_rei - timedelta(days=1)
                legajo = colab[sel]
                conn = get_conn()
                conn.execute("""INSERT INTO novedades
                    (legajo, tipo, fecha_desde, fecha_hasta, descripcion, estado, creado_por, aprobado_por)
                    VALUES (%s,%s,%s,%s,%s,'aprobado',%s,%s)""",
                    (legajo, "Vacaciones",
                     fecha_sal.strftime("%Y-%m-%d"),
                     hasta.strftime("%Y-%m-%d"),
                     obs or None, u["username"], u["username"]))
                conn.commit(); conn.close()
                log_auditoria(u["username"], "CREAR_VACACIONES", "novedades",
                              detalle=f"{legajo} | {fecha_sal} → {hasta}")
                st.success(f"✅ Vacaciones guardadas: {fecha_sal.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}")
                st.rerun()
