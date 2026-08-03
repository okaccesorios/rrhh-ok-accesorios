# OK Accesorios — Sistema de Gestión RRHH

Sistema web de gestión de novedades para liquidación de haberes.

## Cómo deployar en Streamlit Cloud (gratuito)

### Paso 1 — Crear cuenta en GitHub
1. Ir a https://github.com → Sign up
2. Crear cuenta con tu mail

### Paso 2 — Subir el código
1. En GitHub → New repository → Nombre: `rrhh-ok-accesorios` → Public → Create
2. Subir todos los archivos de esta carpeta al repositorio

### Paso 3 — Deployar en Streamlit Cloud
1. Ir a https://share.streamlit.io → Sign in with GitHub
2. New app → seleccionar tu repositorio
3. Main file path: `app.py`
4. Deploy!

En 2 minutos tenés la URL: `https://tu-usuario-rrhh-ok-accesorios.streamlit.app`

## Usuario inicial
- **Usuario:** admin
- **Contraseña:** admin2026
- ⚠️ Cambiar la contraseña después del primer login

## Módulos
- 📊 Dashboard — indicadores del período actual
- ⏱️ Importar reloj — sube el Excel de marcaciones por sector
- 📋 Novedades — bandeja con flujo pendiente → aprobado → enviado
- 👥 Colaboradores — gestión de la plantilla
- 💰 Adelantos — adelantos, descuentos y sanciones
- 📤 Exportar — genera el Excel para el contador
- 📅 Feriados — gestión de feriados
- 🔑 Usuarios — alta y permisos
- 🔍 Auditoría — historial de cambios
- 💾 Backup — respaldo de la base de datos
