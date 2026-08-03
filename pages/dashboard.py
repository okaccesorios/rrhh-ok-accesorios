import streamlit as st
from utils.database import get_conn
from datetime import date

def show():
    st.markdown("""
    <div class="main-header">
      <div>
        <h1>📊 Dashboard</h1>
        <span>Indicadores del período actual</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    conn = get_conn()
    hoy = date.today()
    periodo = hoy.strftime("%Y-%m")

    # ── Métricas globales ─────────────────────────────────────
    total_colab = conn.execute("SELECT COUNT(*) FROM colaboradores WHERE activo=1").fetchone()[0]
    pendientes  = conn.execute("SELECT COUNT(*) FROM novedades WHERE estado='pendiente'").fetchone()[0]
    total_marc  = conn.execute("SELECT COUNT(DISTINCT legajo) FROM marcaciones WHERE fecha LIKE ?",
                               (f"{periodo}%",)).fetchone()[0]
    ausentes_hoy = conn.execute(
        """SELECT COUNT(DISTINCT c.legajo) FROM colaboradores c
           WHERE c.activo=1
           AND c.legajo NOT IN (SELECT legajo FROM marcaciones WHERE fecha=?)""",
        (hoy.strftime("%Y-%m-%d"),)
    ).fetchone()[0]

    cols = st.columns(4)
    metricas = [
        ("total_colab",  "👥 Colaboradores activos", str(total_colab),  "blue"),
        ("total_marc",   "✅ Con marcaciones en el mes", str(total_marc), "green"),
        ("pendientes",   "⏳ Novedades pendientes",   str(pendientes),  "yel"),
        ("ausentes_hoy", "❌ Sin marcar hoy",         str(ausentes_hoy),"red"),
    ]
    for col, (_, label, val, cls) in zip(cols, metricas):
        with col:
            st.markdown(f"""
            <div class="metric-card {cls}">
              <h3>{val}</h3>
              <p>{label}</p>
            </div>""", unsafe_allow_html=True)

    st.markdown("---")
    c1, c2 = st.columns(2)

    # ── Novedades pendientes ───────────────────────────────────
    with c1:
        st.markdown("#### 📋 Novedades pendientes de aprobación")
        rows = conn.execute("""
            SELECT n.id, c.apellido||' '||c.nombre as nombre, n.tipo, n.fecha_desde, n.creado_por
            FROM novedades n JOIN colaboradores c ON c.legajo=n.legajo
            WHERE n.estado='pendiente'
            ORDER BY n.creado_en DESC LIMIT 10
        """).fetchall()
        if rows:
            for r in rows:
                st.markdown(f"""
                <div style="background:#FFF8E1;border-left:3px solid #E6AC00;
                     padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;font-size:0.85rem;">
                  <strong>{r['nombre']}</strong> — {r['tipo']}<br>
                  <span style="color:#888;">Desde {r['fecha_desde']} · Cargado por {r['creado_por'] or '-'}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-ok">✅ No hay novedades pendientes</div>', unsafe_allow_html=True)

    # ── Últimas importaciones ──────────────────────────────────
    with c2:
        st.markdown("#### ⏱️ Últimas importaciones del reloj")
        rows2 = conn.execute("""
            SELECT fuente, COUNT(*) as registros, MAX(importado_en) as ultima
            FROM marcaciones
            GROUP BY fuente ORDER BY ultima DESC LIMIT 8
        """).fetchall()
        if rows2:
            for r in rows2:
                st.markdown(f"""
                <div style="background:#EBF5FB;border-left:3px solid #2E75B6;
                     padding:0.4rem 0.8rem;border-radius:4px;margin-bottom:0.3rem;font-size:0.85rem;">
                  <strong>{r['fuente'] or 'Sin nombre'}</strong> — {r['registros']} registros<br>
                  <span style="color:#888;">{r['ultima']}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="alert-warn">⚠️ Aún no se importaron marcaciones este mes</div>',
                        unsafe_allow_html=True)

    st.markdown("---")

    # ── Resumen por sector ─────────────────────────────────────
    st.markdown("#### 🏢 Colaboradores por sector")
    sectores = conn.execute("""
        SELECT sector, COUNT(*) as total FROM colaboradores
        WHERE activo=1 GROUP BY sector ORDER BY total DESC
    """).fetchall()
    cols_sec = st.columns(len(sectores))
    colores = ["#2E75B6","#375623","#7D3C00","#4A235A","#1F3864"]
    for i, (col, row) in enumerate(zip(cols_sec, sectores)):
        with col:
            color = colores[i % len(colores)]
            st.markdown(f"""
            <div style="background:white;border:1px solid #e0e0e0;border-top:4px solid {color};
                 border-radius:6px;padding:0.8rem;text-align:center;">
              <div style="font-size:1.4rem;font-weight:700;color:{color};">{row['total']}</div>
              <div style="font-size:0.75rem;color:#555;">{row['sector']}</div>
            </div>""", unsafe_allow_html=True)

    conn.close()
