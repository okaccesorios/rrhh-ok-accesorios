import streamlit as st
from utils.exportar import generar_excel
from utils.auth import usuario_actual, log_auditoria
from datetime import date

MESES_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
            7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

def show():
    st.markdown("""
    <div class="main-header">
      <div><h1>📤 Exportar Papel de Trabajo</h1>
      <span>Generá el Excel completo para el estudio contable</span></div>
    </div>""", unsafe_allow_html=True)

    u = usuario_actual()

    st.markdown("""
    <div class="alert-info">
      📋 El Excel generado incluye: <strong>Panel General · Detalle por Empleado ·
      Horas Extras · Tardanzas</strong> — listo para enviar al contador.
    </div>""", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        hoy = date.today()
        anio = st.number_input("Año", value=hoy.year, min_value=2024, max_value=2030)
        mes  = st.selectbox("Mes", list(range(1,13)),
                            index=hoy.month-1,
                            format_func=lambda m: MESES_ES[m])
        periodo = f"{anio}-{mes:02d}"

    with col2:
        st.markdown(f"""
        <div style="background:white;border:1px solid #e0e0e0;border-radius:8px;
             padding:1.5rem;margin-top:0.5rem;">
          <div style="font-size:2rem;text-align:center;">📊</div>
          <div style="text-align:center;font-weight:700;color:#1F3864;font-size:1.1rem;">
            {MESES_ES[mes]} {anio}
          </div>
          <div style="text-align:center;color:#666;font-size:0.85rem;margin-top:0.3rem;">
            Papel de Trabajo Horario
          </div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🚀 Generar y descargar Excel", type="primary", use_container_width=True):
        with st.spinner("Calculando datos y generando el Excel..."):
            try:
                xlsx_bytes = generar_excel(periodo)
                nombre_archivo = f"Papel_Trabajo_{MESES_ES[mes]}_{anio}.xlsx"
                log_auditoria(u["username"], "EXPORTAR_EXCEL", detalle=f"{periodo}")
                st.download_button(
                    label=f"⬇️ Descargar {nombre_archivo}",
                    data=xlsx_bytes,
                    file_name=nombre_archivo,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
                st.success("✅ Excel generado correctamente. Hacé clic en el botón de arriba para descargarlo.")
            except Exception as e:
                st.error(f"Error al generar el Excel: {e}")
                st.exception(e)
