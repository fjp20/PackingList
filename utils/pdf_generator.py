import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

def parse_float(value, default=0.0):
    """Convierte un valor a float de forma segura"""
    try:
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().replace(',', '').replace(' ', '')
        if s == '':
            return default
        return float(s)
    except:
        return default

def parse_int(value, default=0):
    """Convierte un valor a entero de forma segura"""
    try:
        if isinstance(value, (int, float)):
            return int(value)
        s = str(value).strip().replace(',', '').replace(' ', '')
        if s == '':
            return default
        return int(float(s))
    except:
        return default

def calcular_pesos_por_pallet(registros):
    """
    Calcula el peso neto y bruto por pallet
    Suma peso_lote y peso_acumulado para cada pallet único
    """
    pesos_por_pallet = {}
    
    for reg in registros:
        pallet = reg.get('numero_pallet', '')
        if not pallet:
            continue
        
        peso_lote = parse_float(reg.get('peso_lote', 0))
        peso_acumulado = parse_float(reg.get('peso_acumulado', 0))
        
        if pallet not in pesos_por_pallet:
            pesos_por_pallet[pallet] = {
                'peso_neto': 0.0,
                'peso_bruto': 0.0
            }
        
        pesos_por_pallet[pallet]['peso_neto'] += peso_lote
        pesos_por_pallet[pallet]['peso_bruto'] += peso_acumulado
    
    return pesos_por_pallet

def formatear_lista_pesos(pesos_por_pallet):
    """
    Formatea los pesos por pallet en una lista ordenada
    Retorna dos listas: net_weights y gross_weights
    """
    # Ordenar pallets numéricamente
    pallets_ordenados = sorted(pesos_por_pallet.keys(), key=lambda x: int(x) if x.isdigit() else 0)
    
    net_weights = []
    gross_weights = []
    
    for pallet in pallets_ordenados:
        net_weights.append(f"{pesos_por_pallet[pallet]['peso_neto']:.2f}")
        gross_weights.append(f"{pesos_por_pallet[pallet]['peso_bruto']:.2f}")
    
    return net_weights, gross_weights

def generar_pdf_hsps(registros, datos_comercio, config_manager, modelo):
    """
    Genera el PDF en formato HSPS con configuración desde JSON
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elementos = []
    styles = getSampleStyleSheet()

    # Obtener configuración del modelo
    pdf_cfg = config_manager.get_pdf_config(modelo)
    if not pdf_cfg:
        raise Exception(f"No hay configuración de PDF para el modelo '{modelo}'")
    
    shipper_cfg = pdf_cfg.get('shipper', {})
    ship_to_cfg = pdf_cfg.get('ship_to', {})
    bill_to_cfg = pdf_cfg.get('bill_to', {})
    descripcion_producto = pdf_cfg.get('descripcion_producto', 'PRODUCTO')

    # Calcular pesos por pallet
    pesos_por_pallet = calcular_pesos_por_pallet(registros)
    net_weights, gross_weights = formatear_lista_pesos(pesos_por_pallet)

    # Estilos personalizados
    title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=16, 
                                  textColor=colors.HexColor('#000080'), alignment=TA_CENTER, 
                                  spaceAfter=6, fontName='Helvetica-Bold')
    header_style = ParagraphStyle('Header', parent=styles['Normal'], fontSize=8, fontName='Helvetica-Bold')
    normal_style = ParagraphStyle('CustomNormal', parent=styles['Normal'], fontSize=8, fontName='Helvetica')

    # ENCABEZADO
    encabezado_data = [
        [Paragraph("<b>PACKING SLIP</b>", title_style)],
        [Paragraph(f"<b>{shipper_cfg.get('nombre', 'EMPRESA')}</b>", header_style)],
        [Paragraph(shipper_cfg.get('direccion', ''), normal_style)],
        [Paragraph(f"{shipper_cfg.get('ciudad', '')} {shipper_cfg.get('estado', '')}", normal_style)],
        [Paragraph(shipper_cfg.get('cp', ''), normal_style)]
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
{shipper_cfg.get('nombre', '')}<br/>
{shipper_cfg.get('direccion', '')}<br/>
{shipper_cfg.get('ciudad', '')}<br/>
{shipper_cfg.get('estado', '')}<br/>
{shipper_cfg.get('cp', '')}"""

    shipto_text = f"""<b>Ship to:</b><br/>
{datos_comercio.get('ship_to_name', ship_to_cfg.get('nombre', ''))}<br/>
{datos_comercio.get('ship_to_address', ship_to_cfg.get('direccion', ''))}<br/>
{datos_comercio.get('ship_to_city', ship_to_cfg.get('ciudad', ''))}<br/>
TAX ID: {datos_comercio.get('ship_to_tax', ship_to_cfg.get('tax_id', ''))}"""

    billto_text = f"""<b>Bill to:</b><br/>
{datos_comercio.get('bill_to_name', bill_to_cfg.get('nombre', ''))}<br/>
{datos_comercio.get('bill_to_address', bill_to_cfg.get('direccion', ''))}<br/>
{datos_comercio.get('bill_to_city', bill_to_cfg.get('ciudad', ''))}<br/>
{datos_comercio.get('bill_to_state', bill_to_cfg.get('estado', ''))}"""

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
    tabla_info = Table(info_adicional, colWidths=[1.4*inch]*5)
    tabla_info.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E0E0E0')),
    ]))
    elementos.append(tabla_info)
    elementos.append(Spacer(1, 10))

    # TABLA DE PRODUCTOS
    headers = ["Pallets No.", "Quantity", "Boxes", "Product No.", "Description", "Lot", "Manufacturing date"]
    table_data = [headers]

    total_quantity = 0
    ultimo_pallet = ""

    for reg in registros:
        pallet_actual = reg.get('numero_pallet', '')
        pallet_display = pallet_actual if pallet_actual != ultimo_pallet else ''
        ultimo_pallet = pallet_actual
        
        fila = [
            pallet_display,
            reg.get('cantidad', ''),
            reg.get('total_cajas', ''),
            reg.get('n_parte', ''),
            descripcion_producto,
            reg.get('n_lote', ''),
            reg.get('fecha', '')
        ]
        table_data.append(fila)
        total_quantity += parse_int(reg.get('cantidad', 0))

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
        ('BACKGROUND', (0,1), (0,-1), colors.yellow),
        ('BACKGROUND', (1,1), (1,-1), colors.yellow),
        ('BACKGROUND', (2,1), (2,-1), colors.yellow),
        ('BACKGROUND', (3,1), (3,-1), colors.yellow),
        ('BACKGROUND', (5,1), (5,-1), colors.yellow),
        ('BACKGROUND', (6,1), (6,-1), colors.yellow),
    ]))
    elementos.append(tabla_productos)
    elementos.append(Spacer(1, 10))

    # TOTALES CON PESOS CALCULADOS
    pallets_unicos = sorted(set(reg.get('numero_pallet', '') for reg in registros if reg.get('numero_pallet')), 
                           key=lambda x: int(x) if x.isdigit() else 0)
    
    # Calcular totales
    total_peso_neto = sum(pesos_por_pallet[p]['peso_neto'] for p in pallets_unicos)
    total_peso_bruto = sum(pesos_por_pallet[p]['peso_bruto'] for p in pallets_unicos)
    
    totales_headers = ["Total Pallets", "Dimensions (cm)", "Net weight (Kg)", "Gross weight (Kg)", "Total parts"]
    
    # Formatear pesos por pallet
    net_weight_str = '<br/>'.join(net_weights) + f'<br/><b>TOTAL: {total_peso_neto:.2f}</b>'
    gross_weight_str = '<br/>'.join(gross_weights) + f'<br/><b>TOTAL: {total_peso_bruto:.2f}</b>'
    
    totales_values = [
        str(len(pallets_unicos)),
        datos_comercio.get('dimensions', '100 X 110 X 109'),
        Paragraph(net_weight_str, normal_style),
        Paragraph(gross_weight_str, normal_style),
        str(total_quantity)
    ]
    
    totales_data = [totales_headers, totales_values]
    tabla_totales = Table(totales_data, colWidths=[1.4*inch]*5)
    tabla_totales.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#E0E0E0')),
    ]))
    elementos.append(tabla_totales)
    elementos.append(Spacer(1, 12))

    # TRANSPORTE
    transporte_titulo = [["Información del transporte:"]]
    tabla_transporte_titulo = Table(transporte_titulo, colWidths=[7*inch])
    tabla_transporte_titulo.setStyle(TableStyle([('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,0), 9)]))
    elementos.append(tabla_transporte_titulo)
    elementos.append(Spacer(1, 4))

    transporte_data = [
        ["BL/AWB", "Linea", "No. De Placa", "No. De Sello", "Nombre del Conductor"],
        [datos_comercio.get('bl_awb', '-'), datos_comercio.get('linea', 'FEDEX FREIGHT'),
         datos_comercio.get('placa', ''), datos_comercio.get('sello_transporte', '-'),
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