import streamlit as st
import pandas as pd
import os
import pypdf
from PIL import Image
from google import genai
from google.genai import types

# Configuración inicial de la app
st.set_page_config(page_title="Gotit - Asistente IA", page_icon="🤖", layout="wide")

USUARIO_CORRECTO = "admin"
CLAVE_CORRECTA = "123456"

GEMINI_API_KEY_DEFAULT = st.secrets.get("GEMINI_API_KEY", "")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# ----------------------------------------------------
# PANTALLA 1: LOGIN
# ----------------------------------------------------
if not st.session_state.autenticado:
    posibles_nombres = [
        "gotit logo.jpg", "gotit logo.png", "gotit logo.jpeg",
        "gotit_logo.jpg", "gotit_logo.png", "logo.jpg", "logo.png"
    ]
    
    imagen_cargada = None
    for nombre in posibles_nombres:
        if os.path.exists(nombre):
            try:
                imagen_cargada = Image.open(nombre)
                break
            except Exception:
                pass

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if imagen_cargada:
            st.image(imagen_cargada, width=180)
        
        st.title("Hola, soy Gotit")
        st.subheader("Asistente Virtual para Recursos Humanos")
        st.write("---")

        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión", type="primary", use_container_width=True):
            if usuario == USUARIO_CORRECTO and clave == CLAVE_CORRECTA:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

# ----------------------------------------------------
# PANTALLA 2: CONSULTAS POR BASE / HOJA DE DATOS
# ----------------------------------------------------
else:
    st.title("🤖 Asistente Virtual IA - Consultas de RH")

    with st.sidebar:
        st.header("Configuración")
        api_key = st.text_input("Gemini API Key:", value=GEMINI_API_KEY_DEFAULT, type="password")
        opcion_base = st.selectbox(
            "Seleccioná la base de datos o documento:", 
            ["Dota", "Registro", "Vacaciones", "Convenio", "CCT1.txt"]
        )
        
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

    # Carga dinámica de cualquier archivo u hoja seleccionada
    @st.cache_data
    def cargar_documento(nombre_base):
        archivos = os.listdir(".")
        target = nombre_base.lower().replace(".txt", "").strip()
        
        archivo_encontrado = None
        for f in archivos:
            if target in f.lower():
                archivo_encontrado = f
                break

        if not archivo_encontrado:
            return None, f"No se encontró el archivo relacionado con '{nombre_base}'."

        ext = os.path.splitext(archivo_encontrado)[1].lower()
        
        try:
            if ext in [".xlsx", ".xls"]:
                xls = pd.ExcelFile(archivo_encontrado)
                contenido_hojas = {}
                for h in xls.sheet_names:
                    df = pd.read_excel(xls, sheet_name=h)
                    df = df.dropna(how="all").fillna("")
                    contenido_hojas[h] = df
                return ("excel", contenido_hojas), archivo_encontrado

            elif ext == ".csv":
                df = pd.read_csv(archivo_encontrado)
                df = df.dropna(how="all").fillna("")
                return ("excel", {"Datos": df}), archivo_encontrado

            elif ext == ".pdf":
                reader = pypdf.PdfReader(archivo_encontrado)
                texto = "\n".join([p.extract_text() for p in reader.pages if p.extract_text()])
                return ("texto", texto), archivo_encontrado

            elif ext in [".txt", ".md"]:
                with open(archivo_encontrado, "r", encoding="utf-8", errors="ignore") as f:
                    texto = f.read()
                return ("texto", texto), archivo_encontrado

        except Exception as e:
            return None, f"Error cargando {archivo_encontrado}: {e}"

        return None, "Formato no soportado."

    doc_info, nombre_real_archivo = cargar_documento(opcion_base)

    if doc_info is not None:
        tipo, contenido = doc_info
        if tipo == "excel":
            filas_totales = sum(len(df) for df in contenido.values())
            st.success(f"Base activa: **{opcion_base}** (`{nombre_real_archivo}`) — {filas_totales} filas cargadas en {len(contenido)} hoja(s).")
        else:
            st.success(f"Documento activo: **{opcion_base}** (`{nombre_real_archivo}`) listo para consultas.")
    else:
        st.warning(f"⚠️ {nombre_real_archivo}")

    if "mensajes" not in st.session_state:
        st.session_state.mensajes = []

    for msg in st.session_state.mensajes:
        with st.chat_message(msg["rol"]):
            st.write(msg["contenido"])

    pregunta = st.chat_input(f"Preguntale algo a Gotit sobre {opcion_base}...")

    if pregunta:
        if not api_key:
            st.warning("⚠️ Configurá tu Gemini API Key en la barra lateral.")
        elif doc_info is None:
            st.error("⚠️ No se pudo leer la información de la base de datos.")
        else:
            st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
            with st.chat_message("user"):
                st.write(pregunta)

            tipo, contenido = doc_info
            contexto_str = ""

            if tipo == "excel":
                for hoja, df in contenido.items():
                    contexto_str += f"\n--- HOJA: {hoja} ---\n"
                    contexto_str += df.to_string(index=False) + "\n"
            else:
                contexto_str = contenido[:30000]

            prompt_completo = f"""
            Sos 'Gotit', el asistente inteligente de Recursos Humanos.
            Usá la información de la base/documento '{opcion_base}' ({nombre_real_archivo}) para responder:

            DATOS:
            {contexto_str}

            PREGUNTA DEL USUARIO:
            {pregunta}

            INSTRUCCIONES:
            - Respondé de forma precisa y profesional basándote en los datos.
            - Si hay múltiples hojas o filas, cruzá la información necesaria para responder correctamente.
            """

            with st.chat_message("assistant"):
                with st.spinner("Procesando consulta con la IA..."):
                    try:
                        # Inicializar el cliente oficial del SDK
                        client = genai.Client(api_key=api_key.strip())

                        # Probar modelos disponibles de la serie Gemini
                        modelos_a_probar = ["gemini-2.0-flash", "gemini-1.5-flash"]
                        respuesta_texto = None

                        for mod in modelos_a_probar:
                            try:
                                response = client.models.generate_content(
                                    model=mod,
                                    contents=prompt_completo,
                                )
                                respuesta_texto = response.text
                                if respuesta_texto:
                                    break
                            except Exception:
                                continue

                        if respuesta_texto:
                            st.write(respuesta_texto)
                            st.session_state.mensajes.append({"rol": "assistant", "contenido": respuesta_texto})
                        else:
                            st.error("No se pudo obtener respuesta del modelo. Verificá que la API Key sea válida.")

                    except Exception as ex:
                        st.error(f"Error durante la ejecución: {ex}")