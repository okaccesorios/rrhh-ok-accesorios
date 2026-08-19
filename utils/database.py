"""
Base de datos SQLite — OK Accesorios RRHH
Todas las tablas y funciones de acceso centralizadas aquí.
"""
import sqlite3, hashlib, os, shutil
from datetime import datetime, date
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "rrhh.db"
DB_PATH.parent.mkdir(exist_ok=True)

def get_conn():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── Usuarios ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        username  TEXT UNIQUE NOT NULL,
        nombre    TEXT NOT NULL,
        password  TEXT NOT NULL,
        rol       TEXT NOT NULL CHECK(rol IN ('admin','rrhh','consulta')),
        activo    INTEGER DEFAULT 1,
        creado_en TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── Colaboradores ─────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS colaboradores (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        legajo      TEXT UNIQUE NOT NULL,
        apellido    TEXT NOT NULL,
        nombre      TEXT NOT NULL,
        sector      TEXT NOT NULL,
        turno       TEXT,
        entrada     TEXT,
        salida      TEXT,
        entrada_sab TEXT,
        salida_sab  TEXT,
        break_min   INTEGER DEFAULT 0,
        almuerzo_min INTEGER DEFAULT 60,
        rotativo    INTEGER DEFAULT 0,
        tipo        TEXT DEFAULT 'efectivo',
        activo      INTEGER DEFAULT 1,
        fecha_alta  TEXT DEFAULT (date('now','localtime')),
        observaciones TEXT
    )""")

    # ── Marcaciones del reloj ─────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS marcaciones (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        legajo      TEXT NOT NULL,
        fecha       TEXT NOT NULL,
        horas_raw   TEXT,
        ingreso     TEXT,
        egreso      TEXT,
        sector      TEXT,
        importado_en TEXT DEFAULT (datetime('now','localtime')),
        fuente      TEXT,
        UNIQUE(legajo, fecha)
    )""")

    # ── Novedades ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS novedades (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        legajo       TEXT NOT NULL,
        tipo         TEXT NOT NULL,
        fecha_desde  TEXT NOT NULL,
        fecha_hasta  TEXT,
        descripcion  TEXT,
        estado       TEXT DEFAULT 'pendiente' CHECK(estado IN ('pendiente','aprobado','rechazado','enviado')),
        creado_por   TEXT,
        aprobado_por TEXT,
        creado_en    TEXT DEFAULT (datetime('now','localtime')),
        modificado_en TEXT
    )""")

    # ── Documentos adjuntos ───────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS documentos (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        legajo      TEXT NOT NULL,
        novedad_id  INTEGER REFERENCES novedades(id),
        nombre      TEXT NOT NULL,
        tipo_mime   TEXT,
        ruta        TEXT NOT NULL,
        subido_por  TEXT,
        subido_en   TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── Adelantos / Descuentos ────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS adelantos (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        legajo      TEXT NOT NULL,
        periodo     TEXT NOT NULL,
        tipo        TEXT NOT NULL CHECK(tipo IN ('adelanto','descuento_mercaderia','sancion','otro')),
        monto       REAL,
        descripcion TEXT,
        creado_por  TEXT,
        creado_en   TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── Auditoría ─────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS auditoria (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario     TEXT NOT NULL,
        accion      TEXT NOT NULL,
        tabla       TEXT,
        registro_id INTEGER,
        detalle     TEXT,
        fecha       TEXT DEFAULT (datetime('now','localtime'))
    )""")

    # ── Feriados ──────────────────────────────────────────────
    c.execute("""CREATE TABLE IF NOT EXISTS feriados (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha       TEXT UNIQUE NOT NULL,
        descripcion TEXT,
        tipo        TEXT DEFAULT 'nacional'
    )""")

    conn.commit()

    # ── Migraciones automáticas ───────────────────────────────
    # Agrega columna 'tipo' a colaboradores si no existe (migración v3.1)
    cols_colab = [row[1] for row in c.execute("PRAGMA table_info(colaboradores)").fetchall()]
    if "tipo" not in cols_colab:
        c.execute("ALTER TABLE colaboradores ADD COLUMN tipo TEXT DEFAULT 'efectivo'")
        conn.commit()

    # ── Usuario admin por defecto ──────────────────────────────
    c.execute("SELECT COUNT(*) FROM usuarios")
    if c.fetchone()[0] == 0:
        c.execute("""INSERT INTO usuarios (username,nombre,password,rol)
                     VALUES (?,?,?,?)""",
                  ("admin","Administrador",hash_pw("admin2026"),"admin"))
        conn.commit()

    # ── Colaboradores de OK Accesorios ────────────────────────
    c.execute("SELECT COUNT(*) FROM colaboradores")
    if c.fetchone()[0] == 0:
        colaboradores = [
            ("24","GUZMAN","WILFREDO VICTOR","Administración","","08:00","17:30","10:00","14:00",0,90,0),
            ("163","BRANDANI","GABRIELA","Administración","","09:00","18:00","10:00","14:00",0,60,0),
            ("189","GUTIERREZ FRANCO","NICOLAS","Administración","","08:00","17:00","10:00","14:00",0,60,0),
            ("200","SANS","JOAQUIN ALBERTO","Administración","","08:30","17:30","10:00","14:00",0,60,0),
            ("103","TEIXIDO","PABLO","Compras","","09:00","18:00","09:00","13:00",0,60,0),
            ("25","ATENCIO","MAXIMILIANO","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0),
            ("48","GIUNTA","LEONEL ALEJANDRO","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0),
            ("62","ARCAR","HERNAN ADOLFO","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0),
            ("115","CHAVEZ","MARCELA BELEN","Montecaseros","","09:00","18:00","09:00","13:00",15,60,0),
            ("142","MIRANDA","JONATHAN","Montecaseros","","09:00","18:00","09:00","13:00",15,60,0),
            ("167","SCHOENFELD MUÑOZ","GIMENA ALEJANDRA","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0),
            ("179","FARA","FERNANDO GABRIEL","Montecaseros","","09:00","18:00","09:00","13:00",15,60,0),
            ("71","AMMILS","JUAN PABLO","Local calle San Juan","","10:00","19:00","10:00","14:00",15,60,0),
            ("180","TEIXIDO","ANDREA","Local calle San Juan","","10:00","19:00","10:00","14:00",15,60,0),
            ("190","RODRIGUEZ","DEBORA VANINA","Local calle San Juan","","10:00","19:00","10:00","14:00",15,60,0),
            ("52","CASTILLO","GUILLERMO LEONARDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1),
            ("74","CASTRO CORREA","JUAN ALFREDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1),
            ("170","CABAÑEZ","LEONARDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1),
            ("181","FIGUEROA","GABRIEL EDUARDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1),
            ("185","ANDRADA","FERNANDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1),
            ("191","SCAMARDELLA","ADRIAN EZEQUIEL","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1),
        ]
        c.executemany("""INSERT OR IGNORE INTO colaboradores
            (legajo,apellido,nombre,sector,turno,entrada,salida,entrada_sab,salida_sab,break_min,almuerzo_min,rotativo)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", colaboradores)

        # Feriados 2026
        feriados_2026 = [
            ("2026-01-01","Año Nuevo"),("2026-02-16","Carnaval"),("2026-02-17","Carnaval"),
            ("2026-03-24","Día Nacional de la Memoria"),("2026-04-02","Día del Veterano"),
            ("2026-04-03","Viernes Santo"),("2026-05-01","Día del Trabajador"),
            ("2026-05-25","Revolución de Mayo"),("2026-06-15","Paso a la Inmortalidad - Güemes"),
            ("2026-06-20","Paso a la Inmortalidad - Belgrano"),("2026-07-09","Día de la Independencia"),
            ("2026-08-17","Paso a la Inmortalidad - San Martín"),("2026-10-12","Diversidad Cultural"),
            ("2026-11-23","Soberanía Nacional"),("2026-12-08","Inmaculada Concepción"),
            ("2026-12-25","Navidad"),
        ]
        c.executemany("INSERT OR IGNORE INTO feriados (fecha,descripcion) VALUES (?,?)", feriados_2026)
        conn.commit()

    conn.close()

# ── Funciones de auditoría ────────────────────────────────────────
def log_auditoria(usuario, accion, tabla=None, registro_id=None, detalle=None):
    conn = get_conn()
    conn.execute("""INSERT INTO auditoria (usuario,accion,tabla,registro_id,detalle)
                    VALUES (?,?,?,?,?)""", (usuario,accion,tabla,registro_id,detalle))
    conn.commit()
    conn.close()

# ── Backup ────────────────────────────────────────────────────────
def hacer_backup():
    backup_dir = Path(__file__).parent.parent / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = backup_dir / f"rrhh_backup_{ts}.db"
    shutil.copy2(str(DB_PATH), str(dst))
    # Mantener solo los últimos 10 backups
    backups = sorted(backup_dir.glob("rrhh_backup_*.db"))
    for old in backups[:-10]:
        old.unlink()
    return str(dst)
