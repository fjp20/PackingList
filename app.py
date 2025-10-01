import re
import io
import math
from datetime import datetime

import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# -----------------------
# Utilidades
# -----------------------
def normalize_header(h):
    if pd.isna(h):
        return ''
    s = str(h).strip().lower()
    s = s.replace('ñ', 'n')
    s = re.sub(r'[áàäâ]', 'a', s)
    s = re.sub(r'[éèëê]', 'e', s)
    s = re.sub(r'[íìïî]', 'i', s)
    s = re.sub(r'[óòöô]', 'o', s)
    s = re.sub(r'[úùüû]', 'u', s)
    s = re.sub(r'[^a-z0-9]+', '_', s)
    s = re.sub(r'^_|_$', '', s)
    return s

def parse_int(value, default=0):
    try:
        if pd.isna(value):
            return default
        if isinstance(value, (int, float)):
            return int(value)
        s = str(value).strip().replace(',', '').replace(' ', '')
        if s == '':
            return default
        return int(float(s))
    except:
        return default

# Aliases de columnas para detectar en la hoja ZF
COLUMN_ALIASES = {
    'numero_pallet': ['numero de pallet', 'numero_de_pallet', 'pallet', 'num pallet', 'no pallet'],
    'n_lote': ['n. de lote', 'n de lote', 'lote', 'no lote', 'n lote'],
    'fecha': ['fecha', 'date', 'manufacturing date'],
    'modelo': ['modelo', 'model'],
    'n_parte': ['n. parte', 'n parte', 'parte', 'part'],
    'cantidad': ['cantidad', 'quantity', 'qty', 'piezas'],
    'total_cajas': ['total de cajas', 'total cajas', 'cajas', 'boxes']
}

def find_column(df, aliases):
    """Busca una columna en el DataFrame usando lista de aliases"""
    cols_lower = {col: str(col).lower().strip() for col in df.columns}
    
    for col, col_lower in cols_lower.items():
        for alias in aliases:
            if alias.lower() in col_lower or col_lower in alias.lower():
                return col
    return None

def leer_hoja_zf(archivo):
    """Lee específicamente la hoja ZF del Excel"""
    try:
        # Intentar leer la hoja ZF
        df = pd.read_excel(archivo, sheet_name='ZF', header=None)
    except:
        # Si no existe hoja ZF, leer primera hoja
        df = pd.read_excel(archivo, header=None)
    
    # Buscar fila de encabezados (normalmente en las primeras 5 filas)
    header_row = 0
    for idx in range(min(5, len(df))):
        row_str = ' '.join([str(x).lower() for x in df.iloc[idx] if not pd.isna(x)])
        if any(word in row_str for word in ['pallet', 'lote', 'fecha', 'cantidad', 'cajas']):
            header_row = idx
            break
    
    # Obtener encabezados y limpiar duplicados/vacíos
    headers = df.iloc[header_row].tolist()
    clean_headers = []
    seen_headers = {}
    
    for i, h in enumerate(headers):
        if pd.isna(h) or str(h).strip() == '':
            # Columna vacía - asignar nombre genérico
            clean_headers.append(f'col_vacia_{i}')
        else:
            h_str = str(h).strip()
            # Si el header ya existe, agregar sufijo
            if h_str in seen_headers:
                seen_headers[h_str] += 1
                clean_headers.append(f"{h_str}_{seen_headers[h_str]}")
            else:
                seen_headers[h_str] = 0
                clean_headers.append(h_str)
    
    # Establecer encabezados únicos
    df.columns = clean_headers
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    
    # Limpiar filas vacías y filas que contengan "TOTAL GENERAL"
    df = df.dropna(how='all')
    
    # Eliminar filas después de TOTAL GENERAL
    for idx, row in df.iterrows():
        row_str = ' '.join([str(x).lower() for x in row if not pd.isna(x)])
        if 'total general' in row_str:
            df = df.iloc[:idx]
            break
    
    return df

def extraer_datos_excel(df):
    """Extrae los datos del Excel identificando las columnas correctas"""
    
    # Encontrar columnas por aliases
    col_pallet = find_column(df, COLUMN_ALIASES['numero_pallet'])
    col_lote = find_column(df, COLUMN_ALIASES['n_lote'])
    col_fecha = find_column(df, COLUMN_ALIASES['fecha'])
    col_modelo = find_column(df, COLUMN_ALIASES['modelo'])
    col_parte = find_column(df, COLUMN_ALIASES['n_parte'])
    col_cantidad = find_column(df, COLUMN_ALIASES['cantidad'])
    col_cajas = find_column(df, COLUMN_ALIASES['total_cajas'])
    
    # Crear lista de registros EXACTAMENTE como están en el Excel
    registros = []
    
    for idx, row in df.iterrows():
        # Verificar que la fila no esté vacía
        if pd.isna(row.get(col_pallet)) and pd.isna(row.get(col_cantidad)):
            continue
        
        registro = {
            'pallet': row.get(col_pallet, ''),
            'cantidad': row.get(col_cantidad, ''),
            'cajas': row.get(col_cajas, ''),
            'n_parte': row.get(col_parte, ''),
            'lote': row.get(col_lote, ''),
            'fecha': row.get(col_fecha, '')
        }
        
        # Convertir valores a string manteniendo formato original
        for key in registro:
            val = registro[key]
            if pd.isna(val) or val == '':
                registro[key] = ''
            else:
                # Mantener el valor exacto como string
                registro[key] = str(val).strip()
        
        registros.append(registro)
    
    return registros, {
        'col_pallet': col_pallet,
        'col_lote': col_lote,
        'col_fecha': col_fecha,
        'col_modelo': col_modelo,
        'col_parte': col_parte,
        'col_cantidad': col_cantidad,
        'col_cajas': col_cajas
    }

def generar_pdf_hsps(registros, datos_comercio):
    """Genera el PDF en formato HSPS con los datos EXACTOS del Excel"""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    styles = getSampleStyleSheet()

    # Estilos personalizados
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, 
                                  textColor=colors.HexColor('#000080'), alignment=TA_CENTER, 
                                  spaceAfter=6, fontName='Helvetica-Bold')
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=8, fontName='Helvetica')

    # ENCABEZADO
    encabezado_data = [
        [Paragraph("<b>PACKING SLIP</b>", title_style)],
        [Paragraph("<b>HS POWER SPRING MÉXICO SA DE CV</b>", header_style)],
        [Paragraph("Circuito Cerezos Sur No. 106, Parque Industrial San Francisco,", normal_style)],
        [Paragraph("San Francisco de los Romo, Aguascalientes, México. C.P.20355", normal_style)]
    ]
    tabla_encabezado = Table(encabezado_data, colWidths=[7*inch])
    tabla_encabezado.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elementos.append(tabla_encabezado)
    elementos.append(Spacer(1, 10))

    # INFORMACIÓN DE ENVÍO
    shipping_data = [
        ["Shipping date", "Seal No.", "PACKING LIST NO."],
        [datos_comercio.get('shipping_date', ''), 
         datos_comercio.get('seal_no', 'N/A'), 
         datos_comercio.get('packing_slip_no', '')]
    ]
    tabla_shipping = Table(shipping_data, colWidths=[1.8*inch, 1.8*inch, 2*inch])
    tabla_shipping.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E0E0E0')),
    ]))
    elementos.append(tabla_shipping)
    elementos.append(Spacer(1, 8))

    # TRES COLUMNAS
    shipper_text = f"""<b>Shipper / Exporter:</b><br/>
HS POWER SPRING MÉXICO SA DE CV<br/>
Circuito Cerezos Sur No. 106,<br/>
Parque Industrial San Francisco,<br/>
San Francisco de los Romo,<br/>
Aguascalientes, México. C.P.20355"""

    shipto_text = f"""<b>Ship to:</b><br/>
{datos_comercio.get('ship_to_name', 'ZF PASSIVE SAFETY US INC.')}<br/>
{datos_comercio.get('ship_to_address', '9600 International Boulevard, Docks 5-8,')}<br/>
{datos_comercio.get('ship_to_city', 'Pharr, Tx, USA, C.P 78577')}<br/>
TAX ID: {datos_comercio.get('ship_to_tax', '341758354')}"""

    billto_text = f"""<b>Bill to:</b><br/>
{datos_comercio.get('bill_to_name', 'TRW VEHICLE SAFETY SYSTEMS')}<br/>
{datos_comercio.get('bill_to_address', 'Blvd Mike Allen 1370 S/N,')}<br/>
{datos_comercio.get('bill_to_city', 'Parque Industrial Reynosa,')}<br/>
{datos_comercio.get('bill_to_state', 'Reynosa, Tamaulipas, Mex. C.P 88788')}"""

    tres_columnas = [[Paragraph(shipper_text, normal_style), 
                      Paragraph(shipto_text, normal_style), 
                      Paragraph(billto_text, normal_style)]]
    tabla_tres = Table(tres_columnas, colWidths=[2.5*inch, 2.5*inch, 2.5*inch])
    tabla_tres.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elementos.append(tabla_tres)
    elementos.append(Spacer(1, 10))

    # INFORMACIÓN ADICIONAL
    info_adicional = [
        ["Shipping method", "Incoterm:", "Commercial Invoice No.", "Country of Origin", "Country of Destination"],
        [datos_comercio.get('shipping_method', 'LTL'), 
         datos_comercio.get('incoterm', 'FCA'),
         datos_comercio.get('commercial_invoice', ''),
         datos_comercio.get('country_origin', 'México'),
         datos_comercio.get('country_destination', 'Mexico')]
    ]
    tabla_info = Table(info_adicional, colWidths=[1.4*inch, 1.4*inch, 1.4*inch, 1.4*inch, 1.4*inch])
    tabla_info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E0E0E0')),
    ]))
    elementos.append(tabla_info)
    elementos.append(Spacer(1, 10))

    # TABLA DE PRODUCTOS - DATOS EXACTOS DEL EXCEL
    headers = ["Pallets No.", "Quantity", "Boxes", "Product No.", "Description", "Lot", "Manufacturing date"]
    table_data = [headers]

    total_quantity = 0
    total_boxes = 0
    ultimo_pallet = ""

    # Agregar cada registro EXACTAMENTE como viene del Excel
    for reg in registros:
        # Para agrupar visualmente por pallet (mostrar número solo en primera aparición)
        pallet_display = reg['pallet'] if reg['pallet'] != ultimo_pallet else ''
        ultimo_pallet = reg['pallet']
        
        fila = [
            pallet_display,              # Pallet No. (del Excel)
            reg['cantidad'],              # Quantity (del Excel)
            reg['cajas'],                 # Boxes (del Excel)
            reg['n_parte'],               # Product No. (del Excel)
            "SEATBELT RETURN SPRING UNIT",  # Description (fija)
            reg['lote'],                  # Lot (del Excel)
            reg['fecha']                  # Manufacturing date (del Excel)
        ]
        table_data.append(fila)
        
        # Sumar totales
        try:
            total_quantity += parse_int(reg['cantidad'])
        except:
            pass
        try:
            total_boxes += parse_int(reg['cajas'])
        except:
            pass

    # Crear tabla
    col_widths = [0.8*inch, 0.9*inch, 0.7*inch, 1.2*inch, 2.3*inch, 0.8*inch, 1.3*inch]
    tabla_productos = Table(table_data, colWidths=col_widths, repeatRows=1)
    tabla_productos.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#000080')),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 8),
        ('FONTNAME', (0,1), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,1), (-1,-1), 7),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        # Columnas del Excel en amarillo
        ('BACKGROUND', (0,1), (0,-1), colors.yellow),  # Pallet
        ('BACKGROUND', (1,1), (1,-1), colors.yellow),  # Quantity
        ('BACKGROUND', (2,1), (2,-1), colors.yellow),  # Boxes
        ('BACKGROUND', (3,1), (3,-1), colors.yellow),  # Product No
        ('BACKGROUND', (5,1), (5,-1), colors.yellow),  # Lot
        ('BACKGROUND', (6,1), (6,-1), colors.yellow),  # Date
    ]))
    elementos.append(tabla_productos)
    elementos.append(Spacer(1, 10))

    # TOTALES
    # Contar pallets únicos
    pallets_unicos = set()
    for reg in registros:
        if reg['pallet']:
            pallets_unicos.add(reg['pallet'])
    total_pallets = len(pallets_unicos)

    totales_headers = ["Total Pallets", "Dimensions (cm)", "Net weight (Kg)", "Gross weight (Kg)", "Total parts"]
    totales_values = [
        str(total_pallets),
        datos_comercio.get('dimensions', '100 X 110 X 109'),
        datos_comercio.get('net_weight', ''),
        datos_comercio.get('gross_weight', ''),
        str(total_quantity)
    ]
    
    totales_data = [totales_headers, totales_values]
    tabla_totales = Table(totales_data, colWidths=[1.4*inch]*5)
    tabla_totales.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E0E0E0')),
    ]))
    elementos.append(tabla_totales)
    elementos.append(Spacer(1, 12))

    # TRANSPORTE
    transporte_titulo = [["Información del transporte:"]]
    tabla_transporte_titulo = Table(transporte_titulo, colWidths=[7*inch])
    tabla_transporte_titulo.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 9),
    ]))
    elementos.append(tabla_transporte_titulo)
    elementos.append(Spacer(1, 4))

    transporte_data = [
        ["BL/AWB", "Linea", "No. De Placa", "No. De Sello", "Nombre del Conductor"],
        [datos_comercio.get('bl_awb', '-'), 
         datos_comercio.get('linea', 'FEDEX FREIGHT'),
         datos_comercio.get('placa', ''),
         datos_comercio.get('sello_transporte', '-'),
         datos_comercio.get('conductor', '')]
    ]
    tabla_transporte = Table(transporte_data, colWidths=[1.4*inch]*5)
    tabla_transporte.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E0E0E0')),
    ]))
    elementos.append(tabla_transporte)
    elementos.append(Spacer(1, 15))

    # FIRMAS
    firma_data = [
        ["Firma Conductor:", "", f"Fecha: {datos_comercio.get('fecha', datetime.now().strftime('%d/%m/%Y'))}"],
        ["", "", ""],
        ["Autoriza: Ana Maya", "", "Fecha:"],
        ["Foreign Trade and Logistics Coordinator", "", ""]
    ]
    tabla_firmas = Table(firma_data, colWidths=[2.3*inch, 2.4*inch, 2.3*inch])
    tabla_firmas.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (0,-1), 'LEFT'),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
    ]))
    elementos.append(tabla_firmas)

    doc.build(elementos)
    buffer.seek(0)
    return buffer

# -----------------------
# Streamlit UI
# -----------------------
def main():
    st.set_page_config(page_title="HSPS Packing List Generator", page_icon="📦", layout="wide")
    st.title("📦 Generador Packing List HSPS")
    st.markdown("*Conversión directa de Excel (Hoja ZF) a PDF formato oficial HSPS*")
    
    if 'uploaded' not in st.session_state:
        st.session_state.uploaded = False

    paso = st.sidebar.radio("Navegación:", ["1️⃣ Subir Excel", "2️⃣ Datos Comercio Exterior", "3️⃣ Generar PDF"])

    if paso == "1️⃣ Subir Excel":
        st.header("Paso 1: Cargar Excel de Almacén")
        st.info("📄 Sube el archivo Excel con la hoja 'ZF' (formato HSPS-ALM-8.5.4-R09)")
        
        archivo = st.file_uploader("Selecciona el archivo Excel", type=['xlsx','xls'])
        
        if archivo:
            try:
                # Leer hoja ZF
                df = leer_hoja_zf(archivo)
                st.success("✅ Hoja ZF cargada exitosamente")
                
                with st.expander("Ver datos originales de la hoja ZF"):
                    st.dataframe(df)
                
                # Extraer datos
                registros, columnas_detectadas = extraer_datos_excel(df)
                
                st.subheader(f"📊 {len(registros)} registros detectados")
                
                # Mostrar columnas detectadas
                st.subheader("Columnas detectadas en el Excel:")
                col1, col2 = st.columns(2)
                with col1:
                    st.write("🔢 **Numero de Pallet:**", columnas_detectadas['col_pallet'] or '❌ No detectado')
                    st.write("📦 **Cantidad:**", columnas_detectadas['col_cantidad'] or '❌ No detectado')
                    st.write("📦 **Total de Cajas:**", columnas_detectadas['col_cajas'] or '❌ No detectado')
                with col2:
                    st.write("🏷️ **N. Lote:**", columnas_detectadas['col_lote'] or '❌ No detectado')
                    st.write("📅 **Fecha:**", columnas_detectadas['col_fecha'] or '❌ No detectado')
                    st.write("🔧 **N. Parte:**", columnas_detectadas['col_parte'] or '❌ No detectado')
                
                # Mostrar vista previa de registros procesados
                with st.expander("Ver registros extraídos (tal como se pasarán al PDF)"):
                    df_preview = pd.DataFrame(registros)
                    st.dataframe(df_preview)
                
                # Guardar en sesión
                st.session_state.registros = registros
                st.session_state.columnas_detectadas = columnas_detectadas
                st.session_state.uploaded = True
                
                st.success("✅ Datos procesados. Continúa al Paso 2 →")
                
            except Exception as e:
                st.error(f"❌ Error leyendo Excel: {e}")
                st.exception(e)

    elif paso == "2️⃣ Datos Comercio Exterior":
        if not st.session_state.get('uploaded'):
            st.warning("⚠️ Primero sube el Excel en el Paso 1")
            return
        
        st.header("Paso 2: Información de Comercio Exterior")
        st.info("📋 Completa los datos adicionales que no están en el Excel")
        
        with st.form("comercio"):
            st.subheader("Información de envío")
            col1, col2, col3 = st.columns(3)
            with col1:
                shipping_date = st.date_input("Shipping date", value=datetime.now())
            with col2:
                seal_no = st.text_input("Seal No.", value="N/A")
            with col3:
                packing_slip_no = st.text_input("Packing Slip No.", value="")
            
            commercial_invoice = st.text_input("Commercial Invoice No.", value="")
            
            st.subheader("Destinatarios")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Ship to:**")
                ship_to_name = st.text_input("Company Name", value="ZF PASSIVE SAFETY US INC.")
                ship_to_address = st.text_input("Address", value="9600 International Boulevard, Docks 5-8")
                ship_to_city = st.text_input("City/State/ZIP", value="Pharr, Tx, USA, C.P 78577")
                ship_to_tax = st.text_input("TAX ID", value="341758354")
            with col2:
                st.markdown("**Bill to:**")
                bill_to_name = st.text_input("Company Name ", value="TRW VEHICLE SAFETY SYSTEMS")
                bill_to_address = st.text_input("Address ", value="Blvd Mike Allen 1370 S/N")
                bill_to_city = st.text_input("City ", value="Parque Industrial Reynosa")
                bill_to_state = st.text_input("State/ZIP ", value="Reynosa, Tamaulipas, Mex. C.P 88788")
            
            st.subheader("Detalles de envío")
            col1, col2 = st.columns(2)
            with col1:
                shipping_method = st.text_input("Shipping method", value="LTL")
                incoterm = st.text_input("Incoterm", value="FCA")
                country_origin = st.text_input("Country of Origin", value="México")
                country_destination = st.text_input("Country of Destination", value="Mexico")
            with col2:
                dimensions = st.text_input("Dimensions (cm)", value="100 X 110 X 109")
                net_weight = st.text_input("Net weight (Kg)", value="")
                gross_weight = st.text_input("Gross weight (Kg)", value="")
            
            st.subheader("Transporte")
            col1, col2 = st.columns(2)
            with col1:
                bl_awb = st.text_input("BL/AWB", value="-")
                linea = st.text_input("Línea", value="FEDEX FREIGHT")
                placa = st.text_input("No. De Placa", value="")
            with col2:
                sello_transporte = st.text_input("No. De Sello", value="-")
                conductor = st.text_input("Nombre del Conductor", value="")
            
            submitted = st.form_submit_button("💾 Guardar Datos", use_container_width=True)
            
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
                    'fecha': shipping_date.strftime('%d/%m/%Y')
                }
                st.success("✅ Datos guardados correctamente. Continúa al Paso 3 →")

    elif paso == "3️⃣ Generar PDF":
        if not st.session_state.get('uploaded'):
            st.warning("⚠️ Primero sube el Excel en el Paso 1")
            return
        
        if 'datos_comercio' not in st.session_state:
            st.warning("⚠️ Primero completa los datos de Comercio Exterior en el Paso 2")
            return
        
        st.header("Paso 3: Generar PDF")
        
        registros = st.session_state.registros
        datos_comercio = st.session_state.datos_comercio
        
        # Calcular totales
        pallets_unicos = set()
        total_piezas = 0
        total_cajas = 0
        
        for reg in registros:
            if reg['pallet']:
                pallets_unicos.add(reg['pallet'])
            try:
                total_piezas += parse_int(reg['cantidad'])
            except:
                pass
            try:
                total_cajas += parse_int(reg['cajas'])
            except:
                pass
        
        # Resumen
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 Registros", len(registros))
        with col2:
            st.metric("📦 Total Pallets", len(pallets_unicos))
        with col3:
            st.metric("🔢 Total Piezas", total_piezas)
        with col4:
            st.metric("📦 Total Cajas", total_cajas)
        
        st.subheader("Vista previa de datos")
        with st.expander("Ver registros que se incluirán en el PDF"):
            df_preview = pd.DataFrame(registros)
            st.dataframe(df_preview, use_container_width=True)
        
        with st.expander("Ver datos de Comercio Exterior"):
            st.json(datos_comercio)
        
        st.divider()
        
        nombre_archivo = st.text_input(
            "Nombre del archivo PDF", 
            value=f"PackingList_HSPS_{datetime.now().strftime('%Y%m%d_%H%M')}",
            help="Sin extensión .pdf"
        )
        
        col1, col2, col3 = st.columns([2, 1, 2])
        with col2:
            generar_btn = st.button("🚀 Generar PDF", type="primary", use_container_width=True)
        
        if generar_btn:
            try:
                with st.spinner("Generando PDF en formato HSPS..."):
                    buffer = generar_pdf_hsps(registros, datos_comercio)
                
                st.success("✅ PDF generado exitosamente!")
                
                st.download_button(
                    label="⬇️ Descargar Packing List PDF",
                    data=buffer.getvalue(),
                    file_name=f"{nombre_archivo}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary"
                )
                
                st.balloons()
                
                # Información adicional
                st.info("""
                **✓ Los siguientes datos fueron tomados EXACTAMENTE del Excel (columnas en amarillo):**
                - Numero de Pallet
                - Cantidad
                - Total de Cajas
                - N. Parte
                - N. Lote
                - Fecha
                
                **✓ Los demás datos fueron proporcionados por Comercio Exterior**
                """)
                
            except Exception as e:
                st.error(f"❌ Error generando PDF: {e}")
                st.exception(e)

if __name__ == "__main__":
    main()