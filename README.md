# Simulador hídrico del suelo y transitabilidad (prototipo)

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Ejecución online

1. Crea un repositorio en GitHub con `app.py`, `modelo.py` y `requirements.txt`.
2. Ingresa a https://share.streamlit.io/ (Streamlit Community Cloud) y conecta el repositorio.
3. Selecciona `app.py` como archivo principal y despliega la app.

Como alternativa para ejecutar el prototipo en Google Colab se pueden instalar dependencias, pero para la interfaz accesible vía web resulta más directo Streamlit Community Cloud.

## Datos

CSV horario con `fecha,precipitacion_mm,eto_mm,riego_mm`. `fecha` debe ser una marca temporal horaria continua. La precipitación y ET0 son cantidades acumuladas durante esa hora, no intensidad instantánea. `eto_mm` y `riego_mm` son opcionales.

## Límites importantes

Es un modelo conceptual con Green-Ampt explícito, depósitos de humedad, ET0 como entrada y reglas de transitabilidad definidas por el usuario. No es FAO-56 dual, Richards ni una validación de tránsito. Cualquier decisión de ingreso requiere medidas de campo y evaluación de la capacidad portante y las cargas por rueda.

Fuentes para documentar metodología:
- https://www.hec.usace.army.mil/confluence/hmsdocs/hmstrm/canopy-surface-infiltration-and-runoff-volume/infiltration/green-and-ampt-loss-model
- https://www.fao.org/4/x0490e/x0490e00.htm
