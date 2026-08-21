"""
Base de datos PostgreSQL — OK Accesorios RRHH
Conecta a Supabase. Los datos persisten permanentemente.
"""
import os, hashlib
from datetime import datetime
from pathlib import Path
import psycopg2
import psycopg2.extras

def _get_db_url():
    try:
        import streamlit as st
        return st.secrets["DATABASE_URL"]
    except:
        return os.environ.get("DATABASE_URL","")

def get_conn():
    url = _get_db_url()
    conn = psycopg2.connect(url, connect_timeout=15)
    conn.autocommit = False
    return conn

def dict_cursor(conn):
    return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def _count(conn, tabla):
    c = dict_cursor(conn)
    c.execute(f"SELECT COUNT(*) as n FROM {tabla}")
    row = c.fetchone()
    return row['n'] if row else 0

def init_db():
    conn = get_conn()
    c = dict_cursor(conn)

    c.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL,
        nombre TEXT NOT NULL, password TEXT NOT NULL,
        rol TEXT NOT NULL, activo INTEGER DEFAULT 1,
        creado_en TEXT DEFAULT (NOW()::text))""")

    c.execute("""CREATE TABLE IF NOT EXISTS colaboradores (
        id SERIAL PRIMARY KEY, legajo TEXT UNIQUE NOT NULL,
        apellido TEXT NOT NULL, nombre TEXT NOT NULL, sector TEXT NOT NULL,
        turno TEXT, entrada TEXT, salida TEXT, entrada_sab TEXT, salida_sab TEXT,
        break_min INTEGER DEFAULT 0, almuerzo_min INTEGER DEFAULT 60,
        rotativo INTEGER DEFAULT 0, tipo TEXT DEFAULT 'efectivo',
        activo INTEGER DEFAULT 1, fecha_alta TEXT DEFAULT (NOW()::text),
        observaciones TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS marcaciones (
        id SERIAL PRIMARY KEY, legajo TEXT NOT NULL, fecha TEXT NOT NULL,
        horas_raw TEXT, ingreso TEXT, egreso TEXT, sector TEXT,
        importado_en TEXT DEFAULT (NOW()::text), fuente TEXT,
        UNIQUE(legajo, fecha))""")

    c.execute("""CREATE TABLE IF NOT EXISTS novedades (
        id SERIAL PRIMARY KEY, legajo TEXT NOT NULL, tipo TEXT NOT NULL,
        fecha_desde TEXT NOT NULL, fecha_hasta TEXT, descripcion TEXT,
        estado TEXT DEFAULT 'pendiente', creado_por TEXT, aprobado_por TEXT,
        creado_en TEXT DEFAULT (NOW()::text), modificado_en TEXT)""")

    c.execute("""CREATE TABLE IF NOT EXISTS adelantos (
        id SERIAL PRIMARY KEY, legajo TEXT NOT NULL, periodo TEXT NOT NULL,
        tipo TEXT NOT NULL, monto NUMERIC, descripcion TEXT,
        creado_por TEXT, creado_en TEXT DEFAULT (NOW()::text))""")

    c.execute("""CREATE TABLE IF NOT EXISTS auditoria (
        id SERIAL PRIMARY KEY, usuario TEXT NOT NULL, accion TEXT NOT NULL,
        tabla TEXT, registro_id INTEGER, detalle TEXT,
        fecha TEXT DEFAULT (NOW()::text))""")

    c.execute("""CREATE TABLE IF NOT EXISTS feriados (
        id SERIAL PRIMARY KEY, fecha TEXT UNIQUE NOT NULL,
        descripcion TEXT, tipo TEXT DEFAULT 'nacional')""")

    conn.commit()

    # Datos iniciales
    if _count(conn, "usuarios") == 0:
        c.execute("INSERT INTO usuarios (username,nombre,password,rol) VALUES (%s,%s,%s,%s)",
                  ("admin","Administrador",hash_pw("admin2026"),"admin"))
        conn.commit()

    if _count(conn, "colaboradores") == 0:
        cols = [
            ("24","GUZMAN","WILFREDO VICTOR","Administración","","08:00","17:30","10:00","14:00",0,90,0,"efectivo"),
            ("162","BRANDANI","GABRIELA","Administración","","09:00","18:00","10:00","14:00",0,60,0,"efectivo"),
            ("189","GUTIERREZ FRANCO","NICOLAS","Administración","","08:00","17:00","10:00","14:00",0,60,0,"efectivo"),
            ("200","SANS","JOAQUIN ALBERTO","Administración","","08:30","17:30","10:00","14:00",0,60,0,"efectivo"),
            ("103","TEIXIDO","PABLO","Compras","","09:00","18:00","09:00","13:00",0,60,0,"efectivo"),
            ("25","ATENCIO","MAXIMILIANO","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0,"efectivo"),
            ("48","GIUNTA","LEONEL ALEJANDRO","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0,"efectivo"),
            ("62","ARCAR","HERNAN ADOLFO","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0,"efectivo"),
            ("115","CHAVEZ","MARCELA BELEN","Montecaseros","","09:00","18:00","09:00","13:00",15,60,0,"efectivo"),
            ("142","MIRANDA","JONATHAN","Montecaseros","","09:00","18:00","09:00","13:00",15,60,0,"efectivo"),
            ("167","SCHOENFELD MUÑOZ","GIMENA ALEJANDRA","Montecaseros","","09:00","18:00","09:00","13:00",0,60,0,"efectivo"),
            ("179","FARA","FERNANDO GABRIEL","Montecaseros","","09:00","18:00","09:00","13:00",15,60,0,"efectivo"),
            ("71","AMILLS","JUAN PABLO","Local calle San Juan","","10:00","19:00","10:00","14:00",15,60,0,"efectivo"),
            ("180","TEIXIDO","ANDREA","Local calle San Juan","","10:00","19:00","10:00","14:00",15,60,0,"efectivo"),
            ("190","RODRIGUEZ","DEBORA VANINA","Local calle San Juan","","10:00","19:00","10:00","14:00",15,60,0,"efectivo"),
            ("52","CASTILLO","GUILLERMO LEONARDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1,"efectivo"),
            ("74","CASTRO CORREA","JUAN ALFREDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1,"efectivo"),
            ("170","CABAÑEZ","LEONARDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1,"efectivo"),
            ("181","FIGUEROA","GABRIEL EDUARDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1,"efectivo"),
            ("185","ANDRADA","FERNANDO","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1,"efectivo"),
            ("191","SCAMARDELLA","ADRIAN EZEQUIEL","Logistica","rotativo","08:00","17:00","08:00","13:00",0,60,1,"efectivo"),
        ]
        c.executemany("""INSERT INTO colaboradores
            (legajo,apellido,nombre,sector,turno,entrada,salida,entrada_sab,salida_sab,
             break_min,almuerzo_min,rotativo,tipo)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (legajo) DO NOTHING""", cols)
        feriados = [
            ("2026-01-01","Año Nuevo"),("2026-02-16","Carnaval"),("2026-02-17","Carnaval"),
            ("2026-03-24","Día Nacional de la Memoria"),("2026-04-02","Día del Veterano"),
            ("2026-04-03","Viernes Santo"),("2026-05-01","Día del Trabajador"),
            ("2026-05-25","Revolución de Mayo"),("2026-06-15","Güemes"),
            ("2026-06-20","Belgrano"),("2026-07-09","Día de la Independencia"),
            ("2026-08-17","San Martín"),("2026-10-12","Diversidad Cultural"),
            ("2026-11-23","Soberanía Nacional"),("2026-12-08","Inmaculada Concepción"),
            ("2026-12-25","Navidad"),
        ]
        c.executemany("INSERT INTO feriados (fecha,descripcion) VALUES (%s,%s) ON CONFLICT (fecha) DO NOTHING", feriados)
        conn.commit()
    conn.close()

def log_auditoria(usuario, accion, tabla=None, registro_id=None, detalle=None):
    try:
        conn = get_conn()
        c = dict_cursor(conn)
        c.execute("INSERT INTO auditoria (usuario,accion,tabla,registro_id,detalle) VALUES (%s,%s,%s,%s,%s)",
                  (usuario,accion,tabla,registro_id,detalle))
        conn.commit()
        conn.close()
    except:
        pass

def hacer_backup():
    conn = get_conn()
    c = dict_cursor(conn)
    tablas = ["usuarios","colaboradores","marcaciones","novedades","adelantos","feriados"]
    out = [f"-- Backup OK Accesorios RRHH {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    for t in tablas:
        try:
            c.execute(f"SELECT * FROM {t}")
            rows = c.fetchall()
            out.append(f"\n-- {t}: {len(rows)} registros\n")
        except:
            pass
    conn.close()
    return "".join(out)

DB_PATH = Path("/tmp/rrhh_compat.db")
