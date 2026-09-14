import streamlit as st
import pandas as pd
import os
import pypdf
from google import genai
from PIL import Image

# Configuración de página
st.set_page_config(page_title="Gotit - Asistente IA", page_icon="🤖", layout="wide")

# Credenciales de acceso a la app
USUARIO_CORRECTO = "admin"
CLAVE_CORRECTA = "123456"

# API Key tomada de Secrets de Streamlit o fallback vacio
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

# PANTALLA 2: CHAT CON GEMINI Y SOPORTE PARA EXCEL, PDF Y TXT (CONVENIO)
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
        # Mapear nombres o extensiones probables
        posibles = [
            nombre_base, 
            f"{nombre_base}.xlsx", f"{nombre_base}.xls", 
            f"{nombre_base}.csv", f"{nombre_base}.txt", f"{nombre_base}.pdf",
            f"{nombre_base.lower()}.txt", f"{nombre_base.upper()}.txt",
            f"{nombre_base.lower()}.pdf", f"{nombre_base.upper()}.pdf"
        ]
        
        # Si selecciona Convenio o CCT1, aseguramos buscar directamente CCT1.txt
        if nombre_base in ["Convenio", "CCT1"]:
            posibles.insert(0, "CCT1.txt")
            posibles.insert(1, "cct1.txt")

        for archivo in posibles:
            if os.path.exists(archivo):
                # Soporte para archivos de texto plano (.txt)
                if archivo.lower().endswith(".txt"):
                    try:
                        with open(archivo, "r", encoding="utf-8", errors="ignore") as f:
                            texto_txt = f.read()
                        return ("txt", texto_txt), archivo
                    except Exception as e:
                        return None, f"Error al leer archivo de texto '{archivo}': {e}"
                
                # Soporte para archivos PDF (.pdf)
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
                
                # Soporte para planillas Excel y CSV
                else:
                    try:
                        df = pd.read_excel(archivo)
                        return ("df", df), archivo
                    except Exception:
                        try:
                            df = pd.read_csv(archivo)
                            return ("df", df), archivo
                        except Exception as e:
                            return None, f"Error al leer planilla '{archivo}': {e}"

        return None, f"No se encontró el archivo '{nombre_base}'."

    doc_info, estado = cargar_documento(opcion_base)

    if doc_info is not None:
        tipo, contenido_doc = doc_info
        if tipo == "df":
            st.success(f"Base activa: **{opcion_base}** ({len(contenido_doc)} registros cargados)")
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
            st.warning("⚠️ Configurá una Gemini API Key válida en el menú lateral.")
        elif doc_info is None:
            st.error("⚠️ No se pudo cargar el archivo seleccionado.")
        else:
            st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
            with st.chat_message("user"):
                st.write(pregunta)

            tipo, contenido_doc = doc_info
            if tipo == "df":
                contexto_prompt = contenido_doc.to_csv(index=False)
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