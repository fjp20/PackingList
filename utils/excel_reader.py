import re
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any

def normalize_header(h):
    """Normaliza encabezados eliminando acentos y caracteres especiales"""
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
    """Convierte un valor a entero de forma segura"""
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

def find_column(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    """Busca una columna en el DataFrame usando lista de aliases"""
    cols_lower = {col: str(col).lower().strip() for col in df.columns}
    
    for col, col_lower in cols_lower.items():
        for alias in aliases:
            if alias.lower() in col_lower or col_lower in alias.lower():
                return col
    return None

def leer_hoja_excel(archivo, hoja_nombre: Optional[str] = None, 
                    buscar_en_filas: int = 5,
                    detener_en: List[str] = None) -> pd.DataFrame:
    """
    Lee una hoja de Excel con detección inteligente de encabezados
    
    Args:
        archivo: Archivo Excel cargado
        hoja_nombre: Nombre de la hoja a leer (None = primera hoja)
        buscar_en_filas: Número de filas donde buscar encabezados
        detener_en: Lista de palabras que indican fin de datos
    """
    if detener_en is None:
        detener_en = ["TOTAL GENERAL", "Total General", "TOTAL"]
    
    # Leer hoja
    try:
        if hoja_nombre:
            df = pd.read_excel(archivo, sheet_name=hoja_nombre, header=None)
        else:
            df = pd.read_excel(archivo, header=None)
    except Exception as e:
        raise Exception(f"Error leyendo hoja '{hoja_nombre}': {e}")
    
    # Buscar fila de encabezados
    header_row = 0
    for idx in range(min(buscar_en_filas, len(df))):
        row_str = ' '.join([str(x).lower() for x in df.iloc[idx] if not pd.isna(x)])
        # Buscar palabras clave comunes en encabezados
        if any(word in row_str for word in ['pallet', 'lote', 'fecha', 'cantidad', 'cajas', 'parte']):
            header_row = idx
            break
    
    # Limpiar encabezados duplicados/vacíos
    headers = df.iloc[header_row].tolist()
    clean_headers = []
    seen_headers = {}
    
    for i, h in enumerate(headers):
        if pd.isna(h) or str(h).strip() == '':
            clean_headers.append(f'col_vacia_{i}')
        else:
            h_str = str(h).strip()
            if h_str in seen_headers:
                seen_headers[h_str] += 1
                clean_headers.append(f"{h_str}_{seen_headers[h_str]}")
            else:
                seen_headers[h_str] = 0
                clean_headers.append(h_str)
    
    # Establecer encabezados y datos
    df.columns = clean_headers
    df = df.iloc[header_row + 1:].reset_index(drop=True)
    
    # Limpiar filas vacías
    df = df.dropna(how='all')
    
    # Detener en palabras clave
    for idx, row in df.iterrows():
        row_str = ' '.join([str(x).lower() for x in row if not pd.isna(x)])
        if any(palabra.lower() in row_str for palabra in detener_en):
            df = df.iloc[:idx]
            break
    
    return df

def extraer_datos_excel(df: pd.DataFrame, columnas_config: Dict[str, List[str]]) -> Tuple[List[Dict], Dict]:
    """
    Extrae datos del DataFrame usando configuración de columnas
    
    Args:
        df: DataFrame con los datos
        columnas_config: Diccionario con aliases de columnas
    
    Returns:
        Tuple con (registros, columnas_encontradas)
    """
    # Encontrar columnas
    columnas_encontradas = {}
    for nombre_col, aliases in columnas_config.items():
        col_encontrada = find_column(df, aliases)
        columnas_encontradas[nombre_col] = col_encontrada
    
    # Extraer registros
    registros = []
    
    for idx, row in df.iterrows():
        # Verificar que la fila no esté vacía
        col_pallet = columnas_encontradas.get('numero_pallet')
        col_cantidad = columnas_encontradas.get('cantidad')
        
        if col_pallet and col_cantidad:
            if pd.isna(row.get(col_pallet)) and pd.isna(row.get(col_cantidad)):
                continue
        
        # Crear registro
        registro = {}
        for nombre_col, col_excel in columnas_encontradas.items():
            if col_excel:
                val = row.get(col_excel, '')
                if pd.isna(val) or val == '':
                    registro[nombre_col] = ''
                else:
                    registro[nombre_col] = str(val).strip()
            else:
                registro[nombre_col] = ''
        
        registros.append(registro)
    
    return registros, columnas_encontradas

def leer_hoja_calculos(archivo, hoja_nombre: str, calculos_config: Dict) -> Dict[str, str]:
    """
    Lee la hoja de cálculos (peso, dimensiones) según configuración
    
    Args:
        archivo: Archivo Excel
        hoja_nombre: Nombre de la hoja
        calculos_config: Configuración del método de extracción
    
    Returns:
        Diccionario con peso_neto, peso_bruto, dimensiones
    """
    resultado = {
        'net_weight': '',
        'gross_weight': '',
        'dimensions': ''
    }
    
    try:
        df = pd.read_excel(archivo, sheet_name=hoja_nombre, header=None)
        
        metodo = calculos_config.get('metodo', 'busqueda')
        
        if metodo == 'celda_fija':
            # Método 1: Leer de celdas específicas
            peso_neto_cfg = calculos_config.get('peso_neto', {})
            peso_bruto_cfg = calculos_config.get('peso_bruto', {})
            dim_cfg = calculos_config.get('dimensiones', {})
            
            if peso_neto_cfg:
                fila = peso_neto_cfg.get('fila', 0)
                col = peso_neto_cfg.get('columna', 0)
                if fila < len(df) and col < len(df.columns):
                    resultado['net_weight'] = str(df.iloc[fila, col]).strip()
            
            if peso_bruto_cfg:
                fila = peso_bruto_cfg.get('fila', 0)
                col = peso_bruto_cfg.get('columna', 0)
                if fila < len(df) and col < len(df.columns):
                    resultado['gross_weight'] = str(df.iloc[fila, col]).strip()
            
            if dim_cfg:
                fila = dim_cfg.get('fila', 0)
                col = dim_cfg.get('columna', 0)
                if fila < len(df) and col < len(df.columns):
                    resultado['dimensions'] = str(df.iloc[fila, col]).strip()
        
        elif metodo == 'busqueda':
            # Método 2: Buscar por palabras clave
            keywords = calculos_config.get('keywords', {})
            
            for campo, palabras_clave in keywords.items():
                valor = buscar_valor_por_keyword(df, palabras_clave)
                if valor:
                    resultado[campo] = valor
        
    except Exception as e:
        print(f"⚠️ Error leyendo hoja de cálculos: {e}")
    
    return resultado

def buscar_valor_por_keyword(df: pd.DataFrame, keywords: List[str]) -> str:
    """Busca un valor en el DataFrame basado en palabras clave"""
    for keyword in keywords:
        for idx, row in df.iterrows():
            for col_idx, val in enumerate(row):
                if pd.isna(val):
                    continue
                
                cell = str(val).lower()
                if keyword.lower() in cell:
                    # El valor suele estar en la celda siguiente (misma fila, siguiente columna)
                    try:
                        if col_idx + 1 < len(row):
                            siguiente = row.iloc[col_idx + 1]
                            if not pd.isna(siguiente):
                                return str(siguiente).strip()
                    except:
                        pass
                    
                    # O en la fila siguiente, misma columna
                    try:
                        if idx + 1 < len(df):
                            siguiente = df.iloc[idx + 1, col_idx]
                            if not pd.isna(siguiente):
                                return str(siguiente).strip()
                    except:
                        pass
    return ''

def obtener_hojas_disponibles(archivo) -> List[str]:
    """Obtiene lista de hojas disponibles en el Excel"""
    try:
        return pd.ExcelFile(archivo).sheet_names
    except:
        return []