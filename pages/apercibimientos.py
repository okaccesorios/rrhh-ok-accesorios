import streamlit as st
from utils.database import get_conn, dict_cursor, log_auditoria
from utils.auth import usuario_actual
from datetime import date, timedelta
import calendar

TIPOS_SITUACION = [
    "Error en atención al cliente",
    "Incumplimiento de procedimientos",
    "Conflicto con compañeros",
    "Mal uso de recursos de la empresa",
    "Incumplimiento de horario reiterado",
    "Actitud inadecuada",
    "Otro (describir en observaciones)",
]
ESTADOS_APERC = ["pendiente_revision", "apercibido", "advertencia_verbal", "sin_sancion"]
ESTADOS_LABEL = {
    "pendiente_revision": "⏳ Pendiente revisión",
    "apercibido":         "🔴 Apercibido formalmente",
    "advertencia_verbal": "🟡 Advertencia verbal",
    "sin_sancion":        "🟢 Sin sanción",
}

def _init_tabla():
    conn = get_conn()
    c = dict_cursor(conn)
    c.execute("""CREATE TABLE IF NOT EXISTS apercibimientos (
        id           SERIAL PRIMARY KEY,
        legajo       TEXT NOT NULL,
        fecha        TEXT NOT NULL,
        tipo         TEXT NOT NULL,
        descripcion  TEXT,
        reportado_por TEXT,
        estado       TEXT DEFAULT 'pendiente_revision',
        resolucion   TEXT,
        resuelto_por TEXT,
        creado_en    TEXT DEFAULT (NOW()::text),
        resuelto_en  TEXT
    )""")
    conn.commit()
    conn.close()

def show():
    _init_tabla()

    st.markdown("""<div class="main-header"><div>
    <h1>⚠️ Apercibimientos y Alertas</h1>
    <span>Seguimiento de conductas, ausencias reiteradas y tardanzas</span>
    </div></div>""", unsafe_allow_html=True)

    u = usuario_actual()
    tab1, tab2, tab3 = st.tabs(["🚨 Alertas del mes", "📋 Apercibimientos", "➕ Reportar situación"])

    # ── TAB 1: ALERTAS AUTOMÁTICAS ────────────────────────────
    with tab1:
        st.markdown("#### Alertas automáticas basadas en marcaciones")

        col1, col2 = st.columns(2)
        with col1:
            hoy = date.today()
            anio = st.number_input("Año", value=hoy.year, min_value=2024, max_value=2030, key="a_anio")
            mes  = st.selectbox("Mes", list(range(1,13)), index=hoy.month-1, key="a_mes",
                                format_func=lambda m: ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                                "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][m-1])
        with col2:
            sector_f = st.selectbox("Sector", ["Todos","Administración","Compras",
                                               "Montecaseros","Local calle San Juan","Logistica"],
                                    key="a_sec")

        periodo = f"{anio}-{mes:02d}"

        conn = get_conn()
        cur  = dict_cursor(conn)

        # Feriados
        cur.execute("SELECT fecha FROM feriados WHERE fecha LIKE %s", (f"{periodo}%",))
        feriados = {r["fecha"] for r in cur.fetchall()}

        # Novedades aprobadas
        cur.execute("""SELECT legajo, fecha_desde, fecha_hasta FROM novedades
                       WHERE estado IN ('aprobado','enviado')
                       AND (fecha_desde LIKE %s OR fecha_hasta LIKE %s)""",
                    (f"{periodo}%", f"{periodo}%"))
        novs_aprobadas = set()
        for r in cur.fetchall():
            d = date.fromisoformat(r["fecha_desde"])
            h = date.fromisoformat(r["fecha_hasta"]) if r["fecha_hasta"] else d
            while d <= h:
                novs_aprobadas.add((str(r["legajo"]), str(d)))
                d += timedelta(days=1)

        # Colaboradores
        sql_c = "SELECT legajo, apellido||' '||nombre as nombre, sector, entrada, horario_flexible FROM colaboradores WHERE activo=1"
        params_c = []
        if sector_f != "Todos":
            sql_c += " AND sector=%s"; params_c.append(sector_f)
        sql_c += " ORDER BY sector, apellido"
        cur.execute(sql_c, params_c)
        colaboradores = cur.fetchall()

        # Marcaciones del mes
        cur.execute("SELECT legajo, fecha, ingreso FROM marcaciones WHERE fecha LIKE %s", (f"{periodo}%",))
        marc_dict = {}
        for r in cur.fetchall():
            marc_dict.setdefault(str(r["legajo"]), {})[r["fecha"]] = r["ingreso"]

        conn.close()

        primer = date(anio, mes, 1)
        ultimo = date(anio, mes, calendar.monthrange(anio, mes)[1])

        alertas_ausencias = []
        alertas_tardanzas = []

        for col in colaboradores:
            legajo = str(col["legajo"])
            es_flex = bool(col.get("horario_flexible", 0))
            ent_cfg = col.get("entrada") or "09:00"
            marc = marc_dict.get(legajo, {})

            ausencias_sin_just = []
            tardanzas = []

            d = primer
            while d <= ultimo:
                dow = d.weekday()
                if dow >= 5:  # sáb/dom
                    d += timedelta(days=1); continue
                fecha_str = str(d)
                if fecha_str in feriados:
                    d += timedelta(days=1); continue

                ingreso = marc.get(fecha_str)
                tiene_nov = (legajo, fecha_str) in novs_aprobadas

                if not ingreso and not tiene_nov and not es_flex:
                    ausencias_sin_just.append(d.strftime("%d/%m"))
                elif ingreso and not es_flex:
                    # Tardanza
                    try:
                        h_ing = int(ingreso[:2])*60+int(ingreso[3:5])
                        h_cfg = int(ent_cfg[:2])*60+int(ent_cfg[3:5])
                        diff  = h_ing - h_cfg
                        if diff > 5:
                            tardanzas.append((d.strftime("%d/%m"), diff))
                    except: pass
                d += timedelta(days=1)

            # Alertas ausencias
            if len(ausencias_sin_just) >= 3:
                alertas_ausencias.append({
                    "legajo": legajo, "nombre": col["nombre"], "sector": col["sector"],
                    "cant": len(ausencias_sin_just), "fechas": ", ".join(ausencias_sin_just[-5:]),
                    "nivel": "apercibimiento"
                })
            elif len(ausencias_sin_just) >= 1:
                alertas_ausencias.append({
                    "legajo": legajo, "nombre": col["nombre"], "sector": col["sector"],
                    "cant": len(ausencias_sin_just), "fechas": ", ".join(ausencias_sin_just),
                    "nivel": "mail"
                })

            # Alertas tardanzas
            if tardanzas:
                total_min = sum(t[1] for t in tardanzas)
                alertas_tardanzas.append({
                    "legajo": legajo, "nombre": col["nombre"], "sector": col["sector"],
                    "cant": len(tardanzas), "total_min": total_min,
                    "detalle": ", ".join(f"{t[0]} ({t[1]}min)" for t in tardanzas[-3:])
                })

        # Mostrar alertas ausencias
        st.markdown("##### 🚫 Ausencias sin justificar")
        if alertas_ausencias:
            for a in sorted(alertas_ausencias, key=lambda x: -x["cant"]):
                if a["nivel"] == "apercibimiento":
                    bg="#FFF0F0"; borde="#C00000"; icono="🔴"; accion="REALIZAR APERCIBIMIENTO"
                else:
                    bg="#FFF8E1"; borde="#E6AC00"; icono="📧"; accion="Enviar mail"

                st.markdown(f"""
                <div style="background:{bg};border-left:4px solid {borde};
                     padding:0.6rem 1rem;border-radius:4px;margin-bottom:0.4rem;">
                  {icono} <strong>{a['nombre']}</strong>
                  <span style="color:#666;"> · {a['sector']}</span>
                  <span style="float:right;font-weight:700;color:{borde};">
                    {a['cant']} ausencia(s) → {accion}
                  </span><br>
                  <span style="font-size:0.82rem;color:#555;">Días: {a['fechas']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-ok">✅ Sin alertas de ausencias este mes</div>',
                        unsafe_allow_html=True)

        # Mostrar alertas tardanzas
        st.markdown("##### ⏰ Tardanzas del mes")
        if alertas_tardanzas:
            for t in sorted(alertas_tardanzas, key=lambda x: -x["total_min"]):
                h, m = divmod(t["total_min"], 60)
                total_fmt = f"{h}h {m:02d}m" if h else f"{m}m"
                color = "#C00000" if t["cant"] >= 5 else "#E6AC00"
                st.markdown(f"""
                <div style="background:white;border-left:4px solid {color};border:1px solid #eee;
                     padding:0.6rem 1rem;border-radius:4px;margin-bottom:0.4rem;">
                  ⏰ <strong>{t['nombre']}</strong>
                  <span style="color:#666;"> · {t['sector']}</span>
                  <span style="float:right;font-weight:700;color:{color};">
                    {t['cant']} tardanza(s) · {total_fmt} acumulados
                  </span><br>
                  <span style="font-size:0.82rem;color:#555;">Últimas: {t['detalle']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-ok">✅ Sin tardanzas registradas este mes</div>',
                        unsafe_allow_html=True)

    # ── TAB 2: APERCIBIMIENTOS ────────────────────────────────
    with tab2:
        st.markdown("#### Registro de apercibimientos y situaciones")
        col1, col2 = st.columns(2)
        with col1:
            filtro_estado = st.selectbox("Estado", ["Todos"]+list(ESTADOS_LABEL.keys()),
                                         format_func=lambda x: "Todos" if x=="Todos" else ESTADOS_LABEL[x])
        with col2:
            filtro_leg2 = st.text_input("Legajo (opcional)", key="ap_leg")

        conn = get_conn()
        cur  = dict_cursor(conn)
        sql = """SELECT a.*, c.apellido||' '||c.nombre as nombre, c.sector
                 FROM apercibimientos a JOIN colaboradores c ON c.legajo=a.legajo
                 WHERE 1=1"""
        params = []
        if filtro_estado != "Todos": sql += " AND a.estado=%s"; params.append(filtro_estado)
        if filtro_leg2.strip(): sql += " AND a.legajo=%s"; params.append(filtro_leg2.strip())
        sql += " ORDER BY a.creado_en DESC LIMIT 50"
        cur.execute(sql, params)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            st.info("No hay registros para los filtros seleccionados.")
        else:
            for r in rows:
                estado_label = ESTADOS_LABEL.get(r["estado"], r["estado"])
                with st.expander(f"{estado_label} — **{r['nombre']}** | {r['fecha']} | {r['tipo']}"):
                    c1, c2 = st.columns([3,1])
                    with c1:
                        st.write(f"**Sector:** {r['sector']}")
                        st.write(f"**Tipo:** {r['tipo']}")
                        if r["descripcion"]: st.write(f"**Descripción:** {r['descripcion']}")
                        st.caption(f"Reportado por {r['reportado_por'] or '-'} — {r['creado_en']}")
                        if r["resolucion"]: st.write(f"**Resolución:** {r['resolucion']}")
                        if r["resuelto_por"]: st.caption(f"Resuelto por {r['resuelto_por']}")
                    with c2:
                        if r["estado"] == "pendiente_revision" and u["rol"] in ("admin","rrhh"):
                            nuevo_estado = st.selectbox("Resolver como",
                                list(ESTADOS_LABEL.keys())[1:],
                                format_func=lambda x: ESTADOS_LABEL[x],
                                key=f"res_{r['id']}")
                            resolucion = st.text_area("Observación", key=f"obs_{r['id']}", height=60)
                            if st.button("✅ Resolver", key=f"btn_{r['id']}", type="primary"):
                                conn2 = get_conn(); c2b = dict_cursor(conn2)
                                c2b.execute("""UPDATE apercibimientos
                                    SET estado=%s, resolucion=%s, resuelto_por=%s, resuelto_en=NOW()::text
                                    WHERE id=%s""",
                                    (nuevo_estado, resolucion, u["username"], r["id"]))
                                conn2.commit(); conn2.close()
                                log_auditoria(u["username"], "RESOLVER_APERCIBIMIENTO", "apercibimientos", r["id"])
                                st.rerun()

    # ── TAB 3: REPORTAR SITUACIÓN ─────────────────────────────
    with tab3:
        st.markdown("#### Reportar una situación")
        st.markdown("""<div class="alert-info">
          📌 Cualquier miembro del equipo puede reportar una situación.
          RRHH la revisará y decidirá si corresponde un apercibimiento formal, advertencia verbal o ninguna sanción.
        </div>""", unsafe_allow_html=True)

        conn = get_conn()
        cur  = dict_cursor(conn)
        cur.execute("SELECT legajo, apellido||' '||nombre as nombre FROM colaboradores WHERE activo=1 ORDER BY apellido")
        colab_list = {f"{r['legajo']} — {r['nombre']}": r["legajo"] for r in cur.fetchall()}
        conn.close()

        col1, col2 = st.columns(2)
        with col1:
            sel_col  = st.selectbox("Colaborador involucrado *", list(colab_list.keys()))
            fecha_ap = st.date_input("Fecha del hecho *", value=date.today())
            tipo_ap  = st.selectbox("Tipo de situación *", TIPOS_SITUACION)
        with col2:
            descripcion_ap = st.text_area("Descripción detallada *", height=150,
                placeholder="Describí qué pasó, cuándo, dónde y quiénes estuvieron involucrados...")
            reportado_por  = st.text_input("Tu nombre (quien reporta)", value=u.get("nombre",""))

        st.markdown("""<div class="alert-warn">
          ⚠️ Esta información será revisada confidencialmente por RRHH antes de tomar cualquier decisión.
        </div>""", unsafe_allow_html=True)

        if st.button("📨 Enviar reporte", type="primary", use_container_width=True):
            if not descripcion_ap.strip():
                st.error("La descripción es obligatoria.")
            else:
                legajo = colab_list[sel_col]
                conn2 = get_conn(); c2 = dict_cursor(conn2)
                c2.execute("""INSERT INTO apercibimientos
                    (legajo, fecha, tipo, descripcion, reportado_por, estado)
                    VALUES (%s,%s,%s,%s,%s,'pendiente_revision')""",
                    (legajo, str(fecha_ap), tipo_ap, descripcion_ap.strip(),
                     reportado_por or u.get("nombre",u["username"])))
                conn2.commit(); conn2.close()
                log_auditoria(u["username"], "CREAR_APERCIBIMIENTO", "apercibimientos",
                              detalle=f"{legajo} | {tipo_ap}")
                st.success("✅ Reporte enviado. RRHH lo revisará a la brevedad.")
                st.rerun()
