import streamlit as st
from utils.database import get_conn, dict_cursor
from datetime import date, timedelta

MESES_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
            7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

def qry(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchall()

def qone(conn, sql, params=()):
    c = dict_cursor(conn)
    c.execute(sql, params)
    return c.fetchone()

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>📊 Dashboard</h1>
      <span>Resumen del día y del mes en curso</span></div>
    </div>""", unsafe_allow_html=True)

    hoy    = date.today()
    ayer   = hoy - timedelta(days=1)
    periodo = hoy.strftime("%Y-%m")
    conn   = get_conn()

    primer_dia = hoy.replace(day=1)
    if hoy.month == 12:
        ultimo_dia = date(hoy.year+1,1,1) - timedelta(days=1)
    else:
        ultimo_dia = date(hoy.year, hoy.month+1, 1) - timedelta(days=1)

    dias_hab_trans = sum(1 for i in range(max(0,(hoy-primer_dia).days+1))
                         if (primer_dia+timedelta(i)).weekday()<6)

    feriados_mes = qry(conn, "SELECT fecha, descripcion FROM feriados WHERE fecha LIKE %s ORDER BY fecha",
                       (f"{periodo}%",))
    feriados_set = {r["fecha"] for r in feriados_mes}

    total_colab = qone(conn, "SELECT COUNT(*) as n FROM colaboradores WHERE activo=1")["n"]
    pendientes  = qone(conn, "SELECT COUNT(*) as n FROM novedades WHERE estado='pendiente'")["n"]

    sin_marcar_hoy = 0
    ausentes_list  = []
    if ayer.weekday() < 6 and ayer.strftime("%Y-%m-%d") not in feriados_set:
        rows_sin = qry(conn, """
            SELECT c.legajo, c.apellido||' '||c.nombre as nombre, c.sector
            FROM colaboradores c
            WHERE c.activo=1
            AND c.legajo NOT IN (SELECT legajo FROM marcaciones WHERE fecha=%s)
            ORDER BY c.sector, c.apellido
        """, (ayer.strftime("%Y-%m-%d"),))
        sin_marcar_hoy = len(rows_sin)
        ausentes_list  = [dict(r) for r in rows_sin]

    adel = qone(conn, "SELECT COALESCE(SUM(monto),0) as total, COUNT(*) as cant FROM adelantos WHERE periodo=%s AND tipo='adelanto'", (periodo,))
    adel_total = float(adel["total"] or 0)
    adel_cant  = adel["cant"] or 0

    # ── Métricas ──────────────────────────────────────────────
    cols = st.columns(5)
    metricas = [
        (f"{hoy.day}/{hoy.month}", f"Hoy — {MESES_ES[hoy.month]} {hoy.year}", "blue"),
        (f"{dias_hab_trans}/{dias_hab_total}", "Días hábiles del mes", "blue"),
        (str(sin_marcar_hoy), "Sin marcar ayer", "red" if sin_marcar_hoy else "green"),
        (str(pendientes), "Novedades pendientes", "yel"),
        (f"${adel_total:,.0f}", f"Adelantos del mes ({adel_cant})", "blue"),
    ]
    for col, (val, label, cls) in zip(cols, metricas):
        with col:
            st.markdown(f'<div class="metric-card {cls}"><h3>{val}</h3><p>{label}</p></div>',
                        unsafe_allow_html=True)

    st.markdown("---")
    col_izq, col_der = st.columns(2)

    with col_izq:
        st.markdown(f"#### ❌ Sin marcar ayer — {ayer.strftime('%d/%m/%Y')}")
        if ayer.weekday() == 6:
            st.info("Ayer fue domingo.")
        elif ayer.strftime("%Y-%m-%d") in feriados_set:
            st.markdown('<div class="alert-info">📅 Ayer fue feriado.</div>', unsafe_allow_html=True)
        elif not ausentes_list:
            st.markdown('<div class="alert-ok">✅ Todos marcaron ayer</div>', unsafe_allow_html=True)
        else:
            nov_aprobadas = {str(r["legajo"]): r["tipo"] for r in qry(conn, """
                SELECT legajo, tipo FROM novedades
                WHERE estado IN ('aprobado','enviado')
                AND fecha_desde <= %s AND (fecha_hasta >= %s OR fecha_hasta IS NULL)
            """, (ayer.strftime("%Y-%m-%d"), ayer.strftime("%Y-%m-%d")))}

            for emp in ausentes_list:
                nov = nov_aprobadas.get(str(emp["legajo"]))
                bg = "#E8F5E9" if nov else "#FFF0F0"
                borde = "#375623" if nov else "#C00000"
                icono = "📋" if nov else "❌"
                estado = nov if nov else "Sin justificación"
                st.markdown(f"""
                <div style="background:{bg};border-left:3px solid {borde};
                     padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;font-size:0.85rem;">
                  {icono} <strong>{emp['nombre']}</strong>
                  <span style="color:#666;"> · {emp['sector']}</span><br>
                  <span style="color:#555;font-size:0.78rem;">{estado}</span>
                </div>""", unsafe_allow_html=True)

    with col_der:
        st.markdown("#### ⏳ Novedades pendientes")
        rows_nov = qry(conn, """
            SELECT n.id, c.apellido||' '||c.nombre as nombre, c.sector,
                   n.tipo, n.fecha_desde
            FROM novedades n JOIN colaboradores c ON c.legajo=n.legajo
            WHERE n.estado='pendiente' ORDER BY n.creado_en DESC LIMIT 10
        """)
        if rows_nov:
            for r in rows_nov:
                st.markdown(f"""
                <div style="background:#FFF8E1;border-left:3px solid #E6AC00;
                     padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;font-size:0.85rem;">
                  🟡 <strong>{r['nombre']}</strong> · {r['sector']}<br>
                  <span style="color:#555;">{r['tipo']}</span>
                  <span style="color:#aaa;font-size:0.76rem;"> — {r['fecha_desde']}</span>
                </div>""", unsafe_allow_html=True)
            if st.button("📋 Ir a Novedades", use_container_width=True):
                st.session_state["pagina"] = "novedades"; st.rerun()
        else:
            st.markdown('<div class="alert-ok">✅ Sin novedades pendientes</div>', unsafe_allow_html=True)

    st.markdown("---")
    col3, col4, col5 = st.columns(3)

    with col3:
        st.markdown("#### ⏰ Tardanzas acumuladas")
        rows_tard = qry(conn, """
            SELECT c.apellido||' '||c.nombre as nombre, c.sector, COUNT(*) as cant
            FROM marcaciones m JOIN colaboradores c ON c.legajo=m.legajo
            WHERE m.fecha LIKE %s AND m.ingreso IS NOT NULL
            AND m.ingreso > CASE c.sector
                WHEN 'Administración' THEN '08:35' ELSE '09:05' END
            GROUP BY m.legajo, c.apellido, c.nombre, c.sector
            ORDER BY cant DESC LIMIT 8
        """, (f"{periodo}%",))
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
            st.markdown('<div class="alert-ok">✅ Sin tardanzas</div>', unsafe_allow_html=True)

    with col4:
        st.markdown("#### 💵 Adelantos del mes")
        rows_adel = qry(conn, """
            SELECT c.apellido||' '||c.nombre as nombre, a.tipo, SUM(a.monto) as total
            FROM adelantos a JOIN colaboradores c ON c.legajo=a.legajo
            WHERE a.periodo=%s GROUP BY a.legajo, c.apellido, c.nombre, a.tipo
            ORDER BY total DESC LIMIT 8
        """, (periodo,))
        ICON = {"adelanto":"💵","descuento_mercaderia":"🛍️","otro":"📝","sancion":"⚠️"}
        if rows_adel:
            for r in rows_adel:
                st.markdown(f"""
                <div style="background:white;border:1px solid #eee;border-left:3px solid #2E75B6;
                     padding:0.35rem 0.7rem;border-radius:4px;margin-bottom:0.25rem;font-size:0.82rem;">
                  {ICON.get(r['tipo'],'💰')} <strong>{r['nombre']}</strong>
                  <span style="float:right;font-weight:700;">${float(r['total']):,.0f}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Sin adelantos este mes.")

    with col5:
        st.markdown("#### 📅 Feriados del mes")
        if feriados_mes:
            for f in feriados_mes:
                fecha_f = date.fromisoformat(f["fecha"])
                es_pas = fecha_f < hoy; es_hoy = fecha_f == hoy
                color = "#BDBDBD" if es_pas else ("#2E75B6" if es_hoy else "#375623")
                icono = "✅" if es_pas else ("📍" if es_hoy else "📅")
                st.markdown(f"""
                <div style="background:white;border:1px solid #eee;border-left:3px solid {color};
                     padding:0.35rem 0.7rem;border-radius:4px;margin-bottom:0.25rem;font-size:0.82rem;">
                  {icono} <strong>{fecha_f.strftime('%d/%m')}</strong> — {f['descripcion']}
                </div>""", unsafe_allow_html=True)
        else:
            st.info("Sin feriados este mes.")

    conn.close()
