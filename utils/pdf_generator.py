import json
import os
from typing import Dict, List, Optional, Any
from pathlib import Path

class ConfigManager:
    """Gestor de configuraciones de modelos desde JSON"""
    
    def __init__(self, config_path: str = "config/models.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Carga la configuración desde el archivo JSON"""
        try:
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                print(f"⚠️ Archivo {self.config_path} no encontrado. Usando configuración vacía.")
                return {}
        except Exception as e:
            print(f"❌ Error cargando configuración: {e}")
            return {}
    
    def save_config(self) -> bool:
        """Guarda la configuración actual en el archivo JSON"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Error guardando configuración: {e}")
            return False
    
    def get_models(self, activos_solo: bool = True) -> List[str]:
        """Obtiene lista de modelos disponibles"""
        if activos_solo:
            return [k for k, v in self.config.items() if v.get('activo', True)]
        return list(self.config.keys())
    
    def get_model_config(self, modelo: str) -> Optional[Dict]:
        """Obtiene la configuración completa de un modelo"""
        return self.config.get(modelo)
    
    def get_excel_config(self, modelo: str) -> Optional[Dict]:
        """Obtiene configuración de Excel para un modelo"""
        model_cfg = self.get_model_config(modelo)
        return model_cfg.get('excel') if model_cfg else None
    
    def get_pdf_config(self, modelo: str) -> Optional[Dict]:
        """Obtiene configuración de PDF para un modelo"""
        model_cfg = self.get_model_config(modelo)
        return model_cfg.get('pdf') if model_cfg else None
    
    def get_column_aliases(self, modelo: str, columna: str) -> List[str]:
        """Obtiene los aliases de una columna específica"""
        excel_cfg = self.get_excel_config(modelo)
        if excel_cfg and 'columnas' in excel_cfg:
            return excel_cfg['columnas'].get(columna, [])
        return []
    
    def get_calculos_config(self, modelo: str) -> Optional[Dict]:
        """Obtiene configuración de cálculos (peso/dimensiones)"""
        excel_cfg = self.get_excel_config(modelo)
        return excel_cfg.get('calculos') if excel_cfg else None
    
    def get_default_values(self, modelo: str) -> Dict:
        """Obtiene valores por defecto para el PDF"""
        pdf_cfg = self.get_pdf_config(modelo)
        return pdf_cfg.get('defaults', {}) if pdf_cfg else {}
    
    def add_model(self, nombre: str, config: Dict) -> bool:
        """Agrega un nuevo modelo a la configuración"""
        try:
            self.config[nombre] = config
            return self.save_config()
        except Exception as e:
            print(f"❌ Error agregando modelo: {e}")
            return False
    
    def update_model(self, nombre: str, config: Dict) -> bool:
        """Actualiza la configuración de un modelo existente"""
        if nombre in self.config:
            self.config[nombre].update(config)
            return self.save_config()
        return False
    
    def delete_model(self, nombre: str) -> bool:
        """Elimina un modelo de la configuración"""
        if nombre in self.config:
            del self.config[nombre]
            return self.save_config()
        return False
    
    def export_model(self, nombre: str, filepath: str) -> bool:
        """Exporta la configuración de un modelo a un archivo JSON"""
        try:
            model_cfg = self.get_model_config(nombre)
            if model_cfg:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump({nombre: model_cfg}, f, indent=2, ensure_ascii=False)
                return True
            return False
        except Exception as e:
            print(f"❌ Error exportando modelo: {e}")
            return False
    
    def import_model(self, filepath: str) -> bool:
        """Importa un modelo desde un archivo JSON"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                imported = json.load(f)
            
            for nombre, config in imported.items():
                self.config[nombre] = config
            
            return self.save_config()
        except Exception as e:
            print(f"❌ Error importando modelo: {e}")
            return False
    
    def validate_model(self, modelo: str) -> tuple[bool, List[str]]:
        """Valida que un modelo tenga toda la configuración necesaria"""
        errors = []
        model_cfg = self.get_model_config(modelo)
        
        if not model_cfg:
            return False, [f"Modelo '{modelo}' no encontrado"]
        
        # Validar secciones obligatorias
        if 'excel' not in model_cfg:
            errors.append("Falta sección 'excel'")
        else:
            excel_cfg = model_cfg['excel']
            if 'columnas' not in excel_cfg:
                errors.append("Falta 'excel.columnas'")
            if 'calculos' not in excel_cfg:
                errors.append("Falta 'excel.calculos'")
        
        if 'pdf' not in model_cfg:
            errors.append("Falta sección 'pdf'")
        else:
            pdf_cfg = model_cfg['pdf']
            required = ['descripcion_producto', 'shipper', 'ship_to', 'bill_to', 'defaults']
            for req in required:
                if req not in pdf_cfg:
                    errors.append(f"Falta 'pdf.{req}'")
        
        return len(errors) == 0, errors
    
    def get_all_column_aliases(self, modelo: str) -> Dict[str, List[str]]:
        """Obtiene todos los aliases de columnas de un modelo"""
        excel_cfg = self.get_excel_config(modelo)
        return excel_cfg.get('columnas', {}) if excel_cfg else {}

#Funciones generadas por chatgpt

def generar_pdf_hsps(registros, datos_comercio, config_manager, modelo):
    """
    Genera un PDF de Packing List basado en los registros, los datos de comercio
    y la configuración JSON del modelo.
    Devuelve un buffer BytesIO listo para descargar.
    """

    # Cargar configuración desde JSON
    model_pdf_cfg = config_manager.get_pdf_config(modelo) or {}
    global_cfg = _load_global_pdf_config()

    # Crear buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"Packing List - {modelo}",
        author=global_cfg.get("autor", "HSPS Logistics"),
        creator=global_cfg.get("creator", "HSPS Packing List Generator"),
    )

    styles = getSampleStyleSheet()
    elements = []

    # Encabezado
    title_color = colors.HexColor(global_cfg.get("title_color", "#000080"))
    elements.append(Paragraph(f"<b><font color='{title_color}'>PACKING LIST - {modelo}</font></b>", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Datos de comercio
    elements.append(Paragraph("<b>Datos de Envío</b>", styles["Heading2"]))
    for k, v in datos_comercio.items():
        elements.append(Paragraph(f"<b>{k.replace('_', ' ').capitalize()}:</b> {v}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Tabla de registros
    if registros:
        columnas = list(registros[0].keys())
        data = [columnas] + [[str(r.get(c, "")) for c in columnas] for r in registros]

        table = Table(data, repeatRows=1)
        table_style = TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor(global_cfg.get("header_bg_color", "#E0E0E0"))),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
        ])
        table.setStyle(table_style)
        elements.append(table)
    else:
        elements.append(Paragraph("No hay registros disponibles.", styles["Normal"]))

    # Pie de página
    elements.append(Spacer(1, 20))
    elements.append(Paragraph(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles["Italic"]))

    # Construir PDF
    doc.build(elements)
    buffer.seek(0)
    return buffer


def _load_global_pdf_config():
    """Carga configuración general desde config/default.json"""
    import json
    from pathlib import Path
    default_path = Path("config/default.json")

    if default_path.exists():
        with open(default_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            return cfg.get("pdf", {})
    return {}

# Funciones helper para usar en Streamlit
def load_config_manager(config_path: str = "config/models.json") -> ConfigManager:
    """Carga el gestor de configuraciones (cacheable en Streamlit)"""
    return ConfigManager(config_path)


def get_modelo_info(config_manager: ConfigManager, modelo: str) -> str:
    """Obtiene información descriptiva de un modelo"""
    model_cfg = config_manager.get_model_config(modelo)
    if model_cfg:
        nombre = model_cfg.get('nombre_completo', modelo)
        desc = model_cfg.get('descripcion', '')
        return f"{nombre} - {desc}" if desc else nombre
    return modelo