import streamlit as st
from utils.database import get_conn
from datetime import date, timedelta

MESES_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
            7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>📊 Dashboard</h1>
      <span>Resumen del día y del mes en curso</span></div>
    </div>""", unsafe_allow_html=True)

    hoy    = date.today()
    ayer    = hoy - timedelta(days=1)
    periodo = hoy.strftime("%Y-%m")
    conn   = get_conn()

    # ── Días transcurridos y feriados del mes ─────────────────
    primer_dia = hoy.replace(day=1)
    if hoy.month == 12:
        ultimo_dia = date(hoy.year+1,1,1) - timedelta(days=1)
    else:
        ultimo_dia = date(hoy.year, hoy.month+1, 1) - timedelta(days=1)

    dias_habiles_transcurridos = sum(
        1 for i in range((hoy - primer_dia).days + 1)
        if (primer_dia + timedelta(i)).weekday() < 6
    )
    dias_habiles_totales = sum(
        1 for i in range((ultimo_dia - primer_dia).days + 1)
        if (primer_dia + timedelta(i)).weekday() < 6
    )

    feriados_mes = conn.execute(
        "SELECT fecha, descripcion FROM feriados WHERE fecha LIKE %s ORDER BY fecha",
        (f"{periodo}%",)
    ).fetchall()
    feriados_set = {r["fecha"] for r in feriados_mes}

    # ── Métricas superiores ───────────────────────────────────
    total_colab  = conn.execute("SELECT COUNT(*) FROM colaboradores WHERE activo=1").fetchone()[0]
    pendientes   = conn.execute("SELECT COUNT(*) FROM novedades WHERE estado='pendiente'").fetchone()[0]

    # Sin marcar HOY (excluye sábado y domingo)
    sin_marcar_hoy = 0
    ausentes_hoy_list = []
    if ayer.weekday() < 6 and ayer.strftime("%Y-%m-%d") not in feriados_set:
        rows_sin = conn.execute("""
            SELECT c.legajo, c.apellido||' '||c.nombre as nombre, c.sector
            FROM colaboradores c
            WHERE c.activo=1
            AND c.legajo NOT IN (
                SELECT legajo FROM marcaciones WHERE fecha=?
            )
            ORDER BY c.sector, c.apellido
        """, (ayer.strftime("%Y-%m-%d"),)).fetchall()
        sin_marcar_hoy = len(rows_sin)
        ausentes_hoy_list = [dict(r) for r in rows_sin]

    # Tardanzas del mes
    tard_mes = conn.execute("""
        SELECT COUNT(DISTINCT m.legajo) as n
        FROM marcaciones m JOIN colaboradores c ON c.legajo=m.legajo
        WHERE m.fecha LIKE %s
        AND m.ingreso IS NOT NULL
        AND TIME(m.ingreso) > TIME(
            CASE c.sector
                WHEN 'Administración' THEN '08:35'
                WHEN 'Compras' THEN '09:05'
                ELSE '09:05'
            END
        )
    """, (f"{periodo}%",)).fetchone()[0]

    # HE del mes (registros con egreso tardío — aproximación)
    he_mes = conn.execute("""
        SELECT COUNT(DISTINCT legajo) FROM marcaciones
        WHERE fecha LIKE %s AND egreso > '18:00'
    """, (f"{periodo}%",)).fetchone()[0]

    # Adelantos del mes
    adel_rows = conn.execute("""
        SELECT SUM(monto) as total, COUNT(*) as cant
        FROM adelantos WHERE periodo=? AND tipo='adelanto'
    """, (periodo,)).fetchone()
    adel_total = adel_rows["total"] or 0
    adel_cant  = adel_rows["cant"] or 0

    # ── Fila de métricas ─────────────────────────────────────
    cols = st.columns(5)
    metricas = [
        (f"{hoy.day}/{hoy.month}",           f"Hoy — {MESES_ES[hoy.month]} {hoy.year}", "blue"),
        (f"{dias_habiles_transcurridos}/{dias_habiles_totales}", "Días hábiles del mes",  "blue"),
        (str(sin_marcar_hoy),                "Sin marcar ayer",                           "red" if sin_marcar_hoy else "green"),
        (str(pendientes),                    "Novedades pendientes",                     "yel"),
        (f"${adel_total:,.0f}",              f"Adelantos del mes ({adel_cant})",         "blue"),
    ]
    for col, (val, label, cls) in zip(cols, metricas):
        with col:
            st.markdown(f"""
            <div class="metric-card {cls}">
              <h3>{val}</h3><p>{label}</p>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")

    # ── Dos columnas principales ──────────────────────────────
    col_izq, col_der = st.columns(2)

    # ── SIN MARCAR HOY ────────────────────────────────────────
    with col_izq:
        st.markdown(f"#### ❌ Sin marcar ayer — {ayer.strftime('%d/%m/%Y')}")
        if ayer.weekday() == 6:
            st.info("Hoy es domingo.")
        elif ayer.strftime("%Y-%m-%d") in feriados_set:
            desc_feriado = next((r["descripcion"] for r in feriados_mes
                                  if r["fecha"] == ayer.strftime("%Y-%m-%d")), "Feriado")
            st.markdown(f'<div class="alert-info">📅 Hoy es feriado: <strong>{desc_feriado}</strong></div>',
                        unsafe_allow_html=True)
        elif not ausentes_hoy_list:
            st.markdown('<div class="alert-ok">✅ Todos marcaron hoy</div>', unsafe_allow_html=True)
        else:
            # Separar los que tienen novedad aprobada de los ausentes sin justificación
            nov_aprobadas = {}
            for r in conn.execute("""
                SELECT legajo, tipo FROM novedades
                WHERE estado IN ('aprobado','enviado')
                AND (fecha_desde <= %s AND (fecha_hasta >= %s OR fecha_hasta IS NULL))
            """, (ayer.strftime("%Y-%m-%d"), ayer.strftime("%Y-%m-%d"))).fetchall():
                nov_aprobadas[str(r["legajo"])] = r["tipo"]

            for emp in ausentes_hoy_list:
                nov = nov_aprobadas.get(str(emp["legajo"]))
                if nov:
                    bg = "#E8F5E9"; icono = "📋"; estado = nov
                else:
                    bg = "#FFF0F0"; icono = "❌"; estado = "Sin justificación"
                st.markdown(f"""
                <div style="background:{bg};border-left:3px solid {'#375623' if nov else '#C00000'};
                     padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;font-size:0.85rem;">
                  {icono} <strong>{emp['nombre']}</strong>
                  <span style="color:#666;font-size:0.78rem;"> · {emp['sector']}</span><br>
                  <span style="color:#555;font-size:0.78rem;">{estado}</span>
                </div>""", unsafe_allow_html=True)

    # ── NOVEDADES PENDIENTES ───────────────────────────────────
    with col_der:
        st.markdown("#### ⏳ Novedades pendientes de aprobación")
        rows_nov = conn.execute("""
            SELECT n.id, c.apellido||' '||c.nombre as nombre, c.sector,
                   n.tipo, n.fecha_desde, n.creado_en
            FROM novedades n JOIN colaboradores c ON c.legajo=n.legajo
            WHERE n.estado='pendiente'
            ORDER BY n.creado_en DESC LIMIT 10
        """).fetchall()
        if rows_nov:
            for r in rows_nov:
                st.markdown(f"""
                <div style="background:#FFF8E1;border-left:3px solid #E6AC00;
                     padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;font-size:0.85rem;">
                  🟡 <strong>{r['nombre']}</strong>
                  <span style="color:#666;font-size:0.78rem;"> · {r['sector']}</span><br>
                  <span style="color:#555;">{r['tipo']}</span>
                  <span style="color:#aaa;font-size:0.76rem;"> — desde {r['fecha_desde']}</span>
                </div>""", unsafe_allow_html=True)
            if st.button("📋 Ir a Novedades para aprobar", use_container_width=True):
                st.session_state["pagina"] = "novedades"
                st.rerun()
        else:
            st.markdown('<div class="alert-ok">✅ No hay novedades pendientes</div>',
                        unsafe_allow_html=True)

    st.markdown("---")
    col3, col4, col5 = st.columns(3)

    # ── TARDANZAS DEL MES ─────────────────────────────────────
    with col3:
        st.markdown("#### ⏰ Tardanzas acumuladas")
        rows_tard = conn.execute("""
            SELECT c.apellido||' '||c.nombre as nombre, c.sector,
                   COUNT(*) as cant
            FROM marcaciones m JOIN colaboradores c ON c.legajo=m.legajo
            WHERE m.fecha LIKE %s
            AND m.ingreso IS NOT NULL
            AND TIME(m.ingreso) > TIME(
                CASE c.sector
                    WHEN 'Administración' THEN '08:35'
                    ELSE '09:05' END
            )
            GROUP BY m.legajo ORDER BY cant DESC LIMIT 8
        """, (f"{periodo}%",)).fetchall()
        if rows_tard:
            for r in rows_tard:
                color = "#C00000" if r["cant"] >= 3 else "#E6AC00"
                st.markdown(f"""
                <div style="background:white;border-left:3px solid {color};border:1px solid #eee;
                     padding:0.35rem 0.7rem;border-radius:4px;margin-bottom:0.25rem;font-size:0.82rem;">
                  <strong>{r['nombre']}</strong>
                  <span style="float:right;font-weight:700;color:{color};">{r['cant']}x</span><br>
                  <span style="color:#888;">{r['sector']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-ok">✅ Sin tardanzas registradas</div>',
                        unsafe_allow_html=True)

    # ── ADELANTOS DEL MES ─────────────────────────────────────
    with col4:
        st.markdown("#### 💵 Adelantos del mes")
        rows_adel = conn.execute("""
            SELECT c.apellido||' '||c.nombre as nombre, a.tipo,
                   SUM(a.monto) as total
            FROM adelantos a JOIN colaboradores c ON c.legajo=a.legajo
            WHERE a.periodo=?
            GROUP BY a.legajo, a.tipo ORDER BY total DESC LIMIT 8
        """, (periodo,)).fetchall()
        TIPO_ICON = {"adelanto":"💵","descuento_mercaderia":"🛍️","otro":"📝","sancion":"⚠️"}
        if rows_adel:
            for r in rows_adel:
                icon = TIPO_ICON.get(r["tipo"],"💰")
                st.markdown(f"""
                <div style="background:white;border:1px solid #eee;border-left:3px solid #2E75B6;
                     padding:0.35rem 0.7rem;border-radius:4px;margin-bottom:0.25rem;font-size:0.82rem;">
                  {icon} <strong>{r['nombre']}</strong>
                  <span style="float:right;font-weight:700;">${r['total']:,.0f}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Sin adelantos registrados este mes.")

    # ── FERIADOS DEL MES ─────────────────────────────────────
    with col5:
        st.markdown("#### 📅 Feriados del mes")
        if feriados_mes:
            for f in feriados_mes:
                fecha_f = date.fromisoformat(f["fecha"])
                es_pasado = fecha_f < hoy
                es_hoy    = fecha_f == hoy
                color = "#BDBDBD" if es_pasado else ("#2E75B6" if es_hoy else "#375623")
                icono = "✅" if es_pasado else ("📍" if es_hoy else "📅")
                st.markdown(f"""
                <div style="background:white;border:1px solid #eee;border-left:3px solid {color};
                     padding:0.35rem 0.7rem;border-radius:4px;margin-bottom:0.25rem;font-size:0.82rem;">
                  {icono} <strong>{fecha_f.strftime('%d/%m')}</strong> — {f['descripcion']}
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Sin feriados este mes.")

    conn.close()
