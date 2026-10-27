# Simulador hídrico del suelo y transitabilidad — versión 2

Aplicación académica en Streamlit. Incluye balance horario de infiltración, evaporación, transpiración, drenaje, humedad de dos capas y **cribado exploratorio** de maquinaria.

## Ejecución

```bash
pip install -r requirements.txt
streamlit run app.py
```

En Streamlit Community Cloud usa **app.py** como archivo principal.

## Novedades v2

- Cálculo indicativo de carga por rueda del eje más cargado y área de contacto; **no** equivale a cálculo de capacidad portante.
- Indicador opcional de resistencia de penetrómetro comparada con presión de contacto. Su umbral es arbitrario hasta calibración local; nunca debe usarse como autorización automática.
- Se corrige la ventana de `N` horas: ahora se informa tanto cuándo comienza como cuándo **se completan** las N horas favorables después de la última lluvia.
- Gráfico de humedad frente a umbrales editables.

## Datos CSV

Una fila por hora, con columnas `fecha,precipitacion_mm,eto_mm,riego_mm`. La primera y segunda obligatorias. `eto_mm` es ET0 **introducida**, no calculada con FAO-56 Penman-Monteith. Valores de suelo son orientativos: requieren ajuste local.

## Limitaciones

Este prototipo no modela plenamente flujo no saturado, ni cambios de resistencia mecánica con la humedad, ni compactación real, ni huellas, ni resistencia al corte. Una medición única de penetrómetro no puede extrapolarse a futuras horas. **La clasificación favorable es SOLO hídrica**, no un permiso de ingreso. Requiere ensayos y validación de campo antes de utilizarse para operaciones.
