import streamlit as st
from utils.database import get_conn, dict_cursor
from utils.auth import usuario_actual
from datetime import date, timedelta
import calendar
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

DIAS_ES = {"Mon":"Lun","Tue":"Mar","Wed":"Mié","Thu":"Jue","Fri":"Vie","Sat":"Sáb","Sun":"Dom"}

def _fc(h): return PatternFill("solid", fgColor=h)
def _ft(bold=False, sz=10, color="000000"): return Font(bold=bold, size=sz, color=color, name="Calibri")
def _al(h="center", v="center"): return Alignment(horizontal=h, vertical=v)
def _bd():
    s = Side(style="thin", color="BFBFBF")
    return Border(left=s, right=s, top=s, bottom=s)

def show():
    st.markdown("""<div class="main-header"><div><h1>📊 Reportes</h1>
    <span>Reportes de ausencias y asistencia para enviar semanalmente o mensualmente</span>
    </div></div>""", unsafe_allow_html=True)

    u = usuario_actual()
    tab1, tab2 = st.tabs(["📅 Reporte semanal", "📆 Reporte mensual"])

    # ── TAB 1: SEMANAL ────────────────────────────────────────
    with tab1:
        st.markdown("#### Reporte semanal de ausencias")
        col1, col2 = st.columns(2)
        with col1:
            fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=date.today().weekday()))
        with col2:
            fecha_hasta = st.date_input("Hasta", value=fecha_desde + timedelta(days=5))

        sector_sel = st.selectbox("Sector", ["Todos","Administración","Compras",
                                              "Montecaseros","Local calle San Juan","Logistica"],
                                  key="sec_sem")

        if st.button("🔍 Generar reporte semanal", type="primary"):
            datos = _get_ausencias(fecha_desde, fecha_hasta, sector_sel)
            if datos:
                _mostrar_reporte(datos, f"Semana {fecha_desde.strftime('%d/%m')} — {fecha_hasta.strftime('%d/%m/%Y')}")
                xlsx = _exportar_reporte(datos, f"Semana {fecha_desde.strftime('%d/%m')} al {fecha_hasta.strftime('%d/%m/%Y')}")
                st.download_button("⬇️ Descargar Excel",
                                   data=xlsx,
                                   file_name=f"Reporte_Semana_{fecha_desde.strftime('%d%m%Y')}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
            else:
                st.success("✅ Sin ausencias en el período seleccionado.")

    # ── TAB 2: MENSUAL ────────────────────────────────────────
    with tab2:
        st.markdown("#### Reporte mensual de ausencias")
        col1, col2 = st.columns(2)
        with col1:
            hoy = date.today()
            anio = st.number_input("Año", value=hoy.year, min_value=2024, max_value=2030)
            mes  = st.selectbox("Mes", list(range(1,13)), index=hoy.month-1,
                                format_func=lambda m: ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                                                        "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][m-1])
        with col2:
            sector_sel2 = st.selectbox("Sector", ["Todos","Administración","Compras",
                                                   "Montecaseros","Local calle San Juan","Logistica"],
                                       key="sec_men")

        if st.button("🔍 Generar reporte mensual", type="primary"):
            primer = date(anio, mes, 1)
            ultimo = date(anio, mes, calendar.monthrange(anio, mes)[1])
            datos  = _get_ausencias(primer, ultimo, sector_sel2)
            mes_str = ["Enero","Febrero","Marzo","Abril","Mayo","Junio",
                       "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][mes-1]
            if datos:
                _mostrar_reporte(datos, f"{mes_str} {anio}")
                xlsx = _exportar_reporte(datos, f"{mes_str} {anio}")
                st.download_button("⬇️ Descargar Excel",
                                   data=xlsx,
                                   file_name=f"Reporte_Ausencias_{mes_str}_{anio}.xlsx",
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
            else:
                st.success("✅ Sin ausencias en el período seleccionado.")

def _get_ausencias(desde: date, hasta: date, sector: str):
    """Devuelve lista de ausencias e incidencias en el rango de fechas."""
    conn = get_conn()
    cur  = dict_cursor(conn)

    # Feriados del rango
    cur.execute("SELECT fecha FROM feriados WHERE fecha >= %s AND fecha <= %s",
                (str(desde), str(hasta)))
    feriados = {r["fecha"] for r in cur.fetchall()}

    # Novedades aprobadas del rango
    cur.execute("""SELECT n.legajo, n.tipo, n.fecha_desde, n.fecha_hasta, n.descripcion
                   FROM novedades n
                   WHERE n.estado IN ('aprobado','enviado')
                   AND n.fecha_desde <= %s AND (n.fecha_hasta >= %s OR n.fecha_hasta IS NULL)""",
                (str(hasta), str(desde)))
    novedades = {}
    for row in cur.fetchall():
        leg = str(row["legajo"])
        d_from = date.fromisoformat(row["fecha_desde"])
        d_to   = date.fromisoformat(row["fecha_hasta"]) if row["fecha_hasta"] else d_from
        d = d_from
        while d <= d_to:
            if desde <= d <= hasta:
                novedades.setdefault(leg, {})[d] = row["tipo"]
            d += timedelta(days=1)

    # Colaboradores
    sql_col = "SELECT legajo, apellido||' '||nombre as nombre, sector FROM colaboradores WHERE activo=1"
    params_col = []
    if sector != "Todos":
        sql_col += " AND sector=%s"; params_col.append(sector)
    sql_col += " ORDER BY sector, apellido"
    cur.execute(sql_col, params_col)
    colaboradores = cur.fetchall()

    # Marcaciones del rango
    cur.execute("SELECT legajo, fecha FROM marcaciones WHERE fecha >= %s AND fecha <= %s",
                (str(desde), str(hasta)))
    marcaciones = set()
    for r in cur.fetchall():
        marcaciones.add((str(r["legajo"]), r["fecha"]))

    conn.close()

    resultados = []
    d = desde
    while d <= hasta:
        dow = d.weekday()
        if dow == 6:  # domingo
            d += timedelta(days=1)
            continue
        fecha_str = str(d)
        es_fer = fecha_str in feriados

        for col in colaboradores:
            legajo = str(col["legajo"])
            marcó  = (legajo, fecha_str) in marcaciones
            nov    = novedades.get(legajo, {}).get(d)

            if es_fer:
                estado = "Feriado"
            elif not marcó and not nov:
                if dow == 5:  # sábado
                    if legajo == "24":  # Wilfredo — puede ser libre
                        estado = "Sábado libre"
                    elif legajo in {"162","189"}:
                        estado = "Sábado HO"
                    else:
                        estado = "Ausente"
                else:
                    estado = "Ausente"
            elif not marcó and nov:
                estado = nov
            else:
                continue  # marcó correctamente, no incluir en reporte

            if estado in ("Ausente",):  # Solo mostrar las problemáticas
                resultados.append({
                    "fecha": d.strftime("%d/%m/%Y"),
                    "dia":   DIAS_ES.get(d.strftime("%a"), d.strftime("%a")),
                    "legajo": legajo,
                    "nombre": col["nombre"],
                    "sector": col["sector"],
                    "estado": estado,
                    "novedad": nov or "",
                })
        d += timedelta(days=1)

    return resultados

def _mostrar_reporte(datos, titulo):
    st.markdown(f"#### {titulo} — {len(datos)} ausencias sin justificar")
    # Agrupar por colaborador
    por_colab = {}
    for r in datos:
        k = r["nombre"]
        por_colab.setdefault(k, {"sector": r["sector"], "dias": []})
        por_colab[k]["dias"].append(f"{r['dia']} {r['fecha']}")

    for nombre, info in sorted(por_colab.items(), key=lambda x: x[1]["sector"]):
        cant = len(info["dias"])
        color = "#FFF0F0" if cant >= 3 else "#FFF8E1"
        borde = "#C00000" if cant >= 3 else "#E6AC00"
        dias_txt = " · ".join(info["dias"])
        st.markdown(f"""
        <div style="background:{color};border-left:4px solid {borde};
             padding:0.5rem 1rem;border-radius:4px;margin-bottom:0.4rem;">
          <strong>{nombre}</strong> <span style="color:#666;">· {info['sector']}</span>
          <span style="float:right;font-weight:700;color:{borde};">{cant} día(s)</span><br>
          <span style="font-size:0.82rem;color:#555;">{dias_txt}</span>
        </div>""", unsafe_allow_html=True)

def _exportar_reporte(datos, titulo):
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte de Ausencias"
    ws.sheet_view.showGridLines = False

    ws.merge_cells("A1:F1")
    c = ws["A1"]
    c.value = f"OK ACCESORIOS · REPORTE DE AUSENCIAS · {titulo.upper()}"
    c.font = _ft(True,12,"FFFFFF"); c.fill = _fc("1F3864"); c.alignment = _al()
    ws.row_dimensions[1].height = 24

    hdrs = [("A",12,"Fecha"),("B",7,"Día"),("C",10,"Legajo"),
            ("D",26,"Nombre"),("E",20,"Sector"),("F",20,"Estado")]
    for col,w,lbl in hdrs:
        ws.column_dimensions[col].width = w
        c = ws[f"{col}2"]; c.value = lbl
        c.font = _ft(True,9,"FFFFFF"); c.fill = _fc("2E75B6")
        c.alignment = _al(); c.border = _bd()

    for i, r in enumerate(datos):
        row = 3+i
        bg = "FCE4D6" if r["estado"]=="Ausente" else "FFF2CC"
        for ci, val in enumerate([r["fecha"],r["dia"],r["legajo"],
                                   r["nombre"],r["sector"],r["estado"]], 1):
            c = ws.cell(row=row, column=ci, value=val)
            c.fill = _fc(bg); c.border = _bd(); c.font = _ft(sz=9)
            c.alignment = _al("left" if ci in (4,5) else "center")
        ws.row_dimensions[row].height = 14

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
