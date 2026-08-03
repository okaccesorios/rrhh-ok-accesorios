"""
Genera el Excel de Papel de Trabajo desde los datos calculados.
Mismo formato que el sistema anterior.
"""
import io
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from utils.calculos import calcular_periodo, fmt_dur, from_min
from calendar import month_name

MESES_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
            7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

def _fc(h): return PatternFill("solid", fgColor=h)
def _ft(bold=False, sz=10, color="000000"): return Font(bold=bold, size=sz, color=color, name="Calibri")
def _al(h="center", v="center", wrap=False): return Alignment(horizontal=h, vertical=v, wrap_text=wrap)
def _bd():
    s = Side(style="thin", color="BFBFBF")
    return Border(left=s, right=s, top=s, bottom=s)

DARK="1F3864"; BLUE="2E75B6"; LBLUE="D6E4F0"; YEL="FFF2CC"
GREEN="E2EFDA"; LGRY="F2F2F2"; RED="FCE4D6"; WHITE="FFFFFF"

def generar_excel(periodo: str) -> bytes:
    resumen = calcular_periodo(periodo)
    anio, mes = int(periodo[:4]), int(periodo[5:7])
    mes_str = f"{MESES_ES.get(mes, mes)} {anio}"

    wb = Workbook()

    # ══ 1. PANEL GENERAL ══════════════════════════════════════
    ws = wb.active
    ws.title = "Panel General"
    ws.sheet_view.showGridLines = False

    titulo = f"OK ACCESORIOS  ·  PAPEL DE TRABAJO HORARIO  ·  {mes_str.upper()}"
    ws.merge_cells("A1:S1")
    c = ws["A1"]; c.value = titulo
    c.font = _ft(True,14,WHITE); c.fill = _fc(DARK); c.alignment = _al()
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:S2")
    c = ws["A2"]
    c.value = f"Período: {periodo}   |   {len(resumen)} colaboradores"
    c.font = _ft(False,9,WHITE); c.fill = _fc(BLUE); c.alignment = _al("left")

    # Grupos de cabecera
    grupos = [
        ("A1:C1","IDENTIFICACIÓN",DARK),("D1:I1","ASISTENCIA Y PUNTUALIDAD",BLUE),
        ("J1:K1","HORAS EXTRAS","375623"),("L1:O1","LICENCIAS Y AUSENCIAS","7D3C00"),
        ("P1:Q1","ADELANTOS / DESC.",DARK),("R1:S1","NOVEDADES","4A235A"),
    ]
    for rng, lbl, bg in grupos:
        ws.merge_cells(rng.replace("1","4"))
        c = ws[rng.replace("1","4").split(":")[0]]
        c.value = lbl; c.font = _ft(True,8,WHITE); c.fill = _fc(bg); c.alignment = _al()

    hdrs = [
        ("A",8,"Legajo"),("B",26,"Apellido y Nombre"),("C",16,"Sector"),
        ("D",7,"Días\nTrab."),("E",7,"Días\nAus."),("F",7,"Feriados"),
        ("G",7,"Home\nOffice"),("H",8,"Cant.\nTardanzas"),("I",10,"Total\nTardanza"),
        ("J",10,"Hs Extra\n50%"),("K",10,"Hs Extra\n100%"),
        ("L",8,"Lic.\nEnf."),("M",8,"Vacac.\n(días)"),("N",8,"ART\n(días)"),
        ("O",22,"Tipo Ausencia /\nDetalle"),
        ("P",12,"Adelanto $"),("Q",14,"Mercadería /\nDesc. $"),
        ("R",12,"Sanción"),("S",30,"Observaciones"),
    ]
    for col, width, label in hdrs:
        ws.column_dimensions[col].width = width
        c = ws[f"{col}5"]
        c.value = label; c.font = _ft(True,8,WHITE)
        c.fill = _fc("1A3A6B"); c.alignment = _al(wrap=True); c.border = _bd()
    ws.row_dimensions[5].height = 30

    for i, emp in enumerate(resumen):
        row = 6 + i
        bg  = LGRY if i % 2 == 0 else WHITE
        bga = "FFF0E8" if i % 2 == 0 else "FFF8F5"
        bgn = "F5F0FF" if i % 2 == 0 else "FAF7FF"

        # resumen novedades para col O
        partes = []
        if emp["dias_viaje"]: partes.append(f"Viaje ({emp['dias_viaje']}d)")
        if emp["dias_lic"]:   partes.append(f"Lic.Enf ({emp['dias_lic']}d)")
        if emp["dias_vac"]:   partes.append(f"Vacac. ({emp['dias_vac']}d)")
        if emp["dias_art"]:   partes.append(f"ART ({emp['dias_art']}d)")
        tipo_aus = " | ".join(partes)

        vals = [
            (emp["legajo"],bg),(emp["nombre"],bg),(emp["sector"],bg),
            (emp["dias_trab"],bg),(emp["dias_aus"],bg),(emp["dias_feriado"],bg),
            ("",bg),
            (emp["tard_n"] if emp["tard_n"] else "-",bg),
            (fmt_dur(emp["tard_min"]),bg),
            (fmt_dur(emp["he50"]),bga),(fmt_dur(emp["he100"]),bga),
            (emp["dias_lic"] or "",bga),(emp["dias_vac"] or "",bga),(emp["dias_art"] or "",bga),
            (tipo_aus,bga),
            (emp["adelanto"] if emp["adelanto"] else "",bg),
            (emp["descuento"] if emp["descuento"] else "",bg),
            ("",bgn),("",bgn),
        ]
        for ci, (val, bgc) in enumerate(vals, 1):
            c = ws.cell(row=row, column=ci, value=val)
            c.fill = _fc(bgc); c.border = _bd(); c.font = _ft(sz=9)
            c.alignment = _al("left" if ci in (2,3,15,19) else "center")
        ws.row_dimensions[row].height = 15

    # ══ 2. DETALLE POR EMPLEADO ════════════════════════════════
    ws2 = wb.create_sheet("Detalle por Empleado")
    ws2.sheet_view.showGridLines = False
    ws2.merge_cells("A1:J1")
    c = ws2["A1"]; c.value = f"OK ACCESORIOS  ·  DETALLE DIARIO  ·  {mes_str.upper()}"
    c.font = _ft(True,12,WHITE); c.fill = _fc(DARK); c.alignment = _al()
    ws2.row_dimensions[1].height = 24

    hdrs2 = [("A",8,"Legajo"),("B",24,"Nombre"),("C",16,"Sector"),
              ("D",12,"Fecha"),("E",7,"Día"),("F",22,"Estado"),
              ("G",8,"Ingreso"),("H",8,"Salida"),("I",10,"Tardanza"),
              ("J",28,"Novedad / Obs.")]
    for col,w,lbl in hdrs2:
        ws2.column_dimensions[col].width = w
        c = ws2[f"{col}2"]; c.value = lbl
        c.font = _ft(True,8,WHITE); c.fill = _fc("1A3A6B")
        c.alignment = _al(); c.border = _bd()
    ws2.row_dimensions[2].height = 18

    row2 = 3
    ESTADOS_COLOR = {
        "Trabajó":GREEN,"Tardanza":"FFF2CC","Ausente":RED,
        "Feriado":LBLUE,"Feriado trabajado":"D5E8D4","Domingo":LGRY,"Sábado libre":LGRY,
    }
    for emp in resumen:
        for dd in emp["detalle"]:
            bg = ESTADOS_COLOR.get(dd["estado"], WHITE)
            if any(k in dd["estado"] for k in ["Viaje","Licencia","Vacaciones","ART","Home office"]):
                bg = "E8F5E9"
            vals = [emp["legajo"],emp["nombre"],emp["sector"],
                    dd["fecha"].strftime("%d/%m/%Y"),dd["dia"],dd["estado"],
                    dd["ingreso"],dd["salida"],dd["tardanza"],dd.get("novedad","")]
            for ci, val in enumerate(vals, 1):
                c = ws2.cell(row=row2, column=ci, value=val)
                c.fill = _fc(bg); c.border = _bd(); c.font = _ft(sz=8)
                c.alignment = _al("left" if ci in (2,3,6,10) else "center")
            ws2.row_dimensions[row2].height = 13
            row2 += 1

    # ══ 3. HORAS EXTRAS ═══════════════════════════════════════
    ws3 = wb.create_sheet("Horas Extras")
    ws3.sheet_view.showGridLines = False
    ws3.merge_cells("A1:G1")
    c = ws3["A1"]; c.value = f"OK ACCESORIOS  ·  HORAS EXTRAS  ·  {mes_str.upper()}"
    c.font = _ft(True,12,WHITE); c.fill = _fc(DARK); c.alignment = _al()
    for col,w,lbl in [("A",8,"Legajo"),("B",24,"Nombre"),("C",16,"Sector"),
                       ("D",12,"Hs Extra 50%"),("E",12,"Hs Extra 100%"),("F",12,"TOTAL"),("G",24,"Obs.")]:
        ws3.column_dimensions[col].width = w
        c = ws3[f"{col}2"]; c.value = lbl
        c.font = _ft(True,8,WHITE); c.fill = _fc(BLUE); c.alignment = _al(); c.border = _bd()
    r = 3
    for emp in resumen:
        if not emp["he50"] and not emp["he100"]: continue
        for ci,val in enumerate([emp["legajo"],emp["nombre"],emp["sector"],
                                  fmt_dur(emp["he50"]),fmt_dur(emp["he100"]),
                                  fmt_dur(emp["he50"]+emp["he100"]),""],1):
            c = ws3.cell(row=r,column=ci,value=val)
            c.fill = _fc(LGRY if r%2==0 else WHITE); c.border = _bd(); c.font = _ft(sz=9)
            c.alignment = _al("left" if ci in (2,3) else "center")
        r += 1

    # ══ 4. TARDANZAS ══════════════════════════════════════════
    ws4 = wb.create_sheet("Tardanzas")
    ws4.sheet_view.showGridLines = False
    ws4.merge_cells("A1:F1")
    c = ws4["A1"]; c.value = f"OK ACCESORIOS  ·  TARDANZAS  ·  {mes_str.upper()}"
    c.font = _ft(True,12,WHITE); c.fill = _fc(DARK); c.alignment = _al()
    for col,w,lbl in [("A",8,"Legajo"),("B",24,"Nombre"),("C",16,"Sector"),
                       ("D",8,"Cant."),("E",12,"Total"),("F",12,"Alerta")]:
        ws4.column_dimensions[col].width = w
        c = ws4[f"{col}2"]; c.value = lbl
        c.font = _ft(True,8,WHITE); c.fill = _fc(BLUE); c.alignment = _al(); c.border = _bd()
    r = 3
    for emp in sorted(resumen, key=lambda x: -x["tard_min"]):
        if not emp["tard_n"]: continue
        alerta = "🔴 ATENCIÓN" if emp["tard_min"] > 60 else "🟡 Informativo"
        for ci,val in enumerate([emp["legajo"],emp["nombre"],emp["sector"],
                                  emp["tard_n"],fmt_dur(emp["tard_min"]),alerta],1):
            c = ws4.cell(row=r,column=ci,value=val)
            c.fill = _fc(LGRY if r%2==0 else WHITE); c.border = _bd(); c.font = _ft(sz=9)
        r += 1

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
