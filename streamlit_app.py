import streamlit as st
import pandas as pd
import os
import pypdf
import requests
from PIL import Image

# 1. Configuración de página
st.set_page_config(page_title="Gotit - Asistente IA", page_icon="🤖", layout="wide")

USUARIO_CORRECTO = "admin"
CLAVE_CORRECTA = "123456"

GEMINI_API_KEY_DEFAULT = st.secrets.get("GEMINI_API_KEY", "")

if "autenticado" not in st.session_state:
    st.session_state.autenticado = False

# 2. PANTALLA DE LOGIN
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
        st.subheader("Asistente Virtual de Recursos Humanos")
        st.write("---")

        usuario = st.text_input("Usuario")
        clave = st.text_input("Contraseña", type="password")
        
        if st.button("Iniciar Sesión", type="primary", use_container_width=True):
            if usuario == USUARIO_CORRECTO and clave == CLAVE_CORRECTA:
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")

# 3. PANTALLA PRINCIPAL (CHAT CON DATOS)
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

    # Función unificada de lectura de archivos y todas sus hojas
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
            return None, f"No se encontró el archivo '{nombre_base}' en el directorio."

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
            return None, f"Error leyendo {archivo_encontrado}: {e}"

        return None, "Formato no compatible."

    doc_info, nombre_real_archivo = cargar_documento(opcion_base)

    if doc_info is not None:
        tipo, contenido = doc_info
        if tipo == "excel":
            filas_totales = sum(len(df) for df in contenido.values())
            st.success(f"Base activa: **{opcion_base}** (`{nombre_real_archivo}`) — {filas_totales} filas cargadas en {len(contenido)} hoja(s).")
        else:
            st.success(f"Documento activo: **{opcion_base}** (`{nombre_real_archivo}`) cargado.")
    else:
        st.warning(f"⚠️ {nombre_real_archivo}")

    if "mensajes" not in st.session_state:
        st.session_state.mensajes = []

    for msg in st.session_state.mensajes:
        with st.chat_message(msg["rol"]):
            st.write(msg["contenido"])

    pregunta = st.chat_input(f"Consulta sobre {opcion_base}...")

    if pregunta:
        if not api_key:
            st.warning("⚠️ Configurá la API Key de Gemini en el menú lateral.")
        elif doc_info is None:
            st.error("⚠️ No se pudo cargar la información del archivo.")
        else:
            st.session_state.mensajes.append({"rol": "user", "contenido": pregunta})
            with st.chat_message("user"):
                st.write(pregunta)

            tipo, contenido = doc_info
            contexto_str = ""

            if tipo == "excel":
                for hoja, df in contenido.items():
                    contexto_str += f"\n--- HOJA: {hoja} ---\n"
                    contexto_str += df.head(250).to_string(index=False) + "\n"
            else:
                contexto_str = contenido[:20000]

            prompt_completo = f"""
            Sos 'Gotit', asistente virtual de Recursos Humanos. 
            Basándote en los datos del documento '{opcion_base}' ({nombre_real_archivo}):

            {contexto_str}

            PREGUNTA DEL USUARIO: {pregunta}

            Respondé con precisión y claridad profesional en base a la información provista.
            """

            with st.chat_message("assistant"):
                with st.spinner("Procesando consulta..."):
                    try:
                        key_clean = api_key.strip()
                        
                        # Endpoints HTTP estándar para máxima compatibilidad
                        endpoints = [
                            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key_clean}",
                            f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={key_clean}"
                        ]

                        payload = {
                            "contents": [{"parts": [{"text": prompt_completo}]}]
                        }

                        headers = {
                            "Content-Type": "application/json",
                            "x-goog-api-key": key_clean
                        }

                        respuesta_final = None
                        error_detalle = ""

                        for url in endpoints:
                            res = requests.post(url, json=payload, headers=headers, timeout=45)
                            if res.status_code == 200:
                                res_json = res.json()
                                respuesta_final = res_json["candidates"][0]["content"]["parts"][0]["text"]
                                break
                            else:
                                error_detalle += f"[{res.status_code}] {res.text} "

                        if respuesta_final:
                            st.write(respuesta_final)
                            st.session_state.mensajes.append({"rol": "assistant", "contenido": respuesta_final})
                        else:
                            st.error(f"Error de comunicación con la API: {error_detalle}")

                    except Exception as ex:
                        st.error(f"Error en la ejecución: {ex}")