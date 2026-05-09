# app/assets/

Recursos visuales estáticos de la app Streamlit.

Esta carpeta contiene activos no versionados como código Python:

- **`caece_logo.png`** — Logo institucional de la Universidad CAECE, usado
  en el header de la app (`render_header` en `app/streamlit_app.py`). Si
  el archivo se elimina o se mueve, el header sigue funcionando con solo
  el bloque de texto: el helper `_cargar_logo_caece()` maneja la ausencia
  graciosamente.

Si en el futuro se suman más recursos (logos secundarios, imágenes para
las pestañas, etc.) van acá. La carpeta se versiona porque los recursos
forman parte del deploy en Streamlit Cloud.
