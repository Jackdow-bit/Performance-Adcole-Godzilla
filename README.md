# Reporte NoK Engicom — Streamlit

## Ejecutar localmente
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run Reporte_NoK_Engicom.py
```
Sube estos archivos a GitHub y selecciona `Reporte_NoK_Engicom.py` como Main file path en Streamlit Community Cloud.

Incluye carga PDF/ZIP, extracción por pieza, deduplicación SHA-256, Apoyos, Levas, Chatter Levas con Base Circle/Lift Area por separado, Chatter apoyos, Pareto, boxplots, histogramas, valores individuales, Pp/Ppk, Excel y PDF con nombre de fecha/hora.

**Validación:** los límites de especificación se trasladaron del archivo fuente proporcionado; deben confirmarse contra la especificación controlada de Engicom antes de decisiones de liberación. Pp/Ppk usan desviación estándar global muestral y no demuestran estabilidad. LightGBM no se incluye por defecto porque estos PDF no contienen por sí mismos una variable objetivo etiquetada y validada para entrenar un modelo predictivo fiable. Para lotes de 1,500 PDF grandes, la carga en Streamlit Cloud puede superar la memoria disponible; ejecutar localmente o usar una arquitectura de procesamiento en disco/base de datos.
