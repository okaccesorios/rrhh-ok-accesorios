"""
Motor de cálculo del Papel de Trabajo.
Reutiliza toda la lógica ya probada, ahora leyendo desde la BD en lugar del TXT.
"""
from datetime import date, timedelta
from utils.database import get_conn

SABADO_LIMITE_EXTRA = 13 * 60  # 13:00 en minutos
DIAS_ES = {"Mon":"Lun","Tue":"Mar","Wed":"Mié","Thu":"Jue","Fri":"Vie","Sat":"Sáb","Sun":"Dom"}

def to_min(hhmm: str) -> int | None:
    """'09:30' → 570"""
    if not hhmm:
        return None
    try:
        h, m = hhmm.strip().split(":")
        return int(h) * 60 + int(m)
    except:
        return None

def from_min(mins: int) -> str:
    """570 → '09:30'"""
    if mins is None:
        return ""
    return f"{mins//60:02d}:{mins%60:02d}"

def fmt_dur(mins: int) -> str:
    """150 → '2h 30m'"""
    if not mins:
        return "-"
    h, m = divmod(abs(mins), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"

def calcular_periodo(periodo: str):
    """
    Calcula el Papel de Trabajo para un período dado (YYYY-MM).
    Devuelve lista de dicts con todos los indicadores por colaborador.
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
            novedades_db.setdefault(leg, {})[d] = {"tipo": row["tipo"], "obs": row["descripcion"] or ""}
            d += timedelta(days=1)

    # Adelantos del mes
    adelantos_db = {}
    for row in conn.execute(
        "SELECT legajo, tipo, monto, descripcion FROM adelantos WHERE periodo=?", (periodo,)
    ).fetchall():
        adelantos_db.setdefault(str(row["legajo"]), []).append(dict(row))

    # Colaboradores activos
    colaboradores = conn.execute(
        "SELECT * FROM colaboradores WHERE activo=1 ORDER BY sector, apellido"
    ).fetchall()

    # Marcaciones del período
    marcaciones_raw = conn.execute(
        "SELECT legajo, fecha, ingreso, egreso FROM marcaciones WHERE fecha LIKE ?",
        (f"{periodo}%",)
    ).fetchall()
    marc_dict = {}
    for m in marcaciones_raw:
        marc_dict.setdefault(str(m["legajo"]), {})[date.fromisoformat(m["fecha"])] = m

    conn.close()

    # Rango de días del mes
    primer_dia = date(anio, mes, 1)
    if mes == 12:
        ultimo_dia = date(anio+1, 1, 1) - timedelta(days=1)
    else:
        ultimo_dia = date(anio, mes+1, 1) - timedelta(days=1)

    resumen = []

    for col in colaboradores:
        legajo  = str(col["legajo"])
        cfg     = dict(col)
        marc    = marc_dict.get(legajo, {})
        novs    = novedades_db.get(legajo, {})
        adels   = adelantos_db.get(legajo, [])

        dias_trab = dias_aus = dias_feriado = 0
        he50 = he100 = 0
        tard_n = tard_min = 0
        exc_alm = exc_brk = 0
        detalle = []

        d = primer_dia
        while d <= ultimo_dia:
            dow     = d.weekday()  # 0=Lun … 6=Dom
            es_dom  = (dow == 6)
            es_sab  = (dow == 5)
            es_feriado = d in feriados
            fichadas   = marc.get(d)
            nov_dia    = novs.get(d)

            ing = sal = None
            tardanza = 0
            estado   = ""

            if es_dom:
                estado = "Domingo"
                d += timedelta(days=1)
                continue

            if es_feriado:
                dias_feriado += 1
                estado = "Feriado"
                if fichadas and fichadas["ingreso"] and fichadas["egreso"]:
                    ing = to_min(fichadas["ingreso"])
                    sal = to_min(fichadas["egreso"])
                    if ing is not None and sal is not None and sal > ing:
                        he100 += sal - ing
                    estado = "Feriado trabajado"
            elif es_sab:
                if fichadas and fichadas["ingreso"] and fichadas["egreso"]:
                    ing = to_min(fichadas["ingreso"])
                    sal = to_min(fichadas["egreso"])
                    if ing is not None and sal is not None and sal > SABADO_LIMITE_EXTRA:
                        he100 += sal - max(ing, SABADO_LIMITE_EXTRA)
                    dias_trab += 1
                    estado = "Trabajó Sáb"
                else:
                    estado = "Sábado libre"
            else:
                # Día hábil L-V
                ent_cfg = to_min(cfg.get("entrada") or "09:00")
                sal_cfg = to_min(cfg.get("salida")  or "18:00")
                alm_min = cfg.get("almuerzo_min") or 60
                brk_min = cfg.get("break_min") or 0
                jornada = (sal_cfg - ent_cfg) - alm_min - brk_min

                if not fichadas or not fichadas["ingreso"]:
                    if nov_dia:
                        estado = nov_dia["tipo"]
                    else:
                        estado = "Ausente"
                    dias_aus += 1
                else:
                    ing = to_min(fichadas["ingreso"])
                    sal = to_min(fichadas["egreso"]) if fichadas["egreso"] else None
                    dias_trab += 1

                    # Tardanza
                    tolerancia = 5
                    if ing and ent_cfg and ing > ent_cfg + tolerancia:
                        tardanza = ing - ent_cfg
                        tard_n  += 1
                        tard_min += tardanza
                        estado   = "Tardanza"
                    else:
                        estado = "Trabajó"

                    # Horas extra
                    if ing is not None and sal is not None and sal > sal_cfg:
                        he50 += sal - sal_cfg

            detalle.append({
                "fecha":   d,
                "dia":     DIAS_ES.get(d.strftime("%a"), d.strftime("%a")),
                "estado":  estado,
                "ingreso": from_min(ing) if ing is not None else "",
                "salida":  from_min(sal) if sal is not None else "",
                "tardanza":fmt_dur(tardanza) if tardanza else "-",
                "novedad": nov_dia.get("obs","") if nov_dia else "",
            })
            d += timedelta(days=1)

        # Conteo de novedades
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
            "tard_n":     tard_n,
            "tard_min":   tard_min,
            "he50":       he50,
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
