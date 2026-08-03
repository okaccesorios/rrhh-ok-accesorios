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
    Lee el Excel de marcaciones y lo inserta/actualiza en la BD.
    Devuelve (nuevos, actualizados, errores, lista_errores)
    """
    try:
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
