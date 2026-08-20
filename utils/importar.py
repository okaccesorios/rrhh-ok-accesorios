"""
Importador de marcaciones desde Excel (formato InOutData).
Formato: No-Acceso | Nombre | Departamento | Fecha | Hora (marcaciones separadas por espacios)
"""
import pandas as pd
from datetime import datetime, date, timedelta
from utils.database import get_conn, log_auditoria

def _parse_fecha(val):
    """Convierte distintos formatos de fecha a date."""
    if isinstance(val, (datetime, date)):
        return val.date() if isinstance(val, datetime) else val
    if isinstance(val, str):
        val = val.strip()
        for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m/%d/%Y", "%-d/%m/%Y"):
            try:
                return datetime.strptime(val, fmt).date()
            except:
                pass
    return None

def _parse_horas(raw):
    """
    Extrae ingreso y egreso de la cadena de marcaciones.
    Ej: "08:54 10:56 11:02 12:56 13:57 18:15" → ingreso=08:54, egreso=18:15
    """
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
            except:
                pass
    if not horas_validas:
        return None, None, raw
    return horas_validas[0], horas_validas[-1], raw

def importar_excel(file_bytes, nombre_archivo: str, usuario: str, sector_override: str = None):
    """
    Lee el Excel de marcaciones del reloj (formato InOutData) y lo inserta en la BD.
    Devuelve (nuevos, actualizados, errores, lista_errores)
    """
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

    required = ["legajo","fecha"]
    missing  = [r for r in required if r not in col_map]
    if missing:
        return 0, 0, 1, [f"Columnas no encontradas: {missing}. Columnas en el archivo: {list(df.columns)}"]

    conn      = get_conn()
    nuevos    = 0
    actualizados = 0
    errores   = []

    for idx, row in df.iterrows():
        legajo = str(row.get(col_map["legajo"], "")).strip().lstrip("0") or str(row.get(col_map["legajo"], "")).strip()
        if not legajo or legajo in ("nan","None",""):
            continue

        fecha_raw = row.get(col_map["fecha"], "")
        fecha = _parse_fecha(fecha_raw)
        if not fecha:
            errores.append(f"Fila {idx+2}: fecha inválida '{fecha_raw}'")
            continue

        horas_raw = row.get(col_map.get("horas",""), "") if "horas" in col_map else ""
        ingreso, egreso, raw = _parse_horas(horas_raw)

        sector = sector_override or row.get(col_map.get("sector",""), "") or ""
        if hasattr(sector, "strip"):
            sector = str(sector).strip()

        fecha_str = fecha.strftime("%Y-%m-%d")

        existing = conn.execute(
            "SELECT id FROM marcaciones WHERE legajo=? AND fecha=?",
            (legajo, fecha_str)
        ).fetchone()

        if existing:
            conn.execute("""UPDATE marcaciones
                SET horas_raw=?, ingreso=?, egreso=?, sector=?,
                    importado_en=datetime('now','localtime'), fuente=?
                WHERE legajo=? AND fecha=?""",
                (raw, ingreso, egreso, sector, nombre_archivo, legajo, fecha_str))
            actualizados += 1
        else:
            conn.execute("""INSERT INTO marcaciones
                (legajo, fecha, horas_raw, ingreso, egreso, sector, fuente)
                VALUES (?,?,?,?,?,?,?)""",
                (legajo, fecha_str, raw, ingreso, egreso, sector, nombre_archivo))
            nuevos += 1

    conn.commit()
    conn.close()

    log_auditoria(usuario, "IMPORTAR_MARCACIONES", "marcaciones",
                  detalle=f"{nombre_archivo}: {nuevos} nuevas, {actualizados} actualizadas")

    return nuevos, actualizados, len(errores), errores

def importar_solicitudes(file_bytes, nombre_archivo: str, usuario: str):
    """
    Importa el Excel de Solicitudes Administrativas (formulario JotForm).
    Separa automáticamente en novedades y adelantos según el tipo de solicitud.
    Devuelve (novedades_nuevas, adelantos_nuevos, errores, lista_errores)
    """
    import io
    if isinstance(file_bytes, bytes):
        file_bytes = io.BytesIO(file_bytes)
    try:
        df = pd.read_excel(file_bytes, header=0, dtype=str)
    except Exception as e:
        return 0, 0, 1, [f"No se pudo leer el archivo: {e}"]

    # Normalizar columnas
    df.columns = [str(c).strip() for c in df.columns]

    TIPO_COL      = "Tipo de solicitud"
    FECHA_COL     = "Fecha"
    NOMBRE_COL    = "Nombre"
    APELLIDO_COL  = "Apellido"
    SECTOR_COL    = "Área/ Sector"
    MONTO_COL     = "Monto solicitado"
    FACTURA_COL   = "Importe de la factura"
    GASTO_COL     = "Importe del gasto"
    FECHA_FALTA   = "Fecha de la falta"
    TIPO_AUSENCIA = "Tipo de ausencia:"
    DESC_COL      = "Descripción breve de la situación"

    # Mapeo de apellido → legajo
    conn = get_conn()
    colab_rows = conn.execute("SELECT legajo, apellido, nombre FROM colaboradores WHERE activo=1").fetchall()
    conn.close()

    def _buscar_legajo(apellido_raw, nombre_raw):
        """Busca legajo por coincidencia de apellido (flexible)."""
        if not apellido_raw:
            return None
        ap = str(apellido_raw).strip().lower()
        no = str(nombre_raw).strip().lower() if nombre_raw else ""
        # Exacto primero
        for r in colab_rows:
            if r["apellido"].lower() == ap:
                return str(r["legajo"])
        # Parcial: el apellido del formulario está contenido en el apellido BD o viceversa
        for r in colab_rows:
            bd_ap = r["apellido"].lower()
            if ap in bd_ap or bd_ap in ap:
                return str(r["legajo"])
        # Por nombre también
        for r in colab_rows:
            bd_no = r["nombre"].lower()
            if no and (no in bd_no or bd_no in no):
                return str(r["legajo"])
        return None

    def _parse_monto(val):
        if not val or str(val).strip() in ("", "nan", "None"):
            return None
        try:
            return float(str(val).replace(".", "").replace(",", "."))
        except:
            try:
                return float(str(val))
            except:
                return None

    TIPO_MAP = {
        "adelanto de sueldo":                              ("adelanto",              "Adelanto de sueldo",        MONTO_COL),
        "compra de mercadería":                            ("descuento_mercaderia",   "Compra de mercadería",      FACTURA_COL),
        "solicitud de pago de gasto":                      ("otro",                   "Pago de gasto",             GASTO_COL),
        "avisos de ausencias y envío de certificados medicos": None,  # → novedades
    }

    conn        = get_conn()
    nov_nuevas  = 0
    adel_nuevos = 0
    errores     = []

    MESES_ES = {"jan":"01","feb":"02","mar":"03","apr":"04","may":"05","jun":"06",
                "jul":"07","aug":"08","sep":"09","oct":"10","nov":"11","dec":"12",
                "ene":"01","abr":"04","ago":"08"}

    def _parse_fecha_texto(val):
        """Parsea fechas tipo 'jun 8, 2026' o '2026-06-08'."""
        if not val or str(val).strip() in ("", "nan", "None"):
            return None
        val = str(val).strip()
        # Formato "jun 8, 2026"
        import re
        m = re.match(r"([a-záéíóú]+)\s+(\d+),?\s+(\d{4})", val, re.IGNORECASE)
        if m:
            mes_txt, dia, anio = m.groups()
            mes_num = MESES_ES.get(mes_txt.lower()[:3])
            if mes_num:
                try:
                    from datetime import date
                    return date(int(anio), int(mes_num), int(dia))
                except:
                    pass
        # ISO
        try:
            from datetime import datetime
            return datetime.strptime(val, "%Y-%m-%d").date()
        except:
            pass
        return None

    for idx, row in df.iterrows():
        tipo_raw = str(row.get(TIPO_COL, "")).strip().lower()
        if not tipo_raw or tipo_raw in ("nan", "none", ""):
            continue

        apellido = str(row.get(APELLIDO_COL, "")).strip()
        nombre   = str(row.get(NOMBRE_COL, "")).strip()
        legajo   = _buscar_legajo(apellido, nombre)

        if not legajo:
            errores.append(f"Fila {idx+2}: no se encontró legajo para '{apellido} {nombre}'")
            continue

        fecha_sol = _parse_fecha_texto(row.get(FECHA_COL, ""))
        periodo   = fecha_sol.strftime("%Y-%m") if fecha_sol else ""

        # ── AUSENCIAS → novedades ──────────────────────────────
        if "avisos de ausencias" in tipo_raw or "certificados" in tipo_raw:
            fecha_falta   = _parse_fecha_texto(row.get(FECHA_FALTA, ""))
            tipo_aus_raw  = str(row.get(TIPO_AUSENCIA, "")).strip()
            descripcion   = str(row.get(DESC_COL, "")).strip()

            tipo_nov = "Licencia por enfermedad"
            if "accidente" in tipo_aus_raw.lower():
                tipo_nov = "ART"
            elif "otro" in tipo_aus_raw.lower():
                tipo_nov = "Otro"

            fecha_str = fecha_falta.strftime("%Y-%m-%d") if fecha_falta else (
                        fecha_sol.strftime("%Y-%m-%d") if fecha_sol else None)
            if not fecha_str:
                errores.append(f"Fila {idx+2}: fecha de falta no encontrada para {apellido}")
                continue

            # Evitar duplicados
            existe = conn.execute(
                "SELECT id FROM novedades WHERE legajo=? AND fecha_desde=? AND tipo=?",
                (legajo, fecha_str, tipo_nov)
            ).fetchone()
            if not existe:
                obs = f"{tipo_aus_raw}: {descripcion}" if descripcion else tipo_aus_raw
                conn.execute("""INSERT INTO novedades
                    (legajo, tipo, fecha_desde, fecha_hasta, descripcion, estado, creado_por)
                    VALUES (?,?,?,?,?,'pendiente',?)""",
                    (legajo, tipo_nov, fecha_str, fecha_str, obs, usuario))
                nov_nuevas += 1

        # ── ADELANTOS / COMPRAS → adelantos ───────────────────
        else:
            match = None
            for key, val in TIPO_MAP.items():
                if key in tipo_raw and val is not None:
                    match = val
                    break
            if not match:
                errores.append(f"Fila {idx+2}: tipo no reconocido '{tipo_raw}'")
                continue

            tipo_adel, desc_adel, monto_col = match
            monto = _parse_monto(row.get(monto_col, ""))

            if not monto:
                errores.append(f"Fila {idx+2}: monto vacío para {apellido} ({tipo_raw})")
                continue

            if not periodo:
                errores.append(f"Fila {idx+2}: fecha inválida para {apellido}")
                continue

            # Regla 25-24: desde el día 25 pertenece al mes siguiente
            if fecha_sol.day >= 25:
                if fecha_sol.month == 12:
                    periodo = f"{fecha_sol.year + 1}-01"
                else:
                    periodo = f"{fecha_sol.year}-{fecha_sol.month + 1:02d}"

            conn.execute("""INSERT INTO adelantos
                (legajo, periodo, tipo, monto, descripcion, creado_por)
                VALUES (?,?,?,?,?,?)""",
                (legajo, periodo, tipo_adel, monto,
                 f"{desc_adel} — importado desde {nombre_archivo}", usuario))
            adel_nuevos += 1

    conn.commit()
    conn.close()

    log_auditoria(usuario, "IMPORTAR_SOLICITUDES", "novedades+adelantos",
                  detalle=f"{nombre_archivo}: {nov_nuevas} novedades, {adel_nuevos} adelantos")

    return nov_nuevas, adel_nuevos, len(errores), errores
    """
    Lee el Excel de marcaciones y lo inserta/actualiza en la BD.
    Devuelve (nuevos, actualizados, errores, lista_errores)
    """
    try:
        import io
        if isinstance(file_bytes, bytes):
            file_bytes = io.BytesIO(file_bytes)
        df = pd.read_excel(file_bytes, header=0, dtype=str)
    except Exception as e:
        return 0, 0, 1, [f"No se pudo leer el archivo: {e}"]

    # Normalizar nombres de columnas
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Mapeo flexible de columnas
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

    required = ["legajo","fecha"]
    missing  = [r for r in required if r not in col_map]
    if missing:
        return 0, 0, 1, [f"Columnas no encontradas: {missing}. Columnas en el archivo: {list(df.columns)}"]

    conn      = get_conn()
    nuevos    = 0
    actualizados = 0
    errores   = []

    for idx, row in df.iterrows():
        legajo = str(row.get(col_map["legajo"], "")).strip().lstrip("0") or str(row.get(col_map["legajo"], "")).strip()
        if not legajo or legajo in ("nan","None",""):
            continue

        fecha_raw = row.get(col_map["fecha"], "")
        fecha = _parse_fecha(fecha_raw)
        if not fecha:
            errores.append(f"Fila {idx+2}: fecha inválida '{fecha_raw}'")
            continue

        horas_raw = row.get(col_map.get("horas",""), "") if "horas" in col_map else ""
        ingreso, egreso, raw = _parse_horas(horas_raw)

        sector = sector_override or row.get(col_map.get("sector",""), "") or ""
        if hasattr(sector, "strip"):
            sector = str(sector).strip()

        fecha_str = fecha.strftime("%Y-%m-%d")

        # Upsert
        existing = conn.execute(
            "SELECT id FROM marcaciones WHERE legajo=? AND fecha=?",
            (legajo, fecha_str)
        ).fetchone()

        if existing:
            conn.execute("""UPDATE marcaciones
                SET horas_raw=?, ingreso=?, egreso=?, sector=?,
                    importado_en=datetime('now','localtime'), fuente=?
                WHERE legajo=? AND fecha=?""",
                (raw, ingreso, egreso, sector, nombre_archivo, legajo, fecha_str))
            actualizados += 1
        else:
            conn.execute("""INSERT INTO marcaciones
                (legajo, fecha, horas_raw, ingreso, egreso, sector, fuente)
                VALUES (?,?,?,?,?,?,?)""",
                (legajo, fecha_str, raw, ingreso, egreso, sector, nombre_archivo))
            nuevos += 1

    conn.commit()
    conn.close()

    log_auditoria(usuario, "IMPORTAR_MARCACIONES", "marcaciones",
                  detalle=f"{nombre_archivo}: {nuevos} nuevas, {actualizados} actualizadas")

    return nuevos, actualizados, len(errores), errores


def importar_vacaciones(file_bytes, nombre_archivo: str, usuario: str):
    """
    Importa el Excel de vacaciones (hoja Resumen).
    Formato: Apellido y nombre | Salida | Reincorp | Dias | Salida2 | Reincorp2
    """
    import io
    from datetime import datetime, date, timedelta
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
    colab_rows = conn.execute(
        "SELECT legajo, apellido, nombre FROM colaboradores WHERE activo=1"
    ).fetchall()

    def _buscar_legajo(nombre_raw):
        if not nombre_raw or str(nombre_raw).strip() in ("", "nan", "None"):
            return None
        nombre_raw = str(nombre_raw).strip().lower()
        for r in colab_rows:
            ap = r["apellido"].lower()
            if ap in nombre_raw or nombre_raw.split()[0] in ap:
                return str(r["legajo"])
        return None

    def _to_date(val):
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, date):
            return val
        if isinstance(val, str) and val.strip() not in ("", "nan", "None", "-"):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
                try:
                    return datetime.strptime(val.strip(), fmt).date()
                except:
                    pass
        return None

    importadas = omitidas = 0
    errores = []

    for idx, row in df.iterrows():
        vals = list(row.values)
        if not vals or str(vals[0]).strip() in ("", "nan", "None", "Apellido y nombre"):
            continue
        nombre_raw = str(vals[0]).strip()
        legajo = _buscar_legajo(nombre_raw)
        if not legajo:
            errores.append(f"Fila {idx+2}: no se encontró '{nombre_raw}'")
            continue

        rangos = []
        try:
            s1 = _to_date(vals[1]); r1 = _to_date(vals[2])
            if s1 and r1 and r1 > s1:
                rangos.append((s1, r1 - timedelta(days=1)))
        except: pass
        try:
            s2 = _to_date(vals[4]); r2 = _to_date(vals[5])
            if s2 and r2 and r2 > s2:
                rangos.append((s2, r2 - timedelta(days=1)))
        except: pass

        if not rangos:
            omitidas += 1
            continue

        for desde, hasta in rangos:
            existe = conn.execute(
                "SELECT id FROM novedades WHERE legajo=? AND tipo='Vacaciones' AND fecha_desde=?",
                (legajo, str(desde))
            ).fetchone()
            if not existe:
                conn.execute("""INSERT INTO novedades
                    (legajo,tipo,fecha_desde,fecha_hasta,descripcion,estado,creado_por,aprobado_por)
                    VALUES (?,?,?,?,?,'aprobado',?,?)""",
                    (legajo,"Vacaciones",str(desde),str(hasta),
                     f"Importado desde {nombre_archivo}",usuario,usuario))
                importadas += 1
            else:
                omitidas += 1

    conn.commit()
    conn.close()
    log_auditoria(usuario,"IMPORTAR_VACACIONES","novedades",
                  detalle=f"{nombre_archivo}: {importadas} períodos")
    return importadas, omitidas, len(errores), errores
