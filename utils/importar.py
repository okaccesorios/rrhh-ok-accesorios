"""
Importador de marcaciones y solicitudes — PostgreSQL version
"""
import pandas as pd
from datetime import datetime, date, timedelta
from utils.database import get_conn, dict_cursor, log_auditoria

def _parse_fecha(val):
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    if isinstance(val, str):
        val = val.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except: pass
    return None

def _parse_horas(raw):
    if not raw or str(raw).strip() in ("", "nan", "None"):
        return None, None, str(raw).strip() if raw else ""
    partes = str(raw).strip().split()
    horas_validas = []
    for p in partes:
        p = p.strip()
        if len(p) == 5 and p[2] == ":":
            try:
                h, m = int(p[:2]), int(p[3:])
                if 0 <= h <= 23 and 0 <= m <= 59:
                    horas_validas.append(p)
            except: pass
    if not horas_validas:
        return None, None, raw
    return horas_validas[0], horas_validas[-1], raw

def importar_excel(file_bytes, nombre_archivo: str, usuario: str, sector_override: str = None):
    import io
    if isinstance(file_bytes, bytes):
        file_bytes = io.BytesIO(file_bytes)
    try:
        df = pd.read_excel(file_bytes, header=0, dtype=str)
    except Exception as e:
        return 0, 0, 1, [f"No se pudo leer el archivo: {e}"]

    df.columns = [str(c).strip().lower() for c in df.columns]
    col_map = {}
    for col in df.columns:
        if any(k in col for k in ["acceso","legajo","no-acceso","no_acceso"]):
            col_map["legajo"] = col
        elif "nombre" in col:
            col_map["nombre"] = col
        elif any(k in col for k in ["depart","sector"]):
            col_map["sector"] = col
        elif "fecha" in col:
            col_map["fecha"] = col
        elif any(k in col for k in ["hora","marcacion","time"]):
            col_map["horas"] = col

    if "legajo" not in col_map or "fecha" not in col_map:
        return 0, 0, 1, [f"Columnas no encontradas. Columnas en el archivo: {list(df.columns)}"]

    conn = get_conn()
    nuevos = actualizados = 0
    errores = []

    for idx, row in df.iterrows():
        legajo = str(row.get(col_map["legajo"], "")).strip().lstrip("0") or str(row.get(col_map["legajo"], "")).strip()
        if not legajo or legajo in ("nan","None",""):
            continue
        fecha = _parse_fecha(row.get(col_map["fecha"], ""))
        if not fecha:
            errores.append(f"Fila {idx+2}: fecha inválida")
            continue
        horas_raw = row.get(col_map.get("horas",""), "") if "horas" in col_map else ""
        ingreso, egreso, raw = _parse_horas(horas_raw)
        sector = sector_override or str(row.get(col_map.get("sector",""), "") or "").strip()
        fecha_str = fecha.strftime("%Y-%m-%d")

        cur = dict_cursor(conn)
        cur.execute("SELECT id FROM marcaciones WHERE legajo=%s AND fecha=%s", (legajo, fecha_str))
        existing = cur.fetchone()
        if existing:
            cur.execute("""UPDATE marcaciones SET horas_raw=%s, ingreso=%s, egreso=%s,
                sector=%s, importado_en=NOW()::text, fuente=%s
                WHERE legajo=%s AND fecha=%s""",
                (raw, ingreso, egreso, sector, nombre_archivo, legajo, fecha_str))
            actualizados += 1
        else:
            cur.execute("""INSERT INTO marcaciones (legajo,fecha,horas_raw,ingreso,egreso,sector,fuente)
                VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (legajo, fecha_str, raw, ingreso, egreso, sector, nombre_archivo))
            nuevos += 1

    conn.commit()
    conn.close()
    log_auditoria(usuario, "IMPORTAR_MARCACIONES", "marcaciones",
                  detalle=f"{nombre_archivo}: {nuevos} nuevas, {actualizados} actualizadas")
    return nuevos, actualizados, len(errores), errores

def importar_solicitudes(file_bytes, nombre_archivo: str, usuario: str):
    import io, re
    if isinstance(file_bytes, bytes):
        file_bytes = io.BytesIO(file_bytes)
    try:
        df = pd.read_excel(file_bytes, header=0, dtype=str)
    except Exception as e:
        return 0, 0, 1, [f"No se pudo leer el archivo: {e}"]

    df.columns = [str(c).strip() for c in df.columns]
    TIPO_COL = "Tipo de solicitud"
    FECHA_COL = "Fecha"
    APELLIDO_COL = "Apellido"
    NOMBRE_COL = "Nombre"
    MONTO_COL = "Monto solicitado"
    FACTURA_COL = "Importe de la factura"
    GASTO_COL = "Importe del gasto"
    FECHA_FALTA = "Fecha de la falta"
    TIPO_AUSENCIA = "Tipo de ausencia:"
    DESC_COL = "Descripción breve de la situación"

    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("SELECT legajo, apellido, nombre FROM colaboradores WHERE activo=1")
    colab_rows = cur.fetchall()

    def buscar_legajo(apellido_raw, nombre_raw):
        if not apellido_raw: return None
        ap = str(apellido_raw).strip().lower()
        for r in colab_rows:
            bd_ap = r["apellido"].lower()
            if ap in bd_ap or bd_ap in ap: return str(r["legajo"])
        for r in colab_rows:
            bd_ap = r["apellido"].lower()
            diffs = sum(1 for a,b in zip(ap,bd_ap) if a!=b) + abs(len(ap)-len(bd_ap))
            if len(ap)>=4 and diffs<=1: return str(r["legajo"])
        return None

    def parse_monto(val):
        if not val or str(val).strip() in ("","nan","None"): return None
        try: return float(str(val).replace(".","").replace(",","."))
        except:
            try: return float(str(val))
            except: return None

    def parse_fecha_texto(val):
        if not val or str(val).strip() in ("","nan","None"): return None
        val = str(val).strip()
        MESES = {"ene":"01","feb":"02","mar":"03","abr":"04","may":"05","jun":"06",
                 "jul":"07","ago":"08","sep":"09","oct":"10","nov":"11","dic":"12",
                 "jan":"01","apr":"04","aug":"08","dec":"12"}
        m = re.match(r"([a-záéíóú]+)\s+(\d+),?\s+(\d{4})", val, re.IGNORECASE)
        if m:
            mes_txt, dia, anio = m.groups()
            mes_num = MESES.get(mes_txt.lower()[:3])
            if mes_num:
                try: return date(int(anio), int(mes_num), int(dia))
                except: pass
        for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
            try: return datetime.strptime(val, fmt).date()
            except: pass
        return None

    TIPO_MAP = {
        "adelanto de sueldo": ("adelanto", MONTO_COL),
        "compra de mercadería": ("descuento_mercaderia", FACTURA_COL),
        "solicitud de pago de gasto": ("otro", GASTO_COL),
    }

    nov_nuevas = adel_nuevos = 0
    errores = []

    for idx, row in df.iterrows():
        tipo_raw = str(row.get(TIPO_COL,"")).strip().lower()
        if not tipo_raw or tipo_raw in ("nan","none",""): continue

        apellido = str(row.get(APELLIDO_COL,"")).strip()
        nombre   = str(row.get(NOMBRE_COL,"")).strip()
        legajo   = buscar_legajo(apellido, nombre)
        if not legajo:
            errores.append(f"Fila {idx+2}: no se encontró legajo para '{apellido} {nombre}'")
            continue

        fecha_sol = parse_fecha_texto(row.get(FECHA_COL,""))
        if fecha_sol:
            periodo = f"{fecha_sol.year}-{fecha_sol.month:02d}"
            if fecha_sol.day >= 25:
                if fecha_sol.month == 12: periodo = f"{fecha_sol.year+1}-01"
                else: periodo = f"{fecha_sol.year}-{fecha_sol.month+1:02d}"
        else:
            periodo = None

        # Ausencias → novedades
        if "avisos de ausencias" in tipo_raw or "certificados" in tipo_raw:
            fecha_falta = parse_fecha_texto(row.get(FECHA_FALTA,""))
            tipo_aus_raw = str(row.get(TIPO_AUSENCIA,"")).strip()
            descripcion  = str(row.get(DESC_COL,"")).strip()
            tipo_nov = "Licencia por enfermedad"
            if "accidente" in tipo_aus_raw.lower(): tipo_nov = "ART"
            elif "otro" in tipo_aus_raw.lower(): tipo_nov = "Otro"
            fecha_str = fecha_falta.strftime("%Y-%m-%d") if fecha_falta else (
                        fecha_sol.strftime("%Y-%m-%d") if fecha_sol else None)
            if not fecha_str:
                errores.append(f"Fila {idx+2}: fecha de falta no encontrada para {apellido}")
                continue
            cur2 = dict_cursor(conn)
            cur2.execute("SELECT id FROM novedades WHERE legajo=%s AND fecha_desde=%s AND tipo=%s",
                         (legajo, fecha_str, tipo_nov))
            if not cur2.fetchone():
                obs = f"{tipo_aus_raw}: {descripcion}" if descripcion else tipo_aus_raw
                cur2.execute("""INSERT INTO novedades (legajo,tipo,fecha_desde,fecha_hasta,descripcion,estado,creado_por)
                    VALUES (%s,%s,%s,%s,%s,'pendiente',%s)""",
                    (legajo, tipo_nov, fecha_str, fecha_str, obs, usuario))
                nov_nuevas += 1
        else:
            match = None
            for key, val in TIPO_MAP.items():
                if key in tipo_raw: match = val; break
            if not match:
                errores.append(f"Fila {idx+2}: tipo no reconocido '{tipo_raw}'")
                continue
            tipo_adel, monto_col = match
            monto = parse_monto(row.get(monto_col,""))
            if not monto:
                errores.append(f"Fila {idx+2}: monto vacío para {apellido}")
                continue
            if not periodo:
                errores.append(f"Fila {idx+2}: fecha inválida para {apellido}")
                continue
            cur2 = dict_cursor(conn)
            cur2.execute("""INSERT INTO adelantos (legajo,periodo,tipo,monto,descripcion,creado_por)
                VALUES (%s,%s,%s,%s,%s,%s)""",
                (legajo, periodo, tipo_adel, monto, f"Importado desde {nombre_archivo}", usuario))
            adel_nuevos += 1

    conn.commit()
    conn.close()
    log_auditoria(usuario, "IMPORTAR_SOLICITUDES", detalle=f"{nombre_archivo}: {nov_nuevas} nov, {adel_nuevos} adel")
    return nov_nuevas, adel_nuevos, len(errores), errores

def importar_vacaciones(file_bytes, nombre_archivo: str, usuario: str):
    import io
    if isinstance(file_bytes, bytes):
        file_bytes = io.BytesIO(file_bytes)
    try:
        try:
            df = pd.read_excel(file_bytes, sheet_name="Resumen", header=1, dtype=str)
        except:
            file_bytes.seek(0)
            df = pd.read_excel(file_bytes, header=0, dtype=str)
    except Exception as e:
        return 0, 0, 1, [f"No se pudo leer el archivo: {e}"]

    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("SELECT legajo, apellido, nombre FROM colaboradores WHERE activo=1")
    colab_rows = cur.fetchall()

    def buscar_legajo(nombre_raw):
        if not nombre_raw or str(nombre_raw).strip() in ("","nan","None"): return None
        nombre_raw = str(nombre_raw).strip().lower()
        palabras = nombre_raw.split()
        for r in colab_rows:
            ap = r["apellido"].lower()
            if ap in nombre_raw or nombre_raw.split()[0] in ap: return str(r["legajo"])
        for r in colab_rows:
            ap = r["apellido"].lower()
            for p in palabras:
                if len(p)>=4 and len(ap)>=4:
                    diffs = sum(1 for a,b in zip(p,ap) if a!=b)+abs(len(p)-len(ap))
                    if diffs<=1: return str(r["legajo"])
        return None

    def to_date(val):
        if isinstance(val, datetime): return val.date()
        if isinstance(val, date): return val
        if isinstance(val, str) and val.strip() not in ("","nan","None","-"):
            for fmt in ("%Y-%m-%d","%d/%m/%Y"):
                try: return datetime.strptime(val.strip(),fmt).date()
                except: pass
        return None

    importadas = omitidas = 0
    errores = []

    for idx, row in df.iterrows():
        vals = list(row.values)
        if not vals or str(vals[0]).strip() in ("","nan","None","Apellido y nombre"): continue
        nombre_raw = str(vals[0]).strip()
        legajo = buscar_legajo(nombre_raw)
        if not legajo:
            errores.append(f"Fila {idx+2}: no se encontró '{nombre_raw}'")
            continue

        rangos = []
        try:
            s1 = to_date(vals[1]); r1 = to_date(vals[2])
            if s1 and r1 and r1 > s1: rangos.append((s1, r1-timedelta(days=1)))
        except: pass
        try:
            s2 = to_date(vals[4]); r2 = to_date(vals[5])
            if s2 and r2 and r2 > s2: rangos.append((s2, r2-timedelta(days=1)))
        except: pass

        if not rangos: omitidas += 1; continue

        for desde, hasta in rangos:
            cur2 = dict_cursor(conn)
            cur2.execute("SELECT id FROM novedades WHERE legajo=%s AND tipo='Vacaciones' AND fecha_desde=%s",
                         (legajo, str(desde)))
            if not cur2.fetchone():
                cur2.execute("""INSERT INTO novedades (legajo,tipo,fecha_desde,fecha_hasta,descripcion,estado,creado_por,aprobado_por)
                    VALUES (%s,'Vacaciones',%s,%s,%s,'aprobado',%s,%s)""",
                    (legajo, str(desde), str(hasta), f"Importado desde {nombre_archivo}", usuario, usuario))
                importadas += 1
            else:
                omitidas += 1

    conn.commit()
    conn.close()
    log_auditoria(usuario, "IMPORTAR_VACACIONES", detalle=f"{nombre_archivo}: {importadas} períodos")
    return importadas, omitidas, len(errores), errores
