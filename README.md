# Sistema de Gestión GPS - Alquiler de Vehículos Eléctricos

Aplicación web para gestionar vehículos GPS y visualizar sus ubicaciones en tiempo real.

## Características

- ✅ Agregar vehículos GPS
- ✅ Visualizar ubicaciones en mapa interactivo
- ✅ Sistema de alquiler con tiempo de duración
- ✅ Recepción de SMS de placas GPS
- ✅ Envío de SMS para solicitar ubicación
- ✅ Actualización automática de ubicaciones
- ✅ Interfaz responsive (móvil y PC)
- ✅ PWA (Progressive Web App)

## Instalación

```bash
pip install -r requirements.txt
```

## Configuración

### Variables de Entorno

Configura estas variables de entorno (en Render.com o en archivo `.env`):

```env
TWILIO_ACCOUNT_SID=tu_account_sid
TWILIO_AUTH_TOKEN=tu_auth_token
TWILIO_PHONE_NUMBER=+15551234567
DATABASE_URL=sqlite:///gps_devices.db
```

### Ejecutar aplicación

```bash
python app.py
```

La aplicación estará disponible en: `http://localhost:5000`

## Estructura del Proyecto

```
.
├── app.py                      # Aplicación Flask principal
├── sms_gps_handler.py          # Procesador de SMS GPS
├── auto_update_service.py      # Servicio de actualización automática
├── passenger_wsgi.py           # Configuración WSGI para servidores
├── requirements.txt            # Dependencias Python
├── README.md                   # Este archivo
├── static/                     # Archivos estáticos
│   ├── script.js              # JavaScript frontend
│   ├── style.css              # Estilos CSS
│   ├── manifest.json          # Configuración PWA
│   └── ...
└── templates/                  # Plantillas HTML
    └── index.html             # Página principal
```

## Despliegue en Render.com

1. Conecta este repositorio a Render.com
2. Crea un "Web Service"
3. Configura:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
4. Agrega las variables de entorno de Twilio
5. ¡Listo!

## Configuración de Twilio

1. Ve a tu número en Twilio Console
2. Configura el webhook para recibir SMS:
   - URL: `https://TU-URL.onrender.com/api/sms/receive`
   - Método: POST

## Licencia

Este proyecto es privado.
