"""
Módulo para recibir y procesar SMS de placas GPS
La placa GPS envía SMS con la ubicación, este módulo los procesa
"""
import re
from datetime import datetime

# Importación diferida para evitar importaciones circulares
GPSDevice = None
Session = None

def _get_models():
    """Obtiene los modelos de forma diferida"""
    global GPSDevice, Session
    
    if GPSDevice is None or Session is None:
        try:
            # Intentar importar desde app.py (cuando se usa desde Flask)
            from app import GPSDevice as AppGPSDevice, Session as AppSession
            GPSDevice = AppGPSDevice
            Session = AppSession
        except ImportError:
            # Si no se puede, crear la sesión directamente
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            import os
            from dotenv import load_dotenv
            
            load_dotenv()
            DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///gps_devices.db')
            engine = create_engine(DATABASE_URL, echo=False)
            Session = sessionmaker(bind=engine)
            
            # Importar el modelo desde app
            import sys
            import importlib.util
            spec = importlib.util.spec_from_file_location("app", "app.py")
            app_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(app_module)
            GPSDevice = app_module.GPSDevice
    
    return GPSDevice, Session

class SMSGPSHandler:
    """
    Procesa SMS recibidos de placas GPS
    Formato típico de SMS GPS: "LAT:7.1254,LON:-73.1198" o similar
    """
    
    @staticmethod
    def parse_sms(sms_text, phone_number):
        """
        Parsea un SMS recibido de una placa GPS
        
        Args:
            sms_text: Texto del SMS (ej: "LAT:7.1254,LON:-73.1198" o "7.1254,-73.1198")
            phone_number: Número de teléfono que envió el SMS (número de la SIM)
        
        Returns:
            dict: Datos parseados o None si no se puede parsear
        """
        # Diferentes formatos que pueden enviar las placas GPS
        patterns = [
            # Formato: URL de Google Maps (N7.097760,W73.122780)
            r'maps\.google\.com/maps\?q=([NS])(\d+\.?\d*),([EW])(\d+\.?\d*)',
            # Formato: URL de Google Maps (q=N7.097760,W73.122780)
            r'q=([NS])(\d+\.?\d*),([EW])(\d+\.?\d*)',
            # Formato: LAT:7.1254,LON:-73.1198
            r'LAT[:\s]*([+-]?\d+\.?\d*)[,\s]+LON[:\s]*([+-]?\d+\.?\d*)',
            # Formato: 7.1254,-73.1198
            r'([+-]?\d+\.?\d*)[,\s]+([+-]?\d+\.?\d*)',
            # Formato: lat=7.1254&lon=-73.1198
            r'lat[=:]\s*([+-]?\d+\.?\d*)[,\s&]+lon[=:]\s*([+-]?\d+\.?\d*)',
            # Formato: GPS:7.1254,-73.1198
            r'GPS[:\s]*([+-]?\d+\.?\d*)[,\s]+([+-]?\d+\.?\d*)',
        ]
        
        for i, pattern in enumerate(patterns):
            match = re.search(pattern, sms_text, re.IGNORECASE)
            if match:
                try:
                    # Los primeros dos patrones son para URLs de Google Maps (N/E/W/S)
                    if i < 2:  # Formatos de Google Maps
                        direction_lat = match.group(1).upper()  # N o S
                        lat_value = float(match.group(2))
                        direction_lon = match.group(3).upper()  # E o W
                        lon_value = float(match.group(4))
                        
                        # Convertir según dirección
                        lat = lat_value if direction_lat == 'N' else -lat_value
                        lon = lon_value if direction_lon == 'E' else -lon_value
                    else:  # Formatos normales (LAT/LON o números)
                        lat = float(match.group(1))
                        lon = float(match.group(2))
                    
                    # Validar que sean coordenadas válidas
                    if -90 <= lat <= 90 and -180 <= lon <= 180:
                        return {
                            'latitude': lat,
                            'longitude': lon,
                            'phone_number': phone_number,
                            'raw_sms': sms_text
                        }
                except (ValueError, IndexError):
                    continue
        
        return None
    
    @staticmethod
    def process_sms(sms_text, phone_number):
        """
        Procesa un SMS y actualiza la ubicación del vehículo
        
        Args:
            sms_text: Texto del SMS
            phone_number: Número de teléfono (número de la SIM de la placa)
        
        Returns:
            dict: Resultado del procesamiento
        """
        GPSDevice, Session = _get_models()
        
        if GPSDevice is None or Session is None:
            return {
                'status': 'error',
                'message': 'No se pueden importar los modelos de la base de datos'
            }
        
        session = Session()
        try:
            # Parsear el SMS
            parsed = SMSGPSHandler.parse_sms(sms_text, phone_number)
            
            if not parsed:
                return {
                    'status': 'error',
                    'message': 'No se pudo parsear el SMS. Formato no reconocido.',
                    'received_sms': sms_text
                }
            
            # Buscar vehículo por número de SIM (phone_number)
            # El phone_number debe coincidir con placa_gps
            device = session.query(GPSDevice).filter_by(placa_gps=phone_number).first()
            
            if not device:
                # Intentar buscar por device_id
                device = session.query(GPSDevice).filter_by(device_id=phone_number).first()
            
            if not device:
                return {
                    'status': 'not_found',
                    'message': f'Vehículo con SIM {phone_number} no encontrado. Regístralo primero en la aplicación.',
                    'parsed_data': parsed
                }
            
            # Actualizar ubicación
            device.latitude = parsed['latitude']
            device.longitude = parsed['longitude']
            device.last_update = datetime.utcnow()
            
            session.commit()
            
            return {
                'status': 'success',
                'message': f'Ubicación actualizada para {device.name}',
                'device': {
                    'id': device.id,
                    'name': device.name,
                    'latitude': device.latitude,
                    'longitude': device.longitude
                }
            }
            
        except Exception as e:
            session.rollback()
            return {
                'status': 'error',
                'message': f'Error al procesar SMS: {str(e)}'
            }
        finally:
            session.close()

# Ejemplo de uso
if __name__ == '__main__':
    handler = SMSGPSHandler()
    
    # Simular SMS recibido
    test_sms = "LAT:7.1254,LON:-73.1198"
    phone = "3001234567"
    
    result = handler.process_sms(test_sms, phone)
    print("Resultado:", result)


