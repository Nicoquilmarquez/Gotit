import streamlit as st
import pandas as pd
import os
from google import genai
from PIL import Image

# Configuración de página
st.set_page_config(page_title="Gotit - Asistente IA", page_icon="🤖", layout="wide")

# Credenciales de acceso a la app
USUARIO_CORRECTO = "admin"
CLAVE_CORRECTA = "123456"

# API Key Fija precargada
GEMINI_API_KEY_DEFAULT =st.secrets.get("GEMINI_API_KEY", "")

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

# PANTALLA 2: CHAT CON GEMINI
else:
    st.title("🤖 Asistente Virtual IA para Recursos Humanos")

    with st.sidebar:
        st.header("Configuración")
        api_key = st.text_input("Gemini API Key:", value=GEMINI_API_KEY_DEFAULT, type="password")
        opcion_base = st.selectbox("Seleccioná la base de datos:", ["Dota", "Registro", "Vacaciones"])
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

    @st.cache_data
    def cargar_excel(nombre_base):
        posibles = [nombre_base, f"{nombre_base}.xlsx", f"{nombre_base}.xls"]
        for archivo in posibles:
            if os.path.exists(archivo):
                try:
                    df = pd.read_excel(archivo)
                    return df, archivo
                except Exception:
                    try:
                        df = pd.read_csv(archivo)
                        return df, archivo
                    except Exception as e:
                        return None, f"Error al leer {archivo}: {e}"
        return None, f"No se encontró el archivo '{nombre_base}'."

    df, estado = cargar_excel(opcion_base)

    if df is not None:
        st.success(f"Base activa: **{opcion_base}** ({len(df)} registros cargados)")
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
            st.warning("⚠️ Configurá una Gemini API Key válida en el menú lateral.")
        elif df is None:
            st.error("⚠️ No hay base de datos cargada.")
        else:
            st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
            with st.chat_message("user"):
                st.write(pregunta)

            resumen_csv = df.to_csv(index=False)

            prompt = f"""
            Sos un asistente virtual de Recursos Humanos. Analizá detenidamente los datos de la base '{opcion_base}':

            {resumen_csv}

            Pregunta del usuario: {pregunta}
            Respondé con precisión, amabilidad y basándote únicamente en la información contenida en los datos provistos.
            """

            with st.chat_message("assistant"):
                with st.spinner("La IA está analizando los datos..."):
                    try:
                        client = genai.Client(api_key=api_key)
                        
                        candidatos = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.0-flash']
                        response = None
                        error_log = []

                        for mod in candidatos:
                            try:
                                response = client.models.generate_content(
                                    model=mod,
                                    contents=prompt,
                                )
                                break
                            except Exception as err:
                                error_log.append(f"{mod}: {err}")

                        if not response:
                            modelos_lista = [m.name for m in client.models.list()]
                            for mod in modelos_lista:
                                try:
                                    response = client.models.generate_content(
                                        model=mod,
                                        contents=prompt,
                                    )
                                    break
                                except Exception:
                                    continue

                        if response:
                            st.write(response.text)
                            st.session_state.mensajes.append({"rol": "assistant", "contenido": response.text})
                        else:
                            st.error("No se pudo conectar a ningún modelo de tu API Key.")

                    except Exception as e:
                        st.error(f"Error al conectar con Gemini: {e}")