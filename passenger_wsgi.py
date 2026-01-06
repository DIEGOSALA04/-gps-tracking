"""
Archivo WSGI para ejecutar Flask con Passenger (Python App en cPanel)
Este archivo permite que Flask se ejecute automáticamente sin necesidad de SSH
"""
import sys
import os

# Agregar el directorio actual al path de Python
sys.path.insert(0, os.path.dirname(__file__))

# Cargar variables de entorno desde .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Si dotenv no está disponible, intentar cargar variables manualmente
    pass

# Importar la aplicación Flask
from app import app as application

# Passenger espera una variable llamada 'application'
# Esta es la aplicación WSGI que se ejecutará

if __name__ == "__main__":
    # Si se ejecuta directamente, iniciar el servidor de desarrollo
    application.run(host='0.0.0.0', port=5000, debug=False)

