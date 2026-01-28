"""
Módulo para enviar SMS usando:
1. Módem GSM USB (usando AT commands)
2. Teléfono Android como pasarela (usando SMS Gateway API o ADB)
   - Simple SMS Gateway (http://IP:8080/send-sms) - RECOMENDADO
   - SMS Gateway App de Mattia A. (http://IP:8080/send)
   - Traccar SMS Gateway
   - Otras apps SMS Gateway similares
3. SMSMobileAPI (API en la nube - solo saldo local)
4. MessageBird (servicio de pago - confiable, sin prefijo)
5. Sinch SMS (servicio de pago - confiable)
6. Twilio (como respaldo)
"""
import os
import serial
import serial.tools.list_ports
import subprocess
import json
import time
import requests
from typing import Optional, Dict

class FreeSMSSender:
    """
    Envía SMS gratis usando módem GSM o teléfono Android
    """
    
    def __init__(self, method='auto'):
        """
        Args:
            method: 'gsm_modem', 'android_phone', 'twilio', o 'auto' (detecta automáticamente)
        """
        self.method = method
        self.gsm_port = None
        self.gsm_serial = None
        self.android_available = False
        self.android_gateway_url = os.getenv('ANDROID_SMS_GATEWAY_URL', '')
        self.android_gateway_token = os.getenv('ANDROID_SMS_GATEWAY_TOKEN', '')
        # API Key para SMSMobileAPI (api.smsmobileapi.com)
        self.smsmobileapi_key = os.getenv('SMSMOBILEAPI_KEY', '')
        # Credenciales para Sinch SMS
        self.sinch_service_plan_id = os.getenv('SINCH_SERVICE_PLAN_ID', '')
        self.sinch_api_token = os.getenv('SINCH_API_TOKEN', '')
        self.sinch_api_url = os.getenv('SINCH_API_URL', 'https://us.sms.api.sinch.com/xms/v1')
        self.sinch_from_number = os.getenv('SINCH_FROM_NUMBER', '447418631073')
        # Credenciales para MessageBird
        self.messagebird_api_key = os.getenv('MESSAGEBIRD_API_KEY', '').strip()
        self.messagebird_originator = os.getenv('MESSAGEBIRD_ORIGINATOR', 'MessageBird')
        
        # Debug: Verificar API Key al inicializar
        if self.messagebird_api_key:
            print(f"🔍 MessageBird API Key detectada al inicializar:")
            print(f"   - Longitud: {len(self.messagebird_api_key)} caracteres")
            print(f"   - Primeros 20: {self.messagebird_api_key[:20]}...")
            print(f"   - Últimos 10: ...{self.messagebird_api_key[-10:]}")
            print(f"   - Valor completo: {self.messagebird_api_key}")
            import sys
            sys.stdout.flush()
        
        # Detectar método automáticamente
        if method == 'auto':
            # Prioridad 1: SMSMobileAPI, MessageBird o Sinch (métodos automáticos sin prefijo)
            if self._check_android_gateway():
                self.method = 'android_phone'
                if self.smsmobileapi_key:
                    print("✓ SMSMobileAPI detectado (método preferido - sin prefijo)")
                elif self.messagebird_api_key:
                    print("✓ MessageBird detectado (método preferido - sin prefijo)")
                elif self.sinch_service_plan_id:
                    print("✓ Sinch SMS detectado (método preferido - sin prefijo)")
            # Prioridad 2: Módem GSM
            elif self._detect_gsm_modem():
                self.method = 'gsm_modem'
                print("✓ Módem GSM detectado")
            # Prioridad 3: Android ADB (semi-automático)
            elif self._detect_android_phone():
                self.method = 'android_phone'
                print("✓ Teléfono Android detectado (ADB)")
            else:
                self.method = None
                print("⚠ No se detectó módem GSM ni teléfono Android")
    
    def _detect_gsm_modem(self) -> bool:
        """
        Detecta si hay un módem GSM conectado
        """
        try:
            ports = serial.tools.list_ports.comports()
            for port in ports:
                # Buscar módems GSM comunes (Huawei, ZTE, etc.)
                if any(brand in port.description.lower() for brand in ['huawei', 'zte', 'gsm', 'modem', '3g', '4g']):
                    self.gsm_port = port.device
                    return True
            return False
        except Exception as e:
            print(f"Error detectando módem GSM: {e}")
            return False
    
    def _check_android_gateway(self) -> bool:
        """
        Verifica si hay una app SMS Gateway configurada (método automático)
        """
        # Verificar SMSMobileAPI primero (API en la nube - método preferido)
        if self.smsmobileapi_key:
            print(f"✓ SMSMobileAPI detectado con API KEY: {self.smsmobileapi_key[:20]}...")
            self.android_available = True
            return True
        else:
            print("⚠ SMSMobileAPI no configurado (SMSMOBILEAPI_KEY no encontrada)")
        
        # Verificar MessageBird (servicio confiable, sin prefijo)
        if self.messagebird_api_key:
            print(f"✓ MessageBird detectado con API KEY: {self.messagebird_api_key[:20]}...")
            self.android_available = True
            return True
        
        # Verificar Sinch SMS
        if self.sinch_service_plan_id and self.sinch_api_token:
            print(f"✓ Sinch SMS detectado con Service Plan ID: {self.sinch_service_plan_id[:20]}...")
            self.android_available = True
            return True
        
        # Verificar gateway local (SMS Gateway app de Mattia A. u otras apps similares)
        if self.android_gateway_url:
            print(f"✓ Android SMS Gateway URL configurada: {self.android_gateway_url}")
            self.android_available = True
            return True
        return False
    
    def _detect_android_phone(self) -> bool:
        """
        Detecta si hay un teléfono Android conectado vía ADB
        """
        # Primero verificar si hay SMS Gateway configurado (método preferido)
        if self._check_android_gateway():
            return True
            
        # Si no, verificar ADB
        try:
            result = subprocess.run(['adb', 'devices'], 
                                  capture_output=True, 
                                  text=True, 
                                  timeout=5)
            if result.returncode == 0 and 'device' in result.stdout:
                self.android_available = True
                return True
            return False
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
        except Exception as e:
            print(f"Error detectando Android: {e}")
            return False
    
    def _init_gsm_modem(self) -> bool:
        """
        Inicializa el módem GSM
        """
        if not self.gsm_port:
            return False
        
        try:
            self.gsm_serial = serial.Serial(
                port=self.gsm_port,
                baudrate=9600,
                timeout=5,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # Esperar a que el módem esté listo
            time.sleep(2)
            
            # Verificar que el módem responda
            self.gsm_serial.write(b'AT\r\n')
            time.sleep(0.5)
            response = self.gsm_serial.read(100).decode('utf-8', errors='ignore')
            
            if 'OK' in response:
                # Configurar modo texto
                self.gsm_serial.write(b'AT+CMGF=1\r\n')
                time.sleep(0.5)
                self.gsm_serial.read(100)
                return True
            
            return False
        except Exception as e:
            print(f"Error inicializando módem GSM: {e}")
            return False
    
    def _send_sms_gsm_modem(self, phone_number: str, message: str) -> Dict:
        """
        Envía SMS usando módem GSM
        """
        if not self.gsm_serial:
            if not self._init_gsm_modem():
                return {
                    'success': False,
                    'error': 'No se pudo inicializar el módem GSM'
                }
        
        try:
            # Formatear número (remover + y espacios)
            phone = phone_number.replace('+', '').replace(' ', '').replace('-', '')
            
            # Enviar comando AT para enviar SMS
            cmd = f'AT+CMGS="{phone}"\r\n'
            self.gsm_serial.write(cmd.encode())
            time.sleep(0.5)
            
            # Enviar mensaje
            self.gsm_serial.write(message.encode())
            self.gsm_serial.write(b'\x1A')  # Ctrl+Z para enviar
            time.sleep(2)
            
            # Leer respuesta
            response = self.gsm_serial.read(500).decode('utf-8', errors='ignore')
            
            if 'OK' in response or '+CMGS' in response:
                return {
                    'success': True,
                    'method': 'gsm_modem',
                    'to': phone_number,
                    'message': 'SMS enviado exitosamente'
                }
            else:
                return {
                    'success': False,
                    'error': f'Error del módem: {response}',
                    'method': 'gsm_modem'
                }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'gsm_modem'
            }
    
    def _send_sms_android_phone(self, phone_number: str, message: str) -> Dict:
        """
        Envía SMS usando teléfono Android o servicios de SMS
        Método 1 (preferido): SMSMobileAPI - API en la nube (completamente automático, solo saldo local)
        Método 2: MessageBird - Servicio de pago (confiable, sin prefijo)
        Método 3: Sinch SMS - Servicio de pago (confiable, sin prefijo)
        Método 4: SMS Gateway API local - completamente automático
        Método 5 (respaldo): ADB - abre app de SMS (semi-automático)
        """
        # Formatear número (remover + y espacios)
        phone = phone_number.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
        
        # MÉTODO 1: SMSMobileAPI (API en la nube - completamente automático)
        if self.smsmobileapi_key:
            try:
                # URL de la API de SMSMobileAPI
                url = "https://api.smsmobileapi.com/sendsms/"
                
                # Formatear número: remover + y espacios, solo números
                phone_clean = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                
                # Parámetros GET
                params = {
                    'recipients': phone_clean,
                    'message': message,
                    'apikey': self.smsmobileapi_key
                }
                
                # Enviar solicitud
                response = requests.get(url, params=params, timeout=15)
                
                if response.status_code == 200:
                    result_data = response.json()
                    # Verificar respuesta
                    if result_data.get('result', {}).get('error') == 0:
                        return {
                            'success': True,
                            'method': 'smsmobileapi',
                            'to': phone_number,
                            'message': 'SMS enviado exitosamente vía SMSMobileAPI',
                            'gateway_response': result_data
                        }
                    else:
                        # Error en SMSMobileAPI, continuar con otros métodos
                        error_code = result_data.get('result', {}).get('error', 'Error desconocido')
                        error_text = result_data.get('result', {}).get('error-text', '')
                        print(f"⚠ SMSMobileAPI falló (código {error_code}): {error_text}, intentando MessageBird/Sinch...")
                        import sys
                        sys.stdout.flush()  # Forzar que se muestre el mensaje
                else:
                    print(f"⚠ SMSMobileAPI falló (HTTP {response.status_code}): {response.text}, intentando MessageBird/Sinch...")
                    import sys
                    sys.stdout.flush()  # Forzar que se muestre el mensaje
            except Exception as e:
                print(f"⚠ Error con SMSMobileAPI: {e}, intentando otros métodos...")
                import traceback
                print(traceback.format_exc())
        
        # MÉTODO 2: MessageBird (servicio de pago - confiable, sin prefijo)
        if self.messagebird_api_key:
            # Log para diagnóstico (se verá en app.py)
            api_key_preview = self.messagebird_api_key[:20] if len(self.messagebird_api_key) > 20 else self.messagebird_api_key
            print(f"🔄 Intentando MessageBird:")
            print(f"   - API Key (primeros 20): {api_key_preview}...")
            print(f"   - API Key (longitud): {len(self.messagebird_api_key)} caracteres")
            print(f"   - API Key (últimos 10): ...{self.messagebird_api_key[-10:]}")
            print(f"   - API Key (valor completo): '{self.messagebird_api_key}'")
            import sys
            sys.stdout.flush()
            try:
                # Limpiar API Key (eliminar espacios al inicio/final)
                api_key_clean = self.messagebird_api_key.strip()
                print(f"   - API Key después de strip: '{api_key_clean}' (longitud: {len(api_key_clean)})")
                sys.stdout.flush()
                
                # URL de la API de MessageBird
                url = "https://rest.messagebird.com/messages"
                
                # Formatear número: MessageBird requiere formato internacional con +
                phone_clean = phone_number if phone_number.startswith('+') else f'+{phone_number}'
                
                # Headers
                headers = {
                    'Authorization': f'AccessKey {api_key_clean}',
                    'Content-Type': 'application/json'
                }
                
                # Body
                data = {
                    'originator': self.messagebird_originator,
                    'recipients': [phone_clean],
                    'body': message
                }
                
                print(f"🔄 Enviando SMS vía MessageBird:")
                print(f"   - URL: {url}")
                print(f"   - Destino: {phone_clean}")
                print(f"   - Originator: {self.messagebird_originator}")
                print(f"   - API Key (primeros 20 chars): {api_key_clean[:20]}...")
                print(f"   - API Key (longitud): {len(api_key_clean)} caracteres")
                sys.stdout.flush()
                
                # Enviar solicitud
                response = requests.post(url, json=data, headers=headers, timeout=15)
                
                print(f"🔄 Respuesta de MessageBird: Status={response.status_code}, Body={response.text[:200]}")
                sys.stdout.flush()
                
                if response.status_code == 201:  # 201 Created for MessageBird
                    result_data = response.json()
                    print(f"✅ MessageBird exitoso!")
                    sys.stdout.flush()
                    return {
                        'success': True,
                        'method': 'messagebird',
                        'to': phone_number,
                        'message': 'SMS enviado exitosamente vía MessageBird',
                        'gateway_response': result_data
                    }
                else:
                    # Error en MessageBird, continuar con otros métodos
                    error_text = response.text
                    try:
                        error_data = response.json()
                        error_msg = error_data.get('errors', [{}])[0].get('description', error_text)
                        error_code = error_data.get('errors', [{}])[0].get('code', 'unknown')
                        print(f"⚠ MessageBird falló (HTTP {response.status_code}, código: {error_code}): {error_msg}")
                    except:
                        error_msg = error_text
                        print(f"⚠ MessageBird falló (HTTP {response.status_code}): {error_msg}")
                    print(f"⚠ Respuesta completa de MessageBird: {response.text}")
                    print(f"⚠ Intentando Sinch...")
                    sys.stdout.flush()
            except Exception as e:
                print(f"⚠ Error con MessageBird: {e}, intentando otros métodos...")
                import traceback
                print(traceback.format_exc())
                sys.stdout.flush()
        else:
            print(f"⚠ MessageBird no configurado (MESSAGEBIRD_API_KEY vacía)")
            import sys
            sys.stdout.flush()
        
        # MÉTODO 3: Sinch SMS (servicio de pago - confiable)
        if self.sinch_service_plan_id and self.sinch_api_token:
            try:
                # URL completa de Sinch API
                url = f"{self.sinch_api_url}/{self.sinch_service_plan_id}/batches"
                
                # Formatear número: remover + y espacios, solo números
                phone_clean = phone.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                
                # Headers
                headers = {
                    'Authorization': f'Bearer {self.sinch_api_token}',
                    'Content-Type': 'application/json'
                }
                
                # Body
                data = {
                    'from': self.sinch_from_number,
                    'to': [phone_clean],
                    'body': message
                }
                
                # Enviar solicitud
                response = requests.post(url, json=data, headers=headers, timeout=15)
                
                if response.status_code == 200 or response.status_code == 201:
                    result_data = response.json()
                    return {
                        'success': True,
                        'method': 'sinch',
                        'to': phone_number,
                        'message': 'SMS enviado exitosamente vía Sinch',
                        'gateway_response': result_data
                    }
                else:
                    # Error en Sinch, continuar con otros métodos
                    error_text = response.text
                    print(f"⚠ Sinch falló (HTTP {response.status_code}): {error_text}, intentando otros métodos...")
            except Exception as e:
                print(f"⚠ Error con Sinch: {e}, intentando otros métodos...")
                import traceback
                print(traceback.format_exc())
        
        # MÉTODO 3: SMS Gateway API local (completamente automático)
        # Soporta Traccar SMS Gateway y otros gateways locales
        # MÉTODO 4: Android SMS Gateway App (SMS Gateway de Mattia A. u otras apps similares)
        if self.android_gateway_url:
            try:
                print(f"🔄 Intentando Android SMS Gateway: {self.android_gateway_url}")
                import sys
                sys.stdout.flush()
                
                # Formatear número: remover + y espacios para la app
                phone_clean = phone_number.replace('+', '').replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                
                # Intentar formato Traccar SMS Gateway primero
                if 'traccar' in self.android_gateway_url.lower():
                    # Formato Traccar SMS Gateway
                    url = f"{self.android_gateway_url.rstrip('/')}/api/sms/send"
                    headers = {
                        'Content-Type': 'application/json'
                    }
                    if self.android_gateway_token:
                        headers['X-Traccar-Token'] = self.android_gateway_token
                    
                    data = {
                        'phone': phone_clean,
                        'message': message
                    }
                    
                    print(f"   - Formato: Traccar SMS Gateway")
                    print(f"   - URL: {url}")
                    print(f"   - Destino: {phone_clean}")
                    sys.stdout.flush()
                    
                    response = requests.post(url, json=data, headers=headers, timeout=15)
                else:
                    # SIMPLE SMS GATEWAY - Formato específico y optimizado
                    # Simple SMS Gateway usa: POST /send-sms con JSON {"phone": "...", "message": "..."}
                    base_url = self.android_gateway_url.rstrip('/')
                    
                    # Construir URL específica de Simple SMS Gateway
                    if '/send-sms' in base_url:
                        simple_sms_url = base_url
                    else:
                        simple_sms_url = f"{base_url}/send-sms"
                    
                    # Formato específico de Simple SMS Gateway
                    simple_sms_data = {
                        'phone': phone_clean,
                        'message': message
                    }
                    
                    # Simple SMS Gateway NO requiere token
                    print(f"   - Formato: Simple SMS Gateway (específico)")
                    print(f"   - URL: {simple_sms_url}")
                    print(f"   - Destino: {phone_clean}")
                    print(f"   - Método: POST con JSON")
                    sys.stdout.flush()
                    
                    # Intentar Simple SMS Gateway primero (formato específico)
                    headers = {'Content-Type': 'application/json'}
                    print(f"   - Probando Simple SMS Gateway: POST {simple_sms_url}")
                    sys.stdout.flush()
                    
                    try:
                        response = requests.post(simple_sms_url, json=simple_sms_data, headers=headers, timeout=15)
                        
                        if response.status_code == 200:
                            print(f"   - ✅ Éxito con Simple SMS Gateway!")
                            sys.stdout.flush()
                            # Éxito, continuar con el procesamiento de respuesta
                        elif response.status_code in [404, 405]:
                            # Si falla, intentar otros formatos como respaldo
                            print(f"   - ⚠ Simple SMS Gateway falló (HTTP {response.status_code}), intentando otros formatos...")
                            sys.stdout.flush()
                            raise Exception(f"Simple SMS Gateway falló con HTTP {response.status_code}")
                        else:
                            print(f"   - ⚠ Simple SMS Gateway falló (HTTP {response.status_code}): {response.text[:200]}")
                            sys.stdout.flush()
                            raise Exception(f"Simple SMS Gateway falló con HTTP {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        # Si Simple SMS Gateway falla por error de conexión, intentar otros formatos como respaldo
                        print(f"   - ⚠ Error de conexión con Simple SMS Gateway: {e}, intentando otros formatos...")
                        sys.stdout.flush()
                        
                        # Formato genérico para otras apps SMS Gateway (respaldo)
                        param_variations = [
                            {'phone': phone_clean, 'message': message},
                            {'number': phone_clean, 'message': message},
                            {'to': phone_clean, 'message': message},
                        ]
                        
                        url_variations = [
                            f"{base_url}/send",
                            f"{base_url}/api/send",
                            f"{base_url}/sms/send",
                        ]
                        
                        success = False
                        last_error = str(e)
                        
                        for url in url_variations:
                            if success:
                                break
                                
                            for params in param_variations:
                                if success:
                                    break
                                
                                try:
                                    headers = {'Content-Type': 'application/json'}
                                    print(f"   - Probando respaldo: POST {url} con params={list(params.keys())}")
                                    sys.stdout.flush()
                                    
                                    response = requests.post(url, json=params, headers=headers, timeout=15)
                                    
                                    if response.status_code == 200:
                                        print(f"   - ✅ Éxito con formato respaldo: {url}")
                                        success = True
                                        break
                                except Exception as backup_error:
                                    last_error = str(backup_error)
                                    continue
                        
                        if not success:
                            raise Exception(f"No se pudo conectar con Simple SMS Gateway ni otros formatos. Último error: {last_error}")
                    
                    sys.stdout.flush()
                
                print(f"   - Respuesta HTTP: {response.status_code}")
                print(f"   - Respuesta: {response.text[:200]}")
                sys.stdout.flush()
                
                if response.status_code == 200:
                    try:
                        result_data = response.json() if response.text else {}
                    except:
                        result_data = {'response': response.text}
                    
                    print(f"✅ Android SMS Gateway exitoso!")
                    sys.stdout.flush()
                    return {
                        'success': True,
                        'method': 'android_phone_gateway',
                        'to': phone_number,
                        'message': 'SMS enviado exitosamente vía Android SMS Gateway',
                        'gateway_response': result_data
                    }
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    print(f"⚠ Android SMS Gateway falló: {error_msg}")
                    sys.stdout.flush()
            except Exception as e:
                print(f"⚠ Error con Android SMS Gateway: {e}, intentando método ADB...")
                import traceback
                print(traceback.format_exc())
                sys.stdout.flush()
        
        # MÉTODO 3: ADB (semi-automático - abre app de SMS)
        try:
            # Escapar comillas en el mensaje para el shell
            escaped_message = message.replace('"', '\\"').replace("'", "\\'")
            
            # Comando para abrir SMS con número y mensaje
            intent_cmd = [
                'adb', 'shell', 'am', 'start',
                '-a', 'android.intent.action.SENDTO',
                '-d', f'sms:{phone}',
                '--es', 'sms_body', escaped_message
            ]
            
            result = subprocess.run(intent_cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {
                    'success': True,
                    'method': 'android_phone_adb',
                    'to': phone_number,
                    'message': 'SMS listo para enviar en el teléfono (toca enviar manualmente)',
                    'note': 'Para envío automático, configura ANDROID_SMS_GATEWAY_URL'
                }
            else:
                return {
                    'success': False,
                    'error': f'No se pudo abrir SMS. Error: {result.stderr}',
                    'method': 'android_phone',
                    'suggestion': 'Configura ANDROID_SMS_GATEWAY_URL para envío automático o verifica ADB: adb devices'
                }
        except FileNotFoundError:
            return {
                'success': False,
                'error': 'ADB no está instalado. Descarga desde: https://developer.android.com/studio/releases/platform-tools',
                'method': 'android_phone',
                'suggestion': 'O configura ANDROID_SMS_GATEWAY_URL para envío automático sin ADB'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'method': 'android_phone'
            }
    
    def send_sms(self, phone_number: str, message: str) -> Dict:
        """
        Envía un SMS usando el método configurado
        """
        if self.method == 'gsm_modem':
            return self._send_sms_gsm_modem(phone_number, message)
        elif self.method == 'android_phone':
            return self._send_sms_android_phone(phone_number, message)
        else:
            return {
                'success': False,
                'error': f'Método {self.method} no disponible'
            }
    
    def is_available(self) -> bool:
        """
        Verifica si el método de envío está disponible
        """
        if self.method == 'gsm_modem':
            return self.gsm_port is not None
        elif self.method == 'android_phone':
            return self.android_available
        else:
            return False


# Función de conveniencia para usar desde otros módulos
def create_sms_sender(method='auto') -> Optional[FreeSMSSender]:
    """
    Crea un sender de SMS gratis
    """
    sender = FreeSMSSender(method=method)
    if sender.is_available():
        return sender
    return None





