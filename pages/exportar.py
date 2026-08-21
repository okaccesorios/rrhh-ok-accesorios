import streamlit as st
from utils.exportar import generar_excel
from utils.database import log_auditoria
from utils.auth import usuario_actual
from datetime import date

MESES_ES = {1:"Enero",2:"Febrero",3:"Marzo",4:"Abril",5:"Mayo",6:"Junio",
            7:"Julio",8:"Agosto",9:"Septiembre",10:"Octubre",11:"Noviembre",12:"Diciembre"}

def show():
    st.markdown('<div class="main-header"><div><h1>📤 Exportar Papel de Trabajo</h1><span>Generá el Excel para el estudio contable</span></div></div>', unsafe_allow_html=True)
    u = usuario_actual()
    col1,col2 = st.columns(2)
    with col1:
        hoy = date.today()
        anio = st.number_input("Año", value=hoy.year, min_value=2024, max_value=2030)
        mes = st.selectbox("Mes", list(range(1,13)), index=hoy.month-1,
                           format_func=lambda m: MESES_ES[m])
        periodo = f"{anio}-{mes:02d}"
    with col2:
        st.markdown(f"""
        <div style="background:white;border:1px solid #e0e0e0;border-radius:8px;
             padding:1.5rem;margin-top:0.5rem;text-align:center;">
          <div style="font-size:2rem;">📊</div>
          <div style="font-weight:700;color:#1F3864;font-size:1.1rem;">{MESES_ES[mes]} {anio}</div>
          <div style="color:#666;font-size:0.85rem;">Papel de Trabajo Horario</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("---")
    if st.button("🚀 Generar y descargar Excel", type="primary", use_container_width=True):
        with st.spinner("Calculando y generando Excel..."):
            try:
                xlsx = generar_excel(periodo)
                nombre = f"Papel_Trabajo_{MESES_ES[mes]}_{anio}.xlsx"
                log_auditoria(u["username"],"EXPORTAR_EXCEL",detalle=periodo)
                st.download_button(f"⬇️ Descargar {nombre}", data=xlsx,
                                   file_name=nombre,
                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                   use_container_width=True)
                st.success("✅ Excel generado. Hacé clic arriba para descargar.")
            except Exception as e:
                st.error(f"Error: {e}")
                st.exception(e)
