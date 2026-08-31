"""
Motor de cálculo del Papel de Trabajo — PostgreSQL version
"""
from datetime import date, timedelta
import calendar
from utils.database import get_conn, dict_cursor

SABADO_LIMITE_EXTRA = 13 * 60
DIAS_ES = {"Mon":"Lun","Tue":"Mar","Wed":"Mié","Thu":"Jue","Fri":"Vie","Sat":"Sáb","Sun":"Dom"}
SAB_HOME_OFFICE = {"162","189"}
SAB_LIBRE = {"24"}

def to_min(hhmm):
    if not hhmm: return None
    try:
        h, m = str(hhmm).strip().split(":")
        return int(h)*60+int(m)
    except: return None

def from_min(mins):
    if mins is None: return ""
    return f"{mins//60:02d}:{mins%60:02d}"

def fmt_dur(mins):
    if not mins: return "-"
    h, m = divmod(abs(mins), 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"

def _parse_marcaciones(horas_raw):
    if not horas_raw or str(horas_raw).strip() in ("","nan","None"):
        return None, None, None, None
    partes = str(horas_raw).strip().split()
    validas = []
    for p in partes:
        if len(p)==5 and p[2]==":":
            try:
                h,m = int(p[:2]),int(p[3:])
                if 0<=h<=23 and 0<=m<=59: validas.append(p)
            except: pass
    entrada=ini_alm=fin_alm=salida=None
    if len(validas)>=1: entrada=validas[0]
    if len(validas)>=2: salida=validas[-1]
    if len(validas)>=3: ini_alm=validas[1]
    if len(validas)>=4: fin_alm=validas[2]
    return entrada, ini_alm, fin_alm, salida

def calcular_periodo(periodo: str):
    anio, mes = int(periodo[:4]), int(periodo[5:7])
    conn = get_conn()
    cur = dict_cursor(conn)

    # Feriados del mes
    cur.execute("SELECT fecha FROM feriados WHERE fecha LIKE %s", (f"{periodo}%",))
    feriados = set()
    for row in cur.fetchall():
        try: feriados.add(date.fromisoformat(row["fecha"]))
        except: pass

    # Novedades aprobadas
    cur.execute("""SELECT n.legajo, n.tipo, n.fecha_desde, n.fecha_hasta, n.descripcion
                   FROM novedades n
                   WHERE n.estado IN ('aprobado','enviado')
                   AND (n.fecha_desde LIKE %s OR n.fecha_hasta LIKE %s)""",
                (f"{periodo}%", f"{periodo}%"))
    novedades_db = {}
    for row in cur.fetchall():
        leg = str(row["legajo"])
        desde = date.fromisoformat(row["fecha_desde"])
        hasta = date.fromisoformat(row["fecha_hasta"]) if row["fecha_hasta"] else desde
        d = desde
        while d <= hasta:
            novedades_db.setdefault(leg, {})[d] = {"tipo": row["tipo"], "obs": row["descripcion"] or ""}
            d += timedelta(days=1)

    # Adelantos del período
    cur.execute("SELECT legajo, tipo, monto, descripcion FROM adelantos WHERE periodo=%s", (periodo,))
    adelantos_db = {}
    for row in cur.fetchall():
        adelantos_db.setdefault(str(row["legajo"]), []).append(dict(row))

    # Colaboradores activos
    cur.execute("SELECT * FROM colaboradores WHERE activo=1 ORDER BY sector, apellido")
    colaboradores = cur.fetchall()

    # Marcaciones del mes completo
    cur.execute("""SELECT legajo, fecha, horas_raw, ingreso, egreso
                   FROM marcaciones WHERE fecha LIKE %s""", (f"{periodo}%",))
    marc_dict = {}
    for m in cur.fetchall():
        marc_dict.setdefault(str(m["legajo"]), {})[date.fromisoformat(m["fecha"])] = m

    conn.close()

    # Rango mes completo
    primer_dia = date(anio, mes, 1)
    ultimo_dia = date(anio, mes, calendar.monthrange(anio, mes)[1])

    resumen = []
    for col in colaboradores:
        legajo = str(col["legajo"])
        cfg    = dict(col)
        marc   = marc_dict.get(legajo, {})
        novs   = novedades_db.get(legajo, {})
        adels  = adelantos_db.get(legajo, [])

        dias_trab=dias_aus=dias_feriado=dias_home=0
        he50=he100=0
        tard_n=tard_min_total=0
        detalle=[]

        d = primer_dia
        while d <= ultimo_dia:
            dow = d.weekday()
            es_sab = (dow==5)
            es_dom = (dow==6)
            es_feriado = d in feriados
            fichadas = marc.get(d)
            nov_dia  = novs.get(d)

            entrada_str=ini_alm_str=fin_alm_str=salida_str=""
            ing=sal=None
            tardanza_min=0
            estado=""

            if es_dom:
                d += timedelta(days=1)
                continue

            if es_feriado:
                # Feriado: siempre figura como Feriado, no como trabajado
                dias_feriado += 1
                estado = "Feriado"

            elif es_sab:
                if legajo in SAB_HOME_OFFICE:
                    dias_home += 1
                    estado = "Sábado HO"
                elif legajo in SAB_LIBRE:
                    estado = "Sábado libre"
                else:
                    raw_sab = fichadas["horas_raw"] if fichadas else None
                    if raw_sab and str(raw_sab).strip() not in ("","nan","None"):
                        e,ia,fa,s = _parse_marcaciones(raw_sab)
                        entrada_str=e or ""; salida_str=s or ""
                        ing=to_min(e); sal=to_min(s)
                        # Usar salida_sab del colaborador como límite de HE
                        lim_sab = to_min(cfg.get("salida_sab") or "13:00")
                        if ing is not None and sal is not None and lim_sab and sal > lim_sab:
                            he100 += sal - max(ing, lim_sab)
                        dias_trab += 1
                        estado = "Trabajó Sáb"
                    else:
                        estado = nov_dia["tipo"] if nov_dia else "Ausente Sáb"

            else:
                ent_cfg = to_min(cfg.get("entrada") or "09:00")
                sal_cfg = to_min(cfg.get("salida")  or "18:00")
                tolerancia = 5

                raw_dia = fichadas["horas_raw"] if fichadas else None
                if not raw_dia or str(raw_dia).strip() in ("","nan","None"):
                    estado = nov_dia["tipo"] if nov_dia else "Ausente"
                    dias_aus += 1
                else:
                    e,ia,fa,s = _parse_marcaciones(raw_dia)
                    entrada_str=e or ""; ini_alm_str=ia or ""
                    fin_alm_str=fa or ""; salida_str=s or ""
                    ing=to_min(e); sal=to_min(s)
                    dias_trab += 1

                    if ing and ent_cfg and ing > ent_cfg+tolerancia:
                        tardanza_min   = ing-ent_cfg
                        tard_n        += 1
                        tard_min_total += tardanza_min
                        estado = "Tardanza"
                    else:
                        estado = "Trabajó"

                    # Usar salida del colaborador como límite exacto de HE
                    lim_he = to_min(cfg.get("salida") or "18:00")
                    if ing is not None and sal is not None and lim_he and sal > lim_he:
                        he_neta = max(0, sal-lim_he-tardanza_min)
                        he50 += he_neta

            detalle.append({
                "fecha":d, "dia":DIAS_ES.get(d.strftime("%a"),d.strftime("%a")),
                "estado":estado,
                "entrada":entrada_str, "ini_almuerzo":ini_alm_str,
                "fin_almuerzo":fin_alm_str, "salida":salida_str,
                "tardanza":fmt_dur(tardanza_min) if tardanza_min else "-",
                "novedad":nov_dia.get("obs","") if nov_dia else "",
            })
            d += timedelta(days=1)

        cnt = lambda t: sum(1 for dd in detalle if dd["estado"]==t)
        adel_sum = sum(float(a["monto"] or 0) for a in adels if a["tipo"]=="adelanto")
        desc_sum = sum(float(a["monto"] or 0) for a in adels if a["tipo"]=="descuento_mercaderia")

        resumen.append({
            "legajo":legajo, "nombre":f"{cfg['apellido']} {cfg['nombre']}",
            "sector":cfg["sector"],
            "dias_trab":dias_trab, "dias_aus":dias_aus,
            "dias_feriado":dias_feriado, "dias_home":dias_home,
            "tard_n":tard_n, "tard_min":tard_min_total,
            "he50":he50, "he100":he100,
            "dias_lic":cnt("Licencia por enfermedad"),
            "dias_vac":cnt("Vacaciones"),
            "dias_art":cnt("ART"),
            "dias_viaje":cnt("Viaje / visita clientes"),
            "adelanto":adel_sum, "descuento":desc_sum,
            "detalle":detalle, "adels":adels,
        })
    return resumen
