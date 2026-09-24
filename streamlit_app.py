import streamlit as st
import pandas as pd
import os
import pypdf
from google import genai
from google.genai import types
from PIL import Image

# Configuración de página
st.set_page_config(page_title="Gotit - Asistente IA", page_icon="🤖", layout="wide")

# Credenciales de acceso a la app
USUARIO_CORRECTO = "admin"
CLAVE_CORRECTA = "123456"

# Toma la API Key desde Secrets de Streamlit Cloud
GEMINI_API_KEY_DEFAULT = st.secrets.get("GEMINI_API_KEY", "")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# PANTALLA 1: LOGIN
if not st.session_state.autenticado:
    posibles_nombres = [
        "gotit logo.jpg", "gotit logo.png", "gotit logo.jpeg",
        "gotit logo.JPG", "gotit logo.PNG", "gotit logo.JPEG",
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
        else:
            st.info("ℹ️ Guardá la imagen en la carpeta del proyecto como 'gotit logo.jpg'")

        st.title("Hola soy Gotit, el asistente virtual de Aysa !")
        st.subheader("Logueate para empezar a usarme.")
        st.write("---")

        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión", type="primary", use_container_width=True):
            if usuario == USUARIO_CORRECTO and clave == CLAVE_CORRECTA:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

# PANTALLA 2: CHAT CON GEMINI Y SOPORTE PARA EXCEL, PDF Y TXT
else:
    st.title("🤖 Asistente Virtual IA para Recursos Humanos")

    with st.sidebar:
        st.header("Configuración")
        api_key = st.text_input("Gemini API Key:", value=GEMINI_API_KEY_DEFAULT, type="password")
        opcion_base = st.selectbox("Seleccioná la base de datos:", ["Dota", "Registro", "Vacaciones", "Convenio", "CCT1.txt"])
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

    @st.cache_data
    def cargar_documento(nombre_base):
        posibles = [
            nombre_base, 
            f"{nombre_base}.xlsx", f"{nombre_base}.xls", 
            f"{nombre_base}.csv", f"{nombre_base}.txt", f"{nombre_base}.pdf",
            f"{nombre_base.lower()}.xlsx", f"{nombre_base.lower()}.xls",
            f"{nombre_base.lower()}.csv", f"{nombre_base.lower()}.txt", f"{nombre_base.lower()}.pdf"
        ]
        
        if nombre_base in ["Convenio", "CCT1", "CCT1.txt"]:
            posibles.insert(0, "CCT1.txt")
            posibles.insert(1, "cct1.txt")

        for archivo in posibles:
            if os.path.exists(archivo):
                # 1. Archivos TXT
                if archivo.lower().endswith(".txt"):
                    try:
                        with open(archivo, "r", encoding="utf-8", errors="ignore") as f:
                            texto_txt = f.read()
                        return ("txt", texto_txt), archivo
                    except Exception as e:
                        return None, f"Error al leer TXT '{archivo}': {e}"
                
                # 2. Archivos PDF
                elif archivo.lower().endswith(".pdf"):
                    try:
                        reader = pypdf.PdfReader(archivo)
                        texto_pdf = ""
                        for page in reader.pages:
                            t = page.extract_text()
                            if t:
                                texto_pdf += t + "\n"
                        return ("pdf", texto_pdf), archivo
                    except Exception as e:
                        return None, f"Error al leer PDF '{archivo}': {e}"
                
                # 3. Planillas Excel y CSV
                else:
                    try:
                        if archivo.lower().endswith((".xlsx", ".xls")):
                            df = pd.read_excel(archivo)
                        else:
                            df = pd.read_csv(archivo)
                        
                        df = df.dropna(how="all").fillna("")
                        return ("df", df), archivo
                    except Exception as e:
                        return None, f"Error al leer planilla '{archivo}': {e}"

        return None, f"No se encontró el archivo '{nombre_base}'."

    doc_info, estado = cargar_documento(opcion_base)

    if doc_info is not None:
        tipo, contenido_doc = doc_info
        if tipo == "df":
            st.success(f"Base activa: **{opcion_base}** ({len(contenido_doc)} registros cargados desde `{estado}`)")
        elif tipo == "txt":
            st.success(f"Documento de Texto activo: **{opcion_base}** (Cargado desde `{estado}`)")
        else:
            st.success(f"Documento PDF activo: **{opcion_base}** (Texto cargado correctamente)")
    else:
        st.warning(f"⚠️ {estado}")

    if "mensajes" not in st.session_state:
        st.session_state.mensajes = []

    for msg in st.session_state.mensajes:
        with st.chat_message(msg["rol"]):
            st.write(msg["contenido"])

    pregunta = st.chat_input(f"Preguntale algo a la IA sobre {opcion_base}...")

    if pregunta:
        if not api_key:
            st.warning("⚠️ Configurá tu Gemini API Key en el menú lateral.")
        elif doc_info is None:
            st.error("⚠️ No se pudo cargar el archivo seleccionado.")
        else:
            st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
            with st.chat_message("user"):
                st.write(pregunta)

            tipo, contenido_doc = doc_info
            if tipo == "df":
                contexto_prompt = contenido_doc.to_string(index=False)
            else:
                contexto_prompt = contenido_doc

            prompt = f"""
            Sos un asistente virtual de Recursos Humanos de AySA. 
            Analizá detenidamente la información provista en la base/documento '{opcion_base}':

            {contexto_prompt}

            Pregunta del usuario: {pregunta}
            Respondé con precisión, amabilidad y basándote únicamente en la información contenida en el documento provisto.
            """

            with st.chat_message("assistant"):
                with st.spinner("La IA está analizando los datos..."):
                    try:
                        clean_key = api_key.strip()
                        
                        client = genai.Client(
                            api_key=clean_key,
                            http_options=types.HttpOptions(
                                headers={"x-goog-api-key": clean_key}
                            )
                        )
                        
                        # Modelos 100% compatibles con la v1beta de la API
                        modelos_a_probar = [
                            'models/gemini-2.5-flash',
                            'models/gemini-2.0-flash',
                            'models/gemini-1.5-flash'
                        ]
                        
                        response = None
                        ultimo_error = None

                        for modelo in modelos_a_probar:
                            try:
                                response = client.models.generate_content(
                                    model=modelo,
                                    contents=prompt,
                                )
                                if response and response.text:
                                    break
                            except Exception as err:
                                ultimo_error = err

                        if response and response.text:
                            st.write(response.text)
                            st.session_state.mensajes.append({"rol": "assistant", "contenido": response.text})
                        else:
                            st.error(f"Error al conectar con la API de Gemini: {ultimo_error}")

                    except Exception as e:
                        st.error(f"Error de conexión: {e}")