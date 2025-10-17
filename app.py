import streamlit as st
import pandas as pd
from datetime import datetime
import sys
from pathlib import Path

# Agregar utils al path
sys.path.insert(0, str(Path(__file__).parent))

from utils.config_manager import ConfigManager, get_modelo_info
from utils.excel_reader import (
    leer_hoja_excel, extraer_datos_excel, 
    leer_hoja_calculos, obtener_hojas_disponibles,
    parse_int
)
# Asumiendo que pdf_generator.py tendrá la función generar_pdf_hsps refactorizada
from utils.pdf_generator import generar_pdf_hsps

# -----------------------
# Inicialización
# -----------------------
def init_session_state():
    """Inicializa variables de sesión"""
    defaults = {
        'uploaded': False,
        'config_manager': None,
        'modelo_seleccionado': None,
        'registros': None,
        'columnas_detectadas': None,
        'datos_calculos': None,
        'datos_comercio': None
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

@st.cache_resource
def cargar_config_manager():
    """Carga el gestor de configuraciones (cacheado)"""
    return ConfigManager("config/models.json")

# -----------------------
# UI Principal
# -----------------------
def main():
    st.set_page_config(
        page_title="HSPS Packing List Generator", 
        page_icon="📦", 
        layout="wide"
    )
    
    init_session_state()
    
    # Cargar configuración
    if st.session_state.config_manager is None:
        st.session_state.config_manager = cargar_config_manager()
    
    config_mgr = st.session_state.config_manager
    
    # Título
    st.title("📦 Generador Packing List HSPS")
    st.markdown("*Sistema multi-modelo con configuración JSON*")
    
    # Sidebar - Selección de modelo
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        modelos_disponibles = config_mgr.get_models()
        
        if not modelos_disponibles:
            st.error("❌ No hay modelos configurados en models.json")
            st.stop()
        
        modelo = st.selectbox(
            "Selecciona el modelo:",
            modelos_disponibles,
            format_func=lambda x: get_modelo_info(config_mgr, x)
        )
        
        st.session_state.modelo_seleccionado = modelo
        
        # Información del modelo
        model_cfg = config_mgr.get_model_config(modelo)
        if model_cfg:
            with st.expander("ℹ️ Info del modelo"):
                st.write(f"**Nombre:** {model_cfg.get('nombre_completo', modelo)}")
                if 'descripcion' in model_cfg:
                    st.write(f"**Descripción:** {model_cfg['descripcion']}")
                
                # Validar configuración
                es_valido, errores = config_mgr.validate_model(modelo)
                if es_valido:
                    st.success("✅ Configuración válida")
                else:
                    st.warning("⚠️ Configuración incompleta:")
                    for error in errores:
                        st.write(f"- {error}")
        
        st.divider()
        
        # Navegación
        paso = st.radio(
            "Navegación:", 
            ["1️⃣ Subir Excel", "2️⃣ Datos Comercio", "3️⃣ Generar PDF", "⚙️ Gestionar Modelos"]
        )
    
    # -----------------------
    # PASO 1: SUBIR EXCEL
    # -----------------------
    if paso == "1️⃣ Subir Excel":
        paso_1_subir_excel(config_mgr, modelo)
    
    # -----------------------
    # PASO 2: DATOS COMERCIO
    # -----------------------
    elif paso == "2️⃣ Datos Comercio":
        paso_2_datos_comercio(config_mgr, modelo)
    
    # -----------------------
    # PASO 3: GENERAR PDF
    # -----------------------
    elif paso == "3️⃣ Generar PDF":
        paso_3_generar_pdf(config_mgr, modelo)
    
    # -----------------------
    # GESTIONAR MODELOS
    # -----------------------
    elif paso == "⚙️ Gestionar Modelos":
        gestionar_modelos(config_mgr)

# -----------------------
# PASO 1: Subir Excel
# -----------------------
def paso_1_subir_excel(config_mgr: ConfigManager, modelo: str):
    st.header("Paso 1: Cargar Excel")
    
    excel_cfg = config_mgr.get_excel_config(modelo)
    if not excel_cfg:
        st.error(f"❌ No hay configuración de Excel para el modelo '{modelo}'")
        return
    
    st.info(f"📄 Sube el archivo Excel para el modelo: **{modelo}**")
    
    # Mostrar configuración esperada
    with st.expander("📋 Configuración esperada del Excel"):
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Hojas esperadas:**")
            st.write(f"- Datos: `{excel_cfg.get('hoja_datos', 'Auto')}`")
            st.write(f"- Cálculos: `{excel_cfg.get('hoja_calculos', 'Auto')}`")
        with col2:
            st.write("**Columnas a buscar:**")
            columnas = excel_cfg.get('columnas', {})
            for nombre, aliases in columnas.items():
                st.write(f"- {nombre}: {', '.join(aliases[:2])}...")
    
    archivo = st.file_uploader("Selecciona el archivo Excel", type=['xlsx', 'xls'])
    
    if archivo:
        try:
            # Obtener hojas disponibles
            hojas_disponibles = obtener_hojas_disponibles(archivo)
            st.success(f"✅ Excel cargado. Hojas disponibles: {', '.join(hojas_disponibles)}")
            
            # Selección de hoja de datos
            hoja_datos_default = excel_cfg.get('hoja_datos')
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 Hoja de Datos")
                
                if hoja_datos_default and hoja_datos_default in hojas_disponibles:
                    idx_default = hojas_disponibles.index(hoja_datos_default)
                else:
                    idx_default = 0
                
                hoja_datos = st.selectbox(
                    "Selecciona la hoja con los datos:",
                    hojas_disponibles,
                    index=idx_default
                )
            
            with col2:
                st.subheader("📐 Hoja de Cálculos")
                
                hoja_calculos_default = excel_cfg.get('hoja_calculos')
                opciones_calculos = ["Ninguna"] + hojas_disponibles
                
                if hoja_calculos_default and hoja_calculos_default in hojas_disponibles:
                    idx_calc = opciones_calculos.index(hoja_calculos_default)
                else:
                    idx_calc = 0
                
                hoja_calculos = st.selectbox(
                    "Selecciona la hoja de cálculos:",
                    opciones_calculos,
                    index=idx_calc
                )
            
            # Botón para procesar
            if st.button("🔄 Procesar Excel", type="primary", use_container_width=True):
                with st.spinner("Procesando Excel..."):
                    # Leer hoja de datos
                    df = leer_hoja_excel(
                        archivo,
                        hoja_datos,
                        buscar_en_filas=excel_cfg.get('buscar_header_en_filas', 5),
                        detener_en=excel_cfg.get('detener_en', ["TOTAL GENERAL"])
                    )
                    
                    st.success(f"✅ Hoja '{hoja_datos}' cargada: {len(df)} filas")
                    
                    # Extraer datos
                    columnas_config = excel_cfg.get('columnas', {})
                    registros, columnas_detectadas = extraer_datos_excel(df, columnas_config)
                    
                    st.subheader(f"📊 {len(registros)} registros detectados")
                    
                    # Mostrar columnas detectadas
                    with st.expander("🔍 Columnas detectadas"):
                        col1, col2, col3 = st.columns(3)
                        for i, (nombre, col_excel) in enumerate(columnas_detectadas.items()):
                            col_target = [col1, col2, col3][i % 3]
                            with col_target:
                                if col_excel:
                                    st.write(f"✅ **{nombre}:** `{col_excel}`")
                                else:
                                    st.write(f"❌ **{nombre}:** No detectado")
                    
                    # Vista previa de datos
                    with st.expander("👁️ Vista previa de registros"):
                        df_preview = pd.DataFrame(registros)
                        st.dataframe(df_preview, use_container_width=True)
                    
                    # Leer hoja de cálculos
                    datos_calculos = {}
                    if hoja_calculos != "Ninguna":
                        calculos_cfg = config_mgr.get_calculos_config(modelo)
                        if calculos_cfg:
                            datos_calculos = leer_hoja_calculos(archivo, hoja_calculos, calculos_cfg)
                            
                            if any(datos_calculos.values()):
                                st.success("✅ Datos de cálculos extraídos:")
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Peso Neto", datos_calculos.get('net_weight', '-'))
                                with col2:
                                    st.metric("Peso Bruto", datos_calculos.get('gross_weight', '-'))
                                with col3:
                                    st.metric("Dimensiones", datos_calculos.get('dimensions', '-'))
                    
                    # Guardar en sesión
                    st.session_state.registros = registros
                    st.session_state.columnas_detectadas = columnas_detectadas
                    st.session_state.datos_calculos = datos_calculos
                    st.session_state.uploaded = True
                    
                    st.success("✅ Datos procesados. Continúa al **Paso 2** →")
        
        except Exception as e:
            st.error(f"❌ Error procesando Excel: {e}")
            st.exception(e)

# -----------------------
# PASO 2: Datos Comercio
# -----------------------
def paso_2_datos_comercio(config_mgr: ConfigManager, modelo: str):
    if not st.session_state.get('uploaded'):
        st.warning("⚠️ Primero sube el Excel en el **Paso 1**")
        return
    
    st.header("Paso 2: Información de Comercio Exterior")
    
    pdf_cfg = config_mgr.get_pdf_config(modelo)
    if not pdf_cfg:
        st.error(f"❌ No hay configuración de PDF para el modelo '{modelo}'")
        return
    
    defaults = pdf_cfg.get('defaults', {})
    shipper = pdf_cfg.get('shipper', {})
    ship_to = pdf_cfg.get('ship_to', {})
    bill_to = pdf_cfg.get('bill_to', {})
    datos_calculos = st.session_state.get('datos_calculos', {})
    
    st.info("📋 Completa los datos adicionales (valores por defecto cargados desde configuración)")
    
    with st.form("comercio"):
        st.subheader("📦 Información de envío")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            shipping_date = st.date_input("Shipping date", value=datetime.now())
        with col2:
            seal_no = st.text_input("Seal No.", value=defaults.get('seal_no', 'N/A'))
        with col3:
            packing_slip_no = st.text_input("Packing Slip No.", value="")
        
        commercial_invoice = st.text_input("Commercial Invoice No.", value="")
        
        st.subheader("🏢 Destinatarios")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Ship to:**")
            ship_to_name = st.text_input("Company Name", value=ship_to.get('nombre', ''))
            ship_to_address = st.text_input("Address", value=ship_to.get('direccion', ''))
            ship_to_city = st.text_input("City/State/ZIP", value=ship_to.get('ciudad', ''))
            ship_to_tax = st.text_input("TAX ID", value=ship_to.get('tax_id', ''))
        
        with col2:
            st.markdown("**Bill to:**")
            bill_to_name = st.text_input("Company Name ", value=bill_to.get('nombre', ''))
            bill_to_address = st.text_input("Address ", value=bill_to.get('direccion', ''))
            bill_to_city = st.text_input("City ", value=bill_to.get('ciudad', ''))
            bill_to_state = st.text_input("State/ZIP ", value=bill_to.get('estado', ''))
        
        st.subheader("🚚 Detalles de envío")
        col1, col2 = st.columns(2)
        
        with col1:
            shipping_method = st.text_input("Shipping method", value=defaults.get('shipping_method', 'LTL'))
            incoterm = st.text_input("Incoterm", value=defaults.get('incoterm', 'FCA'))
            country_origin = st.text_input("Country of Origin", value=defaults.get('country_origin', 'México'))
            country_destination = st.text_input("Country of Destination", value=defaults.get('country_destination', 'Mexico'))
        
        with col2:
            # Auto-rellenar con datos de la hoja de cálculos
            dimensions = st.text_input(
                "Dimensions (cm)", 
                value=datos_calculos.get('dimensions', defaults.get('dimensions', '100 X 110 X 109'))
            )
            net_weight = st.text_input(
                "Net weight (Kg)", 
                value=datos_calculos.get('net_weight', '')
            )
            gross_weight = st.text_input(
                "Gross weight (Kg)", 
                value=datos_calculos.get('gross_weight', '')
            )
        
        st.subheader("🚛 Transporte")
        col1, col2 = st.columns(2)
        
        with col1:
            bl_awb = st.text_input("BL/AWB", value=defaults.get('bl_awb', '-'))
            linea = st.text_input("Línea", value=defaults.get('linea', 'FEDEX FREIGHT'))
            placa = st.text_input("No. De Placa", value="")
        
        with col2:
            sello_transporte = st.text_input("No. De Sello", value=defaults.get('sello_transporte', '-'))
            conductor = st.text_input("Nombre del Conductor", value="")
        
        submitted = st.form_submit_button("💾 Guardar Datos", use_container_width=True, type="primary")
        
        if submitted:
            st.session_state.datos_comercio = {
                'shipping_date': shipping_date.strftime('%d/%m/%Y'),
                'seal_no': seal_no,
                'packing_slip_no': packing_slip_no,
                'commercial_invoice': commercial_invoice,
                'ship_to_name': ship_to_name,
                'ship_to_address': ship_to_address,
                'ship_to_city': ship_to_city,
                'ship_to_tax': ship_to_tax,
                'bill_to_name': bill_to_name,
                'bill_to_address': bill_to_address,
                'bill_to_city': bill_to_city,
                'bill_to_state': bill_to_state,
                'shipping_method': shipping_method,
                'incoterm': incoterm,
                'country_origin': country_origin,
                'country_destination': country_destination,
                'dimensions': dimensions,
                'net_weight': net_weight,
                'gross_weight': gross_weight,
                'bl_awb': bl_awb,
                'placa': placa,
                'linea': linea,
                'sello_transporte': sello_transporte,
                'conductor': conductor,
                'fecha': shipping_date.strftime('%d/%m/%Y'),
                'descripcion_producto': pdf_cfg.get('descripcion_producto', ''),
                'shipper': shipper
            }
            st.success("✅ Datos guardados correctamente. Continúa al **Paso 3** →")
            st.balloons()

# -----------------------
# PASO 3: Generar PDF
# -----------------------
def paso_3_generar_pdf(config_mgr: ConfigManager, modelo: str):
    if not st.session_state.get('uploaded'):
        st.warning("⚠️ Primero sube el Excel en el **Paso 1**")
        return
    
    if 'datos_comercio' not in st.session_state:
        st.warning("⚠️ Primero completa los datos de Comercio Exterior en el **Paso 2**")
        return
    
    st.header("Paso 3: Generar PDF")
    
    registros = st.session_state.registros
    datos_comercio = st.session_state.datos_comercio
    
    # Calcular totales
    pallets_unicos = set()
    total_piezas = 0
    total_cajas = 0
    
    for reg in registros:
        if reg.get('numero_pallet'):
            pallets_unicos.add(reg['numero_pallet'])
        total_piezas += parse_int(reg.get('cantidad', 0))
        total_cajas += parse_int(reg.get('total_cajas', 0))
    
    # Métricas
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("📋 Registros", len(registros))
    with col2:
        st.metric("📦 Total Pallets", len(pallets_unicos))
    with col3:
        st.metric("🔢 Total Piezas", total_piezas)
    with col4:
        st.metric("📦 Total Cajas", total_cajas)
    
    # Vista previa
    with st.expander("👁️ Vista previa de registros"):
        df_preview = pd.DataFrame(registros)
        st.dataframe(df_preview, use_container_width=True)
    
    with st.expander("📋 Vista previa de datos comerciales"):
        st.json(datos_comercio)
    
    st.divider()
    
    # Nombre del archivo
    nombre_archivo = st.text_input(
        "Nombre del archivo PDF",
        value=f"PackingList_{modelo}_{datetime.now().strftime('%Y%m%d_%H%M')}",
        help="Sin extensión .pdf"
    )
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        generar_btn = st.button("🚀 Generar PDF", type="primary", use_container_width=True)
    
    if generar_btn:
        try:
            with st.spinner("Generando PDF en formato HSPS..."):
                # Generar PDF
                buffer = generar_pdf_hsps(registros, datos_comercio, config_mgr, modelo)
            
            st.success("✅ PDF generado exitosamente!")

            # Botón de descarga
            st.download_button(
                label="⬇️ Descargar Packing List PDF",
                data=buffer.getvalue(),
                file_name=f"{nombre_archivo}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary"
            )
            
        except Exception as e:
            st.error(f"❌ Error generando PDF: {e}")
            st.exception(e)

# -----------------------
# GESTIONAR MODELOS
# -----------------------
def gestionar_modelos(config_mgr: ConfigManager):
    st.header("⚙️ Gestión de Modelos")
    
    tab1, tab2, tab3 = st.tabs(["📋 Ver Modelos", "➕ Agregar Modelo", "📤 Import/Export"])
    
    with tab1:
        st.subheader("Modelos Configurados")
        
        modelos = config_mgr.get_models(activos_solo=False)
        
        for modelo in modelos:
            with st.expander(f"📦 {modelo}"):
                model_cfg = config_mgr.get_model_config(modelo)
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Nombre completo:** {model_cfg.get('nombre_completo', '-')}")
                    st.write(f"**Activo:** {'✅ Sí' if model_cfg.get('activo', True) else '❌ No'}")
                    
                    es_valido, errores = config_mgr.validate_model(modelo)
                    if es_valido:
                        st.success("✅ Configuración válida")
                    else:
                        st.warning("⚠️ Configuración incompleta")
                        for error in errores:
                            st.write(f"- {error}")
                
                with col2:
                    if st.button(f"🗑️ Eliminar", key=f"del_{modelo}"):
                        if config_mgr.delete_model(modelo):
                            st.success(f"✅ Modelo '{modelo}' eliminado")
                            st.rerun()
                        else:
                            st.error("❌ Error eliminando modelo")
                
                # Mostrar JSON
                with st.expander("Ver JSON completo"):
                    st.json(model_cfg)
    
    with tab2:
        st.subheader("Agregar Nuevo Modelo")
        st.info("🚧 Funcionalidad en desarrollo. Por ahora edita config/models.json manualmente.")
    
    with tab3:
        st.subheader("Importar/Exportar Configuraciones")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Exportar Modelo**")
            modelo_export = st.selectbox("Selecciona modelo:", config_mgr.get_models(), key="export")
            
            if st.button("📤 Exportar", key="btn_export"):
                filename = f"config_{modelo_export}.json"
                if config_mgr.export_model(modelo_export, filename):
                    st.success(f"✅ Exportado a {filename}")
        
        with col2:
            st.markdown("**Importar Modelo**")
            uploaded = st.file_uploader("Subir archivo JSON", type=['json'], key="import")
            
            if uploaded and st.button("📥 Importar", key="btn_import"):
                if config_mgr.import_model(uploaded):
                    st.success("✅ Modelo importado correctamente")
                    st.rerun()
                else:
                    st.error("❌ Error importando modelo")

# -----------------------
# EJECUTAR
# -----------------------
if __name__ == "__main__":
    main()