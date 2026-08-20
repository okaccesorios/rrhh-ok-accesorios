"""
Motor de cálculo del Papel de Trabajo.
v3.2 — Neteado tardanzas/HE, marcaciones completas, período 25-24
"""
from datetime import date, timedelta
from utils.database import get_conn

SABADO_LIMITE_EXTRA = 13 * 60  # 13:00 en minutos
DIAS_ES = {"Mon":"Lun","Tue":"Mar","Wed":"Mié","Thu":"Jue","Fri":"Vie","Sat":"Sáb","Sun":"Dom"}

# Colaboradores con sábado home office (no libre, no presencial)
SAB_HOME_OFFICE = {"163","189"}  # Brandani, Gutierrez Franco
# Colaboradores con sábado libre rotativo (1 por mes) — solo Guzman
SAB_LIBRE = {"24"}

def to_min(hhmm: str) -> int | None:
    if not hhmm:
        return None
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h) * 60 + int(m)
    except:
        return None

def from_min(mins: int) -> str:
    if mins is None:
        return ""
    return f"{mins//60:02d}:{mins%60:02d}"

def fmt_dur(mins: int) -> str:
    if not mins:
        return "-"
    h, m = divmod(abs(mins), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"

def _parse_marcaciones(horas_raw: str):
    """
    Extrae hasta 4 marcaciones del string del reloj.
    Devuelve (entrada, ini_almuerzo, fin_almuerzo, salida) como strings HH:MM o None.
    """
    if not horas_raw or str(horas_raw).strip() in ("", "nan", "None"):
        return None, None, None, None
    partes = str(horas_raw).strip().split()
    validas = []
    for p in partes:
        p = p.strip()
        if len(p) == 5 and p[2] == ":":
            try:
                h, m = int(p[:2]), int(p[3:])
                if 0 <= h <= 23 and 0 <= m <= 59:
                    validas.append(p)
            except:
                pass
    # Asignar según cantidad de marcaciones
    entrada = ini_alm = fin_alm = salida = None
    if len(validas) >= 1: entrada  = validas[0]
    if len(validas) >= 2: salida   = validas[-1]
    if len(validas) >= 3: ini_alm  = validas[1]
    if len(validas) >= 4: fin_alm  = validas[2]
    return entrada, ini_alm, fin_alm, salida

def _periodo_liquidacion(fecha: date) -> str:
    """
    Determina el período de liquidación según regla 25-24.
    Del 25 de un mes al 24 del siguiente → pertenece al mes siguiente.
    """
    if fecha.day >= 25:
        # Pertenece al mes siguiente
        if fecha.month == 12:
            return f"{fecha.year + 1}-01"
        else:
            return f"{fecha.year}-{fecha.month + 1:02d}"
    else:
        return f"{fecha.year}-{fecha.month:02d}"

def calcular_periodo(periodo: str):
    """
    Calcula el Papel de Trabajo para un período dado (YYYY-MM).
    Período = mes de liquidación (puede incluir días del 25 del mes anterior al 24 de este mes).
    """
    anio, mes = int(periodo[:4]), int(periodo[5:7])
    conn = get_conn()

    # Feriados del mes
    feriados = set()
    for row in conn.execute(
        "SELECT fecha FROM feriados WHERE fecha LIKE ?", (f"{periodo}%",)
    ).fetchall():
        try:
            feriados.add(date.fromisoformat(row["fecha"]))
        except:
            pass

    # Novedades aprobadas del mes
    novedades_db = {}
    for row in conn.execute("""
        SELECT n.legajo, n.tipo, n.fecha_desde, n.fecha_hasta, n.descripcion
        FROM novedades n
        WHERE n.estado IN ('aprobado','enviado')
        AND (n.fecha_desde LIKE ? OR n.fecha_hasta LIKE ?)
    """, (f"{periodo}%", f"{periodo}%")).fetchall():
        leg = str(row["legajo"])
        desde = date.fromisoformat(row["fecha_desde"])
        hasta = date.fromisoformat(row["fecha_hasta"]) if row["fecha_hasta"] else desde
        d = desde
        while d <= hasta:
            novedades_db.setdefault(leg, {})[d] = {
                "tipo": row["tipo"], "obs": row["descripcion"] or ""
            }
            d += timedelta(days=1)

    # Adelantos del período de liquidación (regla 25-24)
    adelantos_db = {}
    for row in conn.execute(
        "SELECT legajo, tipo, monto, descripcion FROM adelantos WHERE periodo=?",
        (periodo,)
    ).fetchall():
        adelantos_db.setdefault(str(row["legajo"]), []).append(dict(row))

    # Colaboradores activos
    colaboradores = conn.execute(
        "SELECT * FROM colaboradores WHERE activo=1 ORDER BY sector, apellido"
    ).fetchall()

    # Marcaciones del período — incluir del 25 del mes anterior al 24 de este mes
    if mes == 1:
        mes_ant, anio_ant = 12, anio - 1
    else:
        mes_ant, anio_ant = mes - 1, anio

    # Buscar marcaciones del rango completo (25 mes anterior al 24 este mes)
    fecha_inicio = f"{anio_ant}-{mes_ant:02d}-25"
    fecha_fin    = f"{anio}-{mes:02d}-24"
    marcaciones_raw = conn.execute("""
        SELECT legajo, fecha, horas_raw, ingreso, egreso
        FROM marcaciones
        WHERE fecha >= ? AND fecha <= ?
    """, (fecha_inicio, fecha_fin)).fetchall()

    marc_dict = {}
    for m in marcaciones_raw:
        marc_dict.setdefault(str(m["legajo"]), {})[date.fromisoformat(m["fecha"])] = m

    conn.close()

    # Rango del período: del 25 del mes anterior al 24 de este mes
    primer_dia = date(anio_ant, mes_ant, 25)
    ultimo_dia = date(anio, mes, 24)

    resumen = []

    for col in colaboradores:
        legajo  = str(col["legajo"])
        cfg     = dict(col)
        marc    = marc_dict.get(legajo, {})
        novs    = novedades_db.get(legajo, {})
        adels   = adelantos_db.get(legajo, [])

        dias_trab = dias_aus = dias_feriado = dias_home = 0
        he50_bruto = he100 = 0
        tard_n = tard_min_total = 0
        detalle = []

        d = primer_dia
        while d <= ultimo_dia:
            dow       = d.weekday()  # 0=Lun … 6=Dom
            es_dom    = (dow == 6)
            es_sab    = (dow == 5)
            es_feriado = d in feriados
            fichadas  = marc.get(d)
            nov_dia   = novs.get(d)

            entrada_str = ini_alm_str = fin_alm_str = salida_str = ""
            ing = sal = None
            tardanza_min = 0
            estado = ""

            if es_dom:
                estado = "Domingo"
                d += timedelta(days=1)
                continue

            if es_feriado:
                dias_feriado += 1
                estado = "Feriado"
                if fichadas and fichadas["horas_raw"]:
                    e, ia, fa, s = _parse_marcaciones(fichadas["horas_raw"])
                    entrada_str = e or ""
                    salida_str  = s or ""
                    ing = to_min(e)
                    sal = to_min(s)
                    if ing is not None and sal is not None and sal > ing:
                        he100 += sal - ing
                    estado = "Feriado trabajado"

            elif es_sab:
                # Determinar tipo de sábado por legajo
                if legajo in SAB_HOME_OFFICE:
                    dias_home += 1
                    estado = "Sábado HO"
                elif legajo in SAB_LIBRE:
                    estado = "Sábado libre"
                else:
                    # Sábado presencial
                    if fichadas and fichadas["horas_raw"]:
                        e, ia, fa, s = _parse_marcaciones(fichadas["horas_raw"])
                        entrada_str = e or ""
                        salida_str  = s or ""
                        ing = to_min(e)
                        sal = to_min(s)
                        if ing is not None and sal is not None and sal > SABADO_LIMITE_EXTRA:
                            he100 += sal - max(ing, SABADO_LIMITE_EXTRA)
                        dias_trab += 1
                        estado = "Trabajó Sáb"
                    else:
                        if nov_dia:
                            estado = nov_dia["tipo"]
                        else:
                            estado = "Sábado libre"

            else:
                # Día hábil L-V
                ent_cfg = to_min(cfg.get("entrada") or "09:00")
                sal_cfg = to_min(cfg.get("salida")  or "18:00")
                alm_min = cfg.get("almuerzo_min") or 60
                brk_min = cfg.get("break_min") or 0
                tolerancia = 5  # minutos de gracia

                if not fichadas or not fichadas["horas_raw"] or str(fichadas["horas_raw"]).strip() in ("","nan","None"):
                    if nov_dia:
                        estado = nov_dia["tipo"]
                    else:
                        estado = "Ausente"
                    dias_aus += 1
                else:
                    e, ia, fa, s = _parse_marcaciones(fichadas["horas_raw"])
                    entrada_str  = e  or ""
                    ini_alm_str  = ia or ""
                    fin_alm_str  = fa or ""
                    salida_str   = s  or ""

                    ing = to_min(e)
                    sal = to_min(s)
                    dias_trab += 1

                    # Tardanza
                    if ing and ent_cfg and ing > ent_cfg + tolerancia:
                        tardanza_min   = ing - ent_cfg
                        tard_n        += 1
                        tard_min_total += tardanza_min
                        estado = "Tardanza"
                    else:
                        estado = "Trabajó"

                    # Horas extra brutas (salida posterior al horario)
                    if ing is not None and sal is not None and sal > sal_cfg:
                        he_bruta = sal - sal_cfg
                        # Neteado: descontar tardanza de las HE
                        he_neta = max(0, he_bruta - tardanza_min)
                        he50_bruto += he_neta
                    
            detalle.append({
                "fecha":       d,
                "dia":         DIAS_ES.get(d.strftime("%a"), d.strftime("%a")),
                "estado":      estado,
                "entrada":     entrada_str,
                "ini_almuerzo":ini_alm_str,
                "fin_almuerzo":fin_alm_str,
                "salida":      salida_str,
                "tardanza":    fmt_dur(tardanza_min) if tardanza_min else "-",
                "novedad":     nov_dia.get("obs","") if nov_dia else "",
            })
            d += timedelta(days=1)

        # Conteo novedades
        cnt = lambda t: sum(1 for dd in detalle if dd["estado"] == t)
        adel_sum = sum(a["monto"] or 0 for a in adels if a["tipo"] == "adelanto")
        desc_sum = sum(a["monto"] or 0 for a in adels if a["tipo"] == "descuento_mercaderia")

        resumen.append({
            "legajo":     legajo,
            "nombre":     f"{cfg['apellido']} {cfg['nombre']}",
            "sector":     cfg["sector"],
            "dias_trab":  dias_trab,
            "dias_aus":   dias_aus,
            "dias_feriado": dias_feriado,
            "dias_home":  dias_home,
            "tard_n":     tard_n,
            "tard_min":   tard_min_total,
            "he50":       he50_bruto,
            "he100":      he100,
            "dias_lic":   cnt("Licencia por enfermedad"),
            "dias_vac":   cnt("Vacaciones"),
            "dias_art":   cnt("ART"),
            "dias_viaje": cnt("Viaje / visita clientes"),
            "adelanto":   adel_sum,
            "descuento":  desc_sum,
            "detalle":    detalle,
            "adels":      adels,
        })

    return resumen
