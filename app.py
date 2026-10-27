import io
import pandas as pd
import numpy as np
import streamlit as st
from modelo import SUELOS, Config, simular

st.set_page_config(page_title='Simulador hídrico y transitabilidad', page_icon='🚜', layout='wide')
st.title('🌧️ Simulador hídrico del suelo y transitabilidad agrícola')
st.caption('Prototipo académico: balance horario de lluvia, infiltración, evaporación, transpiración y drenaje. La decisión de ingresar maquinaria exige comprobaciones en campo.')

with st.sidebar:
    st.header('1. Suelo')
    suelo=st.selectbox('Textura',list(SUELOS))
    base=SUELOS[suelo]
    ks=st.number_input('Conductividad Ks (mm/h)',0.01,500.0,float(base['ks']),step=0.5)
    psi=st.number_input('Succión del frente húmedo (mm)',1.0,1000.0,float(base['psi']))
    sat=st.number_input('Humedad a saturación (m³/m³)',0.10,0.79,float(base['sat']),0.01)
    fc=st.number_input('Capacidad de campo (m³/m³)',0.01,0.75,float(base['fc']),0.01)
    wp=st.number_input('Punto de marchitez (m³/m³)',0.01,0.70,float(base['wp']),0.01)
    theta0=st.number_input('Humedad inicial (m³/m³)',0.01,0.79,float(min(sat,max(wp,fc+.02))),0.01)
    prof1=st.number_input('Espesor capa superficial (mm)',50.0,1000.0,150.0,step=50.0)
    prof2=st.number_input('Espesor capa inferior (mm)',50.0,2000.0,350.0,step=50.0)
    dren=st.slider('Drenaje horario (fracción del exceso sobre CC)',0.0,0.20,0.025,0.005)
    charco=st.number_input('Máx. lámina superficial retenida (mm)',0.0,50.0,5.0)
    st.header('2. Evaporación y cultivo')
    cobertura=st.slider('Cobertura vegetal/fracción de ET0 atribuida a transpiración',0.,1.,.35,.05)
    et0=st.number_input('ET0 diaria constante si no se carga (mm/día)',0.,15.,4.,.5)
    st.header('3. Tránsito de maquinaria')
    maquina=st.selectbox('Maquinaria', ['Tractor','Sembradora','Cosechadora','Pulverizadora','Otra'])
    peso=st.number_input('Masa total de la máquina (kg) — dato descriptivo',100.,100000.,4000.,100.)
    pres=st.number_input('Presión de contacto estimada del neumático (kPa) — descriptiva',10.,1000.,130.,10.)
    nota_res=st.checkbox('Tengo medición de resistencia del suelo con penetrómetro')
    resistencia=st.number_input('Resistencia medida (MPa)',0.,10.,1.5,.1) if nota_res else None
    rmin=st.number_input('Mínimo de resistencia adoptado (MPa, calibrar)',0.1,10.,1.,.1)
    no_go=st.slider('Umbral no ingresar: humedad relativa CC-saturación (%)',0,100,85)
    caution=st.slider('Umbral favorable: humedad relativa CC-saturación (%)',0,no_go,65)

st.subheader('4. Precipitación y clima horario')
modo=st.radio('Fuente', ['Ejemplo incorporado','Subir CSV','Crear lluvia manual'],horizontal=True)
if modo=='Ejemplo incorporado':
    fechas=pd.date_range('2026-10-26 00:00',periods=168,freq='h')
    lluvia=np.zeros(len(fechas))
    lluvia[8:12]=[5,12,15,8]
    lluvia[85:88]=[3,6,3]
    datos=pd.DataFrame({'fecha':fechas,'precipitacion_mm':lluvia,'eto_mm':[et0/24]*len(fechas),'riego_mm':0.})
elif modo=='Crear lluvia manual':
    horas=st.number_input('Horizonte (horas)',24,720,168,24)
    hora_inicio=st.number_input('Hora inicial del evento (desde 0)',0,int(horas)-1,8)
    lluvia_evento=st.number_input('Precipitación del evento (mm)',0.,300.,40.)
    dur=st.number_input('Duración de lluvia (horas)',1,min(48,int(horas)),4)
    fechas=pd.date_range('2026-10-26 00:00',periods=int(horas),freq='h')
    lluvias=np.zeros(int(horas))
    end=min(int(horas),int(hora_inicio+dur))
    lluvias[int(hora_inicio):end]=lluvia_evento/(end-int(hora_inicio))
    datos=pd.DataFrame({'fecha':fechas,'precipitacion_mm':lluvias,'eto_mm':et0/24,'riego_mm':0.})
else:
    st.markdown('Formato: `fecha,precipitacion_mm,eto_mm,riego_mm`. Una fila por hora, sin saltos. `eto_mm` y `riego_mm` son opcionales; ET0 faltante usa el valor diario indicado dividido entre 24.')
    plantilla=pd.DataFrame({'fecha':pd.date_range('2026-10-26',periods=48,freq='h'),'precipitacion_mm':[5.,10.,3.]+[0.]*45,'eto_mm':[et0/24]*48,'riego_mm':[0.]*48})
    st.download_button('Descargar plantilla CSV',plantilla.to_csv(index=False).encode('utf-8-sig'),'plantilla_lluvia.csv','text/csv')
    uploaded=st.file_uploader('CSV horario',type=['csv'])
    if uploaded is None:
        st.info('Sube un CSV para iniciar el cálculo.'); st.stop()
    try:
        datos=pd.read_csv(uploaded,encoding='utf-8-sig',sep=None,engine='python')
        if 'fecha' not in datos or 'precipitacion_mm' not in datos:
            st.error('Faltan columnas fecha y/o precipitacion_mm.'); st.stop()
        datos['fecha']=pd.to_datetime(datos['fecha'],errors='raise')
        datos=datos.sort_values('fecha').reset_index(drop=True)
        if datos.fecha.duplicated().any() or (datos.fecha.diff().dropna()!=pd.Timedelta(hours=1)).any():
            st.error('Las fechas deben ser únicas y tener intervalos exactos de una hora.'); st.stop()
        if 'eto_mm' not in datos:
            datos['eto_mm']=et0/24
        if 'riego_mm' not in datos:
            datos['riego_mm']=0.
    except Exception as exc:
        st.error(f'No se pudo leer el CSV: {exc}'); st.stop()

with st.expander('Ver / editar serie de entrada',expanded=False):
    datos=st.data_editor(datos,num_rows='fixed',hide_index=True,use_container_width=True)
try:
    datos['fecha']=pd.to_datetime(datos['fecha'],errors='raise')
    if datos.fecha.duplicated().any() or (datos.fecha.diff().dropna()!=pd.Timedelta(hours=1)).any():
        raise ValueError('Las fechas deben ser horarias, continuas y sin duplicados.')
    cfg=Config(ks=ks,psi=psi,theta_sat=sat,theta_fc=fc,theta_wp=wp,theta0=theta0,
        capa_sup_mm=prof1,capa_inf_mm=prof2,cobertura=cobertura,drenaje_factor=dren,
        encharcamiento_max_mm=charco,inicio_ventana_pct=no_go,fin_ventana_pct=caution,
        resistencia_mpa=resistencia,resistencia_min_mpa=rmin)
    resultado,error=simular(datos,cfg)
except Exception as exc:
    st.error(f'Revisa los datos: {exc}'); st.stop()

st.subheader('5. Resultados')
cols=st.columns(6)
for col,label,key in zip(cols,['Lluvia','Infiltración','Escorrentía','Evaporación','Transpiración','Drenaje'],
       ['precipitacion_mm','infiltracion_mm','escorrentia_mm','evaporacion_mm','transpiracion_mm','drenaje_profundo_mm']):
    col.metric(label,f'{resultado[key].sum():.1f} mm')
st.caption(f'Error numérico de balance: {error:+.7f} mm (debe ser prácticamente 0). La infiltración es un flujo interno y NO se suma a las salidas totales del perfil.')
graf=resultado.set_index('fecha')
a,b=st.columns(2)
with a:
    st.markdown('**Lluvia, infiltración y escorrentía por hora (mm)**')
    st.line_chart(graf[['precipitacion_mm','infiltracion_mm','escorrentia_mm']])
    st.markdown('**Evaporación y transpiración (mm/h)**')
    st.line_chart(graf[['evaporacion_mm','transpiracion_mm']])
with b:
    st.markdown('**Humedad volumétrica por profundidad (m³/m³)**')
    st.line_chart(graf[['humedad_superficial','humedad_profunda']])
    st.markdown('**Humedad relativa entre capacidad de campo y saturación (%)**')
    st.line_chart(graf[['humedad_relativa_cc_saturacion_pct']])

st.subheader('6. Ventana de transitabilidad — evaluación preliminar')
st.warning('NO es un permiso de ingreso: los umbrales son configurables, NO certificados. Masa y presión del neumático se documentan, pero NO se usan para predecir capacidad portante. Para una decisión operativa son necesarias mediciones de humedad, resistencia, profundidad de huellas y condiciones de campo.')
actual=resultado.iloc[-1]
st.write(f'**Equipo:** {maquina} ({peso:,.0f} kg; presión declarada {pres:.0f} kPa). **Última hora simulada:** {actual.fecha}. **Estado:** {actual.estado}.')
mask=resultado.estado.eq('Humedad favorable (no habilita ingreso)')
ult_lluvia=resultado.index[(resultado.precipitacion_mm+resultado.riego_mm)>0]
ref=int(ult_lluvia[-1]) if len(ult_lluvia) else -1
candidatos=resultado.iloc[ref+1:] if ref+1<len(resultado) else resultado.iloc[0:0]
# Exigimos persistencia al menos 6 h y buscamos después de la última lluvia
hallada=None
for i in range(len(candidatos)-5):
    segmento=candidatos.iloc[i:i+6]
    if segmento.estado.eq('Humedad favorable (no habilita ingreso)').all():
        hallada=segmento.iloc[0].fecha
        break
if hallada is None:
    st.info('No se identificó una ventana preliminar favorable y sostenida de 6 horas después de la última lluvia dentro del horizonte simulado.')
else:
    desde=resultado.iloc[ref].fecha if ref>=0 else resultado.iloc[0].fecha
    st.success(f'Primera ventana preliminar con 6 h continuas de humedad favorable después de la última lluvia: {hallada} (~{(hallada-desde).total_seconds()/3600:.0f} h después de la última hora con lluvia). Requiere verificación de campo.')

st.dataframe(resultado,hide_index=True,use_container_width=True)
st.download_button('📥 Descargar resultados CSV',resultado.to_csv(index=False).encode('utf-8-sig'),'resultados_simulacion.csv','text/csv')
with st.expander('Alcance y limitaciones técnicas'):
    st.markdown('''- Green-Ampt se aproxima con subpasos horarios y un frente de humectación simplificado; no resuelve la ecuación de Richards ni el método Green-Ampt exacto de HEC-HMS.
- La ET0 es **dato de entrada**, no se calcula con Penman-Monteith. Si existe una serie horaria de ET0, cárgala. La partición entre evaporación y transpiración mediante cobertura es simplificada, NO es el coeficiente dual FAO-56.
- El drenaje es un depósito lineal por capas, no un modelo de flujo de suelo no saturado. No contempla ascenso capilar, redistribución detallada, napa freática ni pendientes.
- Ks, succión, saturación, capacidad de campo, marchitez, parámetros de drenaje y umbrales son valores de exploración; calibrar con ensayos y mediciones locales.
- El diagnóstico solo clasifica humedad superficial mediante umbrales definidos por el usuario y, si se incorpora, una resistencia de penetrómetro; no predice rutting, tracción o capacidad portante ni utiliza el peso/carga del tractor en sus cálculos.
- En suelos arcillosos la transitabilidad puede ser especialmente sensible a estructura, plasticidad y compactación; una 'ventana favorable' no sustituye inspección ni prueba de campo.
''')
