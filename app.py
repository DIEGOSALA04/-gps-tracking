from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

# Importar el procesador de SMS
try:
    from sms_gps_handler import SMSGPSHandler
except ImportError:
    SMSGPSHandler = None
    print("Advertencia: sms_gps_handler no disponible")

# Importar Twilio para enviar SMS
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    print("Advertencia: Twilio no está disponible. Instala con: pip install twilio")

# Importar servicio de actualización automática
try:
    from auto_update_service import AutoUpdateService
except ImportError:
    AutoUpdateService = None
    print("Advertencia: auto_update_service no disponible")

load_dotenv()

app = Flask(__name__)
CORS(app)

# Configuración de base de datos
# En Render, usar disco persistente si está disponible, sino usar directorio temporal
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///gps_devices.db')
# Si estamos en Render y no hay DATABASE_URL configurado, usar directorio persistente
if 'RENDER' in os.environ and not os.getenv('DATABASE_URL'):
    # En Render, intentar usar /tmp que es persistente entre reinicios
    db_path = '/tmp/gps_devices.db'
    DATABASE_URL = f'sqlite:///{db_path}'
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# Modelo de base de datos
class GPSDevice(Base):
    __tablename__ = 'gps_devices'
    
    id = Column(Integer, primary_key=True)
    device_id = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(255))
    # Campos simplificados para vehículos eléctricos de juguetes
    placa_gps = Column(String(50), default='')  # Número de placa GPS o SIM
    color = Column(String(50), default='')  # Color del vehículo
    # Campos antiguos (mantener para compatibilidad)
    tipo = Column(String(50), default=None)
    marca = Column(String(50), default=None)
    modelo = Column(String(100), default=None)
    # Ubicación GPS
    latitude = Column(Float, default=7.1254)  # Bucaramanga por defecto
    longitude = Column(Float, default=-73.1198)
    last_update = Column(DateTime, default=datetime.utcnow)
    # Estado del dispositivo
    status = Column(String(20), default='active')  # active, inactive, deleted
    # Campos de alquiler
    is_rented = Column(Boolean, default=False)
    rental_start = Column(DateTime, default=None)
    rental_end = Column(DateTime, default=None)
    rental_duration_hours = Column(Integer, default=None)
    
    def to_dict(self):
        return {
            'id': self.id,
            'device_id': self.device_id,
            'name': self.name,
            'description': self.description,
            'placa_gps': self.placa_gps or '',
            'color': self.color or '',
            'tipo': self.tipo,
            'marca': self.marca,
            'modelo': self.modelo,
            'latitude': self.latitude,
            'longitude': self.longitude,
            'last_update': self.last_update.isoformat() if self.last_update else None,
            'status': self.status,
            'is_rented': bool(self.is_rented),
            'rental_start': self.rental_start.isoformat() if self.rental_start else None,
            'rental_end': self.rental_end.isoformat() if self.rental_end else None,
            'rental_duration_hours': self.rental_duration_hours
        }

# Crear tablas
Base.metadata.create_all(engine)

# Migración de base de datos
def migrate_database():
    """Agrega columnas nuevas si no existen"""
    try:
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('gps_devices')]
        
        with engine.connect() as conn:
            if 'placa_gps' not in columns:
                conn.execute(text("ALTER TABLE gps_devices ADD COLUMN placa_gps VARCHAR(50) DEFAULT ''"))
                conn.commit()
            
            if 'color' not in columns:
                conn.execute(text("ALTER TABLE gps_devices ADD COLUMN color VARCHAR(50) DEFAULT ''"))
                conn.commit()
            
            if 'is_rented' not in columns:
                conn.execute(text("ALTER TABLE gps_devices ADD COLUMN is_rented BOOLEAN DEFAULT 0"))
                conn.commit()
            
            if 'rental_start' not in columns:
                conn.execute(text("ALTER TABLE gps_devices ADD COLUMN rental_start DATETIME"))
                conn.commit()
            
            if 'rental_end' not in columns:
                conn.execute(text("ALTER TABLE gps_devices ADD COLUMN rental_end DATETIME"))
                conn.commit()
            
            if 'rental_duration_hours' not in columns:
                conn.execute(text("ALTER TABLE gps_devices ADD COLUMN rental_duration_hours INTEGER"))
                conn.commit()
    except Exception as e:
        print(f"Error en migracion: {e}")

# Ejecutar migración
migrate_database()

# Inicializar servicio de actualización automática
auto_update_service = None
if AutoUpdateService:
    try:
        auto_update_service = AutoUpdateService(
            session_factory=Session,
            gps_device_model=GPSDevice,
            interval_seconds=10
        )
    except Exception as e:
        print(f"Error inicializando auto_update_service: {e}")

# Rutas
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

# API - Obtener todos los dispositivos
@app.route('/api/devices', methods=['GET'])
def get_devices():
    session = Session()
    try:
        devices = session.query(GPSDevice).filter(
            GPSDevice.status != 'deleted'
        ).all()
        
        devices_list = [device.to_dict() for device in devices]
        return jsonify(devices_list)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# API - Agregar dispositivo
@app.route('/api/devices', methods=['POST'])
def add_device():
    session = Session()
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        if not data.get('name'):
            return jsonify({'error': 'El nombre es requerido'}), 400
        
        # Crear nuevo dispositivo
        device = GPSDevice(
            device_id=data.get('device_id', f"DEV_{datetime.now().strftime('%Y%m%d%H%M%S')}"),
            name=data.get('name'),
            description=data.get('description', ''),
            placa_gps=data.get('placa_gps', ''),
            color=data.get('color', ''),
            tipo=data.get('tipo'),
            marca=data.get('marca'),
            modelo=data.get('modelo'),
            latitude=data.get('latitude', 7.1254),
            longitude=data.get('longitude', -73.1198),
            status='active'
        )
        
        session.add(device)
        session.commit()
        
        return jsonify({
            'message': 'Dispositivo agregado exitosamente',
            'device': device.to_dict()
        }), 201
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# API - Actualizar dispositivo
@app.route('/api/devices/<int:device_id>', methods=['PUT'])
def update_device(device_id):
    session = Session()
    try:
        device = session.query(GPSDevice).filter_by(id=device_id).first()
        if not device:
            return jsonify({'error': 'Dispositivo no encontrado'}), 404
        
        data = request.get_json()
        
        if 'name' in data:
            device.name = data['name']
        if 'description' in data:
            device.description = data['description']
        if 'placa_gps' in data:
            device.placa_gps = data['placa_gps']
        if 'color' in data:
            device.color = data['color']
        if 'latitude' in data:
            device.latitude = data['latitude']
        if 'longitude' in data:
            device.longitude = data['longitude']
        
        session.commit()
        
        return jsonify({
            'message': 'Dispositivo actualizado exitosamente',
            'device': device.to_dict()
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# API - Eliminar dispositivo
@app.route('/api/devices/<int:device_id>', methods=['DELETE'])
def delete_device(device_id):
    session = Session()
    try:
        device = session.query(GPSDevice).filter_by(id=device_id).first()
        if not device:
            return jsonify({'error': 'Dispositivo no encontrado'}), 404
        
        device.status = 'deleted'
        session.commit()
        
        return jsonify({'message': 'Dispositivo eliminado exitosamente'})
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# API - Iniciar alquiler
@app.route('/api/devices/<int:device_id>/rent', methods=['POST'])
def start_rental(device_id):
    session = Session()
    try:
        device = session.query(GPSDevice).filter_by(id=device_id).first()
        if not device:
            return jsonify({'error': 'Dispositivo no encontrado'}), 404
        
        data = request.get_json()
        duration_hours = int(data.get('duration_hours', 1))
        
        device.is_rented = True
        device.rental_start = datetime.utcnow()
        device.rental_end = datetime.utcnow() + timedelta(hours=duration_hours)
        device.rental_duration_hours = duration_hours
        
        session.commit()
        
        return jsonify({
            'message': 'Alquiler iniciado exitosamente',
            'device': device.to_dict()
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# API - Finalizar alquiler
@app.route('/api/devices/<int:device_id>/end-rental', methods=['POST'])
def end_rental(device_id):
    session = Session()
    try:
        device = session.query(GPSDevice).filter_by(id=device_id).first()
        if not device:
            return jsonify({'error': 'Dispositivo no encontrado'}), 404
        
        device.is_rented = False
        device.rental_start = None
        device.rental_end = None
        device.rental_duration_hours = None
        
        session.commit()
        
        return jsonify({
            'message': 'Alquiler finalizado exitosamente',
            'device': device.to_dict()
        })
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()

# API - Recibir SMS de Twilio o formato directo
@app.route('/api/sms/receive', methods=['POST'])
def receive_sms():
    try:
        # Formato Twilio
        if 'From' in request.form:
            phone_number = request.form.get('From', '').replace('whatsapp:', '')
            sms_text = request.form.get('Body', '')
        # Formato directo JSON
        elif request.is_json:
            data = request.get_json()
            phone_number = data.get('phone_number', '') or data.get('From', '')
            sms_text = data.get('sms_text', '') or data.get('Body', '')
        else:
            return jsonify({'error': 'Formato de solicitud no válido'}), 400
        
        if not SMSGPSHandler:
            return jsonify({'error': 'SMSGPSHandler no disponible'}), 500
        
        # Procesar SMS
        result = SMSGPSHandler.process_sms(sms_text, phone_number)
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API - Solicitar ubicación (enviar SMS)
@app.route('/api/devices/<int:device_id>/request-location', methods=['POST'])
def request_location(device_id):
    session = Session()
    try:
        device = session.query(GPSDevice).filter_by(id=device_id).first()
        if not device:
            return jsonify({'error': 'Dispositivo no encontrado'}), 404
        
        if not device.placa_gps:
            return jsonify({'error': 'El dispositivo no tiene número de SIM configurado'}), 400
        
        if not TWILIO_AVAILABLE:
            return jsonify({'error': 'Twilio no está configurado'}), 500
        
        # Configurar Twilio
        account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        twilio_phone = os.getenv('TWILIO_PHONE_NUMBER')
        
        if not account_sid or not auth_token or not twilio_phone:
            return jsonify({'error': 'Credenciales de Twilio no configuradas'}), 500
        
        client = Client(account_sid, auth_token)
        
        # Formatear número de teléfono
        to_number = device.placa_gps.strip()
        if not to_number.startswith('+'):
            to_number = to_number.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
            if to_number.startswith('0'):
                to_number = to_number[1:]
            if not to_number.startswith('57'):
                to_number = f'+57{to_number}'
            else:
                to_number = f'+{to_number}'
        
        # Enviar SMS
        data = request.get_json()
        message = data.get('message', 'LOC') if data else 'LOC'
        
        try:
            message_obj = client.messages.create(
                body=message,
                from_=twilio_phone,
                to=to_number
            )
            
            return jsonify({
                'message': f'SMS enviado exitosamente a {device.name}',
                'message_sid': message_obj.sid,
                'to': to_number,
                'status': 'success'
            }), 200
        except Exception as e:
            return jsonify({
                'error': f'Error al enviar SMS: {str(e)}',
                'status': 'error'
            }), 500
            
    except Exception as e:
        session.rollback()
        return jsonify({'error': str(e), 'status': 'error'}), 500
    finally:
        session.close()

# API - Actualización automática
@app.route('/api/auto-update/start', methods=['POST'])
def start_auto_update():
    """Inicia el servicio de actualización automática"""
    if not auto_update_service:
        return jsonify({'status': 'error', 'message': 'AutoUpdateService no disponible'}), 500
    try:
        result = auto_update_service.start()
        return jsonify(result), 200 if result['status'] != 'error' else 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/auto-update/stop', methods=['POST'])
def stop_auto_update():
    """Detiene el servicio de actualización automática"""
    if not auto_update_service:
        return jsonify({'status': 'error', 'message': 'AutoUpdateService no disponible'}), 500
    try:
        result = auto_update_service.stop()
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/auto-update/status', methods=['GET'])
def get_auto_update_status():
    """Obtiene el estado del servicio de actualización automática"""
    if not auto_update_service:
        return jsonify({
            'is_running': False,
            'twilio_configured': False,
            'error': 'AutoUpdateService no disponible'
        }), 200
    try:
        status = auto_update_service.get_status()
        return jsonify(status), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/auto-update/set-interval', methods=['POST'])
def set_auto_update_interval():
    """Cambia el intervalo de actualización automática"""
    if not auto_update_service:
        return jsonify({'status': 'error', 'message': 'AutoUpdateService no disponible'}), 500
    try:
        data = request.get_json()
        seconds = int(data.get('seconds', 10))
        
        result = auto_update_service.set_interval(seconds)
        return jsonify(result), 200 if result['status'] != 'error' else 400
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

