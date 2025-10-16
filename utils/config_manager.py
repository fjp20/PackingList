import json
from typing import Dict, List, Optional
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
                print(f"Archivo {self.config_path} no encontrado")
                return {}
        except Exception as e:
            print(f"Error cargando configuración: {e}")
            return {}
    
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
    
    def get_calculos_config(self, modelo: str) -> Optional[Dict]:
        """Obtiene configuración de cálculos"""
        excel_cfg = self.get_excel_config(modelo)
        return excel_cfg.get('calculos') if excel_cfg else None
    
    def validate_model(self, modelo: str) -> tuple:
        """Valida que un modelo tenga toda la configuración necesaria"""
        errors = []
        model_cfg = self.get_model_config(modelo)
        
        if not model_cfg:
            return False, [f"Modelo '{modelo}' no encontrado"]
        
        if 'excel' not in model_cfg:
            errors.append("Falta sección 'excel'")
        
        if 'pdf' not in model_cfg:
            errors.append("Falta sección 'pdf'")
        
        return len(errors) == 0, errors


def get_modelo_info(config_manager, modelo: str) -> str:
    """Obtiene información descriptiva de un modelo"""
    model_cfg = config_manager.get_model_config(modelo)
    if model_cfg:
        nombre = model_cfg.get('nombre_completo', modelo)
        return nombre
    return modelo