"""
Servicio de actualización automática de ubicaciones GPS
Envía SMS cada X segundos a todos los vehículos para solicitar su ubicación
"""
import threading
import time
from datetime import datetime
import os
from dotenv import load_dotenv

# Importar Twilio
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Advertencia: Twilio no está disponible")

load_dotenv()

class AutoUpdateService:
    """
    Servicio que envía SMS automáticamente cada X segundos
    para solicitar ubicación a todos los vehículos GPS
    """
    
    def __init__(self, session_factory, gps_device_model, interval_seconds=10):
        """
        Args:
            session_factory: Función que retorna una sesión de base de datos
            gps_device_model: Modelo GPSDevice
            interval_seconds: Intervalo en segundos entre envíos (default: 10)
        """
        self.session_factory = session_factory
        self.gps_device_model = gps_device_model
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.thread = None
        self.last_update = None
        self.stats = {
            'total_sent': 0,
            'total_errors': 0,
            'last_sent_time': None
        }
        
        # Configurar Twilio
        if TWILIO_AVAILABLE:
            account_sid = os.getenv('TWILIO_ACCOUNT_SID')
            auth_token = os.getenv('TWILIO_AUTH_TOKEN')
            twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
            
            if account_sid and auth_token:
                try:
                    self.twilio_client = Client(account_sid, auth_token)
                    self.twilio_phone = twilio_phone
                    self.twilio_configured = True
                except Exception as e:
                    print(f"Error configurando Twilio: {e}")
                    self.twilio_configured = False
            else:
                self.twilio_configured = False
        else:
            self.twilio_configured = False
    
    def _format_phone_number(self, phone):
        """
        Formatea el número de teléfono para envío internacional
        """
        phone = str(phone).strip()
        
        # Si no tiene código de país, asumir Colombia (+57)
        if not phone.startswith('+'):
            # Remover espacios y caracteres especiales
            phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            
            # Si empieza con 0, removerlo
            if phone.startswith('0'):
                phone = phone[1:]
            
            # Agregar código de país de Colombia
            if not phone.startswith('57'):
                phone = f'+57{phone}'
            else:
                phone = f'+{phone}'
        
        return phone
    
    def _send_location_request(self, device):
        """
        Envía un SMS a un dispositivo para solicitar su ubicación
        """
        if not self.twilio_configured:
            return {
                'success': False,
                'error': 'Twilio no está configurado'
            }
        
        if not device.placa_gps:
            return {
                'success': False,
                'error': 'Dispositivo no tiene número de SIM configurado'
            }
        
        try:
            to_number = self._format_phone_number(device.placa_gps)
            message = 'LOC'  # Comando para solicitar ubicación
            
            # Enviar SMS
            message_obj = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_phone,
                to=to_number
            )
            
            return {
                'success': True,
                'message_sid': message_obj.sid,
                'to': to_number,
                'device_name': device.name
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'device_name': device.name
            }
    
    def _update_loop(self):
        """
        Loop principal que envía SMS cada X segundos
        """
        while self.is_running:
            try:
                session = self.session_factory()
                
                try:
                    # Obtener todos los vehículos activos (no eliminados)
                    devices = session.query(self.gps_device_model).filter(
                        self.gps_device_model.status != 'deleted'
                    ).all()
                    
                    # Filtrar solo los que tienen número de SIM configurado
                    devices_with_sim = [d for d in devices if d.placa_gps]
                    
                    if devices_with_sim:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Enviando SMS a {len(devices_with_sim)} vehículos...")
                        
                        for device in devices_with_sim:
                            result = self._send_location_request(device)
                            
                            if result['success']:
                                self.stats['total_sent'] += 1
                                print(f"  ✓ SMS enviado a {result['device_name']} ({result['to']})")
                            else:
                                self.stats['total_errors'] += 1
                                print(f"  ✗ Error enviando a {result.get('device_name', 'desconocido')}: {result.get('error', 'Error desconocido')}")
                        
                        self.stats['last_sent_time'] = datetime.now()
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] No hay vehículos con SIM configurado")
                    
                finally:
                    session.close()
                
                # Esperar el intervalo antes de la siguiente iteración
                time.sleep(self.interval_seconds)
                
            except Exception as e:
                print(f"Error en loop de actualización: {e}")
                self.stats['total_errors'] += 1
                time.sleep(self.interval_seconds)
    
    def start(self):
        """
        Inicia el servicio de actualización automática
        """
        if self.is_running:
            return {'status': 'already_running', 'message': 'El servicio ya está corriendo'}
        
        if not self.twilio_configured:
            return {
                'status': 'error',
                'message': 'Twilio no está configurado. Verifica las variables de entorno.'
            }
        
        self.is_running = True
        self.thread = threading.Thread(target=self._update_loop, daemon=True)
        self.thread.start()
        
        return {
            'status': 'started',
            'message': f'Servicio iniciado. Enviando SMS cada {self.interval_seconds} segundos.',
            'interval': self.interval_seconds
        }
    
    def stop(self):
        """
        Detiene el servicio de actualización automática
        """
        if not self.is_running:
            return {'status': 'not_running', 'message': 'El servicio no está corriendo'}
        
        self.is_running = False
        
        # Esperar a que el thread termine (máximo 2 segundos)
        if self.thread:
            self.thread.join(timeout=2)
        
        return {
            'status': 'stopped',
            'message': 'Servicio detenido',
            'stats': self.get_stats()
        }
    
    def get_status(self):
        """
        Obtiene el estado actual del servicio
        """
        return {
            'is_running': self.is_running,
            'interval_seconds': self.interval_seconds,
            'twilio_configured': self.twilio_configured,
            'stats': self.get_stats()
        }
    
    def get_stats(self):
        """
        Obtiene estadísticas del servicio
        """
        return {
            'total_sent': self.stats['total_sent'],
            'total_errors': self.stats['total_errors'],
            'last_sent_time': self.stats['last_sent_time'].isoformat() if self.stats['last_sent_time'] else None
        }
    
    def set_interval(self, seconds):
        """
        Cambia el intervalo de actualización
        """
        if seconds < 5:
            return {'status': 'error', 'message': 'El intervalo mínimo es 5 segundos'}
        
        old_interval = self.interval_seconds
        self.interval_seconds = seconds
        
        return {
            'status': 'updated',
            'message': f'Intervalo actualizado de {old_interval}s a {seconds}s',
            'new_interval': seconds
        }

