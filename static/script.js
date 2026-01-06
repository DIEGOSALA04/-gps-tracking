// Inicializar el mapa
let map;
let markers = {};
let selectedDeviceId = null;
let realTimeUpdateInterval = null;
let allDevices = [];

let currentRentalDeviceId = null;

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar mapa primero y esperar a que esté listo
    initializeMap();
    // Esperar a que el mapa esté completamente inicializado antes de cargar dispositivos
    setTimeout(() => {
        loadDevices();
    }, 500);
    registerServiceWorker();
    
    // Event listeners
    document.getElementById('deviceForm').addEventListener('submit', handleAddDevice);
    document.getElementById('rentalForm').addEventListener('submit', handleStartRental);
    document.getElementById('refreshBtn').addEventListener('click', loadDevices);
    
    // Menú móvil
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const sidebar = document.getElementById('sidebar');
    const mobileOverlay = document.getElementById('mobileOverlay');
    
    if (mobileMenuBtn) {
        mobileMenuBtn.addEventListener('click', toggleMobileMenu);
    }
    
    if (mobileOverlay) {
        mobileOverlay.addEventListener('click', closeMobileMenu);
    }
    
    // Actualizar ubicaciones cada 30 segundos (solo si no hay dispositivo seleccionado)
    setInterval(() => {
        if (!selectedDeviceId) {
            loadDevices();
        }
    }, 30000);
    
    // Verificar alquileres expirados cada minuto (DESACTIVADO)
    // setInterval(checkExpiredRentals, 60000);
    // checkExpiredRentals(); // Verificar inmediatamente
});

function toggleMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const mobileOverlay = document.getElementById('mobileOverlay');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    
    if (sidebar && mobileOverlay && mobileMenuBtn) {
        sidebar.classList.toggle('mobile-open');
        mobileOverlay.classList.toggle('active');
        mobileMenuBtn.classList.toggle('active');
        document.body.style.overflow = sidebar.classList.contains('mobile-open') ? 'hidden' : '';
    }
}

function closeMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const mobileOverlay = document.getElementById('mobileOverlay');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    
    if (sidebar && mobileOverlay && mobileMenuBtn) {
        sidebar.classList.remove('mobile-open');
        mobileOverlay.classList.remove('active');
        mobileMenuBtn.classList.remove('active');
        document.body.style.overflow = '';
    }
}

// Registrar Service Worker para PWA
function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/sw.js')
            .then((registration) => {
                console.log('Service Worker registrado:', registration);
            })
            .catch((error) => {
                console.log('Error al registrar Service Worker:', error);
            });
    }
}

function initializeMap() {
    // Verificar que el contenedor del mapa exista
    const mapContainer = document.getElementById('map');
    if (!mapContainer) {
        console.error('Contenedor del mapa no encontrado');
        return;
    }
    
    // Inicializar mapa centrado en Bucaramanga, Colombia
    map = L.map('map').setView([7.1254, -73.1198], 13);
    
    // Agregar capa de OpenStreetMap
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);
    
    // Esperar a que el mapa esté completamente listo
    map.whenReady(function() {
        console.log('Mapa inicializado correctamente');
    });
}

async function loadDevices() {
    try {
        const response = await fetch('/api/devices');
        const devices = await response.json();
        
        console.log('Dispositivos cargados:', devices.length);
        console.log('Vehículos alquilados:', devices.filter(d => d.is_rented).length);
        
        displayDevices(devices);
        updateMap(devices);
        updateStats(devices);
    } catch (error) {
        console.error('Error al cargar dispositivos:', error);
        showError('Error al cargar los dispositivos');
    }
}

function updateStats(devices) {
    const totalDevices = devices.length;
    const activeDevices = devices.filter(d => d.latitude && d.longitude).length;
    
    // Filtrar vehículos alquilados correctamente (manejar boolean y números)
    const rentedDevices = devices.filter(d => {
        return d.is_rented === true || d.is_rented === 1 || d.is_rented === 'true' || d.is_rented === '1';
    }).length;
    
    const availableDevices = totalDevices - rentedDevices;
    
    console.log('=== UPDATE STATS ===');
    console.log('Total dispositivos:', totalDevices);
    console.log('Vehículos alquilados:', rentedDevices);
    console.log('Vehículos disponibles:', availableDevices);
    
    const totalDevicesEl = document.getElementById('totalDevices');
    const activeDevicesEl = document.getElementById('activeDevices');
    const rentedCountBadgeEl = document.getElementById('rentedCountBadge');
    const availableCountBadgeEl = document.getElementById('availableCountBadge');
    
    if (totalDevicesEl) totalDevicesEl.textContent = totalDevices;
    if (activeDevicesEl) activeDevicesEl.textContent = activeDevices;
    if (rentedCountBadgeEl) rentedCountBadgeEl.textContent = rentedDevices;
    if (availableCountBadgeEl) availableCountBadgeEl.textContent = availableDevices;
    
    // Mostrar/ocultar sección de alquilados
    const rentedCard = document.getElementById('rentedCard');
    if (rentedCard) {
        if (rentedDevices > 0) {
            rentedCard.style.setProperty('display', 'flex', 'important');
        } else {
            rentedCard.style.setProperty('display', 'none', 'important');
        }
    }
}

function displayDevices(devices) {
    allDevices = devices;
    
    // Separar vehículos alquilados y disponibles (manejar diferentes formatos de boolean)
    const rentedDevices = devices.filter(d => {
        return d.is_rented === true || d.is_rented === 1 || d.is_rented === 'true' || d.is_rented === '1';
    });
    
    const availableDevices = devices.filter(d => {
        return !d.is_rented || d.is_rented === false || d.is_rented === 0 || d.is_rented === 'false' || d.is_rented === '0' || d.is_rented === null;
    });
    
    console.log('=== DISPLAY DEVICES ===');
    console.log('Total dispositivos:', devices.length);
    console.log('Vehículos alquilados encontrados:', rentedDevices.length);
    console.log('Vehículos disponibles:', availableDevices.length);
    
    if (rentedDevices.length > 0) {
        console.log('Vehículos alquilados:', rentedDevices.map(d => ({ id: d.id, name: d.name, is_rented: d.is_rented })));
    }
    
    // Mostrar vehículos alquilados PRIMERO
    displayRentedDevices(rentedDevices);
    
    // Mostrar vehículos disponibles DESPUÉS
    displayAvailableDevices(availableDevices);
}

function displayRentedDevices(devices) {
    const rentedList = document.getElementById('rentedDevicesList');
    const rentedCard = document.getElementById('rentedCard');
    
    console.log('displayRentedDevices llamado con', devices.length, 'vehículos');
    
    if (!rentedList) {
        console.error('No se encontró rentedDevicesList');
        return;
    }
    
    if (!rentedCard) {
        console.error('No se encontró rentedCard');
        return;
    }
    
    if (devices.length === 0) {
        rentedCard.style.setProperty('display', 'none', 'important');
        rentedList.innerHTML = '';
        console.log('No hay vehículos alquilados, ocultando sección');
        return;
    }
    
    // Asegurar que la sección esté visible
    console.log('Mostrando sección de alquilados con', devices.length, 'vehículos');
    
    // Forzar que se muestre - remover cualquier estilo que lo oculte
    rentedCard.style.removeProperty('display');
    rentedCard.style.setProperty('display', 'flex', 'important');
    rentedCard.style.setProperty('visibility', 'visible', 'important');
    rentedCard.style.setProperty('opacity', '1', 'important');
    
    // Asegurar que tenga altura
    rentedCard.style.setProperty('min-height', '200px', 'important');
    
    // Hacer scroll hacia la sección después de un pequeño delay
    setTimeout(() => {
        rentedCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
    
    rentedList.innerHTML = devices.map(device => {
        const isSelected = selectedDeviceId === device.id;
        const rentalTimeRemaining = device.rental_end ? getTimeRemaining(device.rental_end) : null;
        const hasLocation = device.latitude && device.longitude;
        const isExpired = device.rental_end && new Date(device.rental_end) < new Date();
        
        return `
        <div class="device-item rented ${isSelected ? 'selected' : ''} ${hasLocation ? 'has-location' : 'no-location'} ${isExpired ? 'expired' : ''}" 
             data-device-id="${device.id}" 
             onclick="selectDevice(${device.id}); closeMobileMenu();">
            <div class="device-item-header">
                <div class="device-item-info">
                    <h3>
                        <span class="device-item-icon">⏰</span>
                        ${device.name}
                        ${device.color ? `<span class="device-color">${device.color}</span>` : ''}
                    </h3>
                </div>
                ${isSelected ? `<span class="tracking-badge-small">🟢</span>` : ''}
            </div>
            
            <div class="rental-info-box">
                <div class="rental-time-display">
                    <span class="rental-label">Tiempo Restante:</span>
                    <span class="rental-time-value ${isExpired ? 'expired' : ''}">${rentalTimeRemaining || 'Calculando...'}</span>
                </div>
                ${device.rental_end ? `
                    <div class="rental-detail">
                        <span class="rental-detail-label">Termina:</span>
                        <span class="rental-detail-value">${formatDate(device.rental_end)}</span>
                    </div>
                ` : ''}
            </div>
            
            <div class="device-item-body">
                ${device.placa_gps ? `<div class="device-detail"><span class="detail-label">Placa:</span><span class="detail-value">${device.placa_gps}</span></div>` : ''}
                ${hasLocation ? 
                    `<div class="device-detail">
                        <span class="detail-label">📍 Ubicación:</span>
                        <span class="detail-value location-value">${device.latitude.toFixed(4)}, ${device.longitude.toFixed(4)}</span>
                    </div>` :
                    `<div class="device-detail"><span class="detail-label">Estado:</span><span class="detail-value no-location-text">Sin ubicación</span></div>`
                }
            </div>
            
            <div class="device-actions" onclick="event.stopPropagation()">
                ${hasLocation && !isSelected ? 
                    `<button class="btn-action btn-view" onclick="selectDevice(${device.id}); closeMobileMenu();">
                        <span>📍</span> Ver
                    </button>` : ''
                }
                ${isSelected ? 
                    `<button class="btn-action btn-stop" onclick="stopTracking(); closeMobileMenu();">
                        <span>⏹️</span> Detener
                    </button>` : ''
                }
                <button class="btn-action btn-end" onclick="endRental(${device.id})">
                    <span>✅</span> Finalizar
                </button>
                <button class="btn-action btn-delete" onclick="deleteDevice(${device.id})">
                    <span>🗑️</span> Eliminar
                </button>
            </div>
        </div>
    `}).join('');
}

function displayAvailableDevices(devices) {
    const devicesList = document.getElementById('devicesList');
    
    if (devices.length === 0) {
        devicesList.innerHTML = '<div class="empty-state">No hay vehículos disponibles</div>';
        return;
    }
    
    devicesList.innerHTML = devices.map(device => {
        const isSelected = selectedDeviceId === device.id;
        const hasLocation = device.latitude && device.longitude;
        
        return `
        <div class="device-item ${isSelected ? 'selected' : ''} ${hasLocation ? 'has-location' : 'no-location'}" 
             data-device-id="${device.id}" 
             onclick="selectDevice(${device.id}); closeMobileMenu();">
            <div class="device-item-header">
                <div class="device-item-info">
                    <h3>
                        <span class="device-item-icon">${hasLocation ? '📍' : '🚗'}</span>
                        ${device.name}
                        ${device.color ? `<span class="device-color">${device.color}</span>` : ''}
                    </h3>
                </div>
                ${isSelected ? `<span class="tracking-badge-small">🟢</span>` : ''}
            </div>
            
            <div class="device-item-body">
                ${device.placa_gps ? `<div class="device-detail"><span class="detail-label">Placa:</span><span class="detail-value">${device.placa_gps}</span></div>` : ''}
                ${hasLocation ? 
                    `<div class="device-detail">
                        <span class="detail-label">📍 Ubicación:</span>
                        <span class="detail-value location-value">${device.latitude.toFixed(4)}, ${device.longitude.toFixed(4)}</span>
                    </div>` :
                    `<div class="device-detail"><span class="detail-label">Estado:</span><span class="detail-value no-location-text">Sin ubicación</span></div>`
                }
                ${device.last_update ? `<div class="device-detail"><span class="detail-label">Actualizado:</span><span class="detail-value">${formatDate(device.last_update)}</span></div>` : ''}
            </div>
            
            <div class="device-actions" onclick="event.stopPropagation()">
                ${device.placa_gps ? 
                    `<button class="btn-action btn-request" onclick="requestLocation(${device.id}); closeMobileMenu();" title="Solicitar ubicación">
                        <span>📲</span> Solicitar
                    </button>` : ''
                }
                ${hasLocation && !isSelected ? 
                    `<button class="btn-action btn-view" onclick="selectDevice(${device.id}); closeMobileMenu();">
                        <span>📍</span> Ver
                    </button>` : ''
                }
                ${isSelected ? 
                    `<button class="btn-action btn-stop" onclick="stopTracking(); closeMobileMenu();">
                        <span>⏹️</span> Detener
                    </button>` : ''
                }
                <button class="btn-action btn-rent" onclick="openRentalModal(${device.id})">
                    <span>⏰</span> Alquilar
                </button>
                <button class="btn-action btn-delete" onclick="deleteDevice(${device.id})">
                    <span>🗑️</span> Eliminar
                </button>
            </div>
        </div>
    `}).join('');
}

function getTimeRemaining(endDate) {
    const now = new Date();
    const end = new Date(endDate);
    const diff = end - now;
    
    if (diff <= 0) return 'EXPIRADO';
    
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
    
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

function updateMap(devices) {
    // Verificar que el mapa esté inicializado
    if (!map) {
        console.error('Mapa no inicializado, esperando...');
        setTimeout(() => {
            if (map) {
                updateMap(devices);
            }
        }, 500);
        return;
    }
    
    // Limpiar marcadores existentes
    Object.values(markers).forEach(marker => {
        if (marker && map.hasLayer(marker)) {
            map.removeLayer(marker);
        }
    });
    markers = {};
    
    // Agregar marcadores para cada dispositivo con ubicación
    devices.forEach(device => {
        if (device.latitude && device.longitude) {
            const isSelected = selectedDeviceId === device.id;
            
            // Icono diferente para dispositivo seleccionado
            const icon = isSelected ? 
                L.divIcon({
                    className: 'selected-marker',
                    html: '<div style="background-color: #4CAF50; width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px rgba(76, 175, 80, 0.8);"></div>',
                    iconSize: [20, 20],
                    iconAnchor: [10, 10]
                }) : L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-blue.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34]
                });
            
            const marker = L.marker([device.latitude, device.longitude], { icon: icon })
                .addTo(map)
                .bindPopup(`
                    <strong>${device.name}</strong><br>
                    ID: ${device.device_id}<br>
                    ${device.placa_gps ? `📡 Placa GPS: <strong>${device.placa_gps}</strong><br>` : ''}
                    ${device.color ? `🎨 Color: ${device.color}<br>` : ''}
                    ${device.description ? `${device.description}<br>` : ''}
                    <strong>📍 Ubicación Exacta:</strong><br>
                    Lat: ${device.latitude.toFixed(6)}<br>
                    Lon: ${device.longitude.toFixed(6)}<br>
                    ${device.last_update ? `Actualizado: ${formatDate(device.last_update)}<br>` : ''}
                    ${device.is_rented ? `<br><strong style="color: #f59e0b;">⏰ EN ALQUILER</strong>` : ''}
                    ${isSelected ? '<br><strong style="color: #10b981;">🟢 Siguiendo en tiempo real</strong>' : ''}
                `);
            
            markers[device.id] = marker;
            
            // Si es el dispositivo seleccionado, centrar el mapa y abrir popup
            if (isSelected) {
                map.setView([device.latitude, device.longitude], 15);
                marker.openPopup();
            }
        }
    });
    
    // Solo ajustar vista automáticamente si no hay dispositivo seleccionado
    if (!selectedDeviceId && devices.length > 0 && devices.some(d => d.latitude && d.longitude)) {
        const bounds = devices
            .filter(d => d.latitude && d.longitude)
            .map(d => [d.latitude, d.longitude]);
        
        if (bounds.length > 0) {
            map.fitBounds(bounds, { padding: [50, 50] });
        }
    }
}

async function handleAddDevice(e) {
    e.preventDefault();
    
    const deviceName = document.getElementById('deviceName').value.trim();
    const placa_gps = document.getElementById('placa_gps').value.trim();
    const color = document.getElementById('color').value.trim();
    
    if (!deviceName) {
        showError('Por favor ingresa un nombre para el vehículo');
        return;
    }
    
    if (!placa_gps) {
        showError('Por favor ingresa la placa GPS o número SIM');
        return;
    }
    
    const formData = {
        name: deviceName,
        placa_gps: placa_gps,
        color: color,
        description: `Vehículo eléctrico de juguete - Color: ${color || 'No especificado'}`
    };
    
    try {
        const response = await fetch('/api/devices', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess('✅ Vehículo agregado correctamente');
            document.getElementById('deviceForm').reset();
            document.getElementById('deviceName').focus();
            // Recargar dispositivos y forzar actualización de estadísticas
            await loadDevices();
            // Esperar un momento y verificar que las estadísticas se actualizaron
            setTimeout(() => {
                if (allDevices && allDevices.length > 0) {
                    updateStats(allDevices);
                }
            }, 200);
            
            // Servicio automático desactivado - solo envío manual
            // if (placa_gps && placa_gps.trim() !== '') {
            //     await startAutoUpdateIfNotRunning();
            // }
            
            showNotification('Vehículo Agregado', `Se agregó ${deviceName} correctamente`, 'success');
        } else {
            showError(result.error || 'Error al agregar el vehículo');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al agregar el vehículo: ' + error.message);
    }
}

async function requestLocation(deviceId) {
    const device = allDevices.find(d => d.id === deviceId);
    if (!device) {
        showError('Vehículo no encontrado');
        return;
    }
    
    if (!device.placa_gps) {
        showError('Este vehículo no tiene número de SIM configurado');
        return;
    }
    
    if (!confirm(`¿Enviar SMS a ${device.name} para solicitar ubicación?`)) {
        return;
    }
    
    try {
        showSuccess('Enviando SMS...');
        
        const response = await fetch(`/api/devices/${deviceId}/request-location`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ message: 'LOC' })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(`✅ SMS enviado a ${device.name}. La placa responderá con su ubicación.`);
            showNotification('SMS Enviado', `Se solicitó ubicación a ${device.name}`, 'success');
            
            // Esperar unos segundos y actualizar ubicación
            setTimeout(() => {
                loadDevices();
            }, 5000);
        } else {
            const errorMsg = result.error || 'Error al enviar SMS';
            console.error('Error al enviar SMS:', result);
            
            // Si se alcanzó el límite diario, detener el servicio automático
            if (errorMsg.includes('límite') || errorMsg.includes('limit') || errorMsg.includes('429')) {
                showError('Límite diario de SMS alcanzado (50 SMS/día). El servicio automático se detuvo.');
                showNotification('Límite Alcanzado', 'Se alcanzó el límite de 50 SMS/día. El servicio automático se detuvo. Espera 24 horas o detén el servicio manualmente.', 'error');
                
                // Detener el servicio automático
                try {
                    await fetch('/api/auto-update/stop', { method: 'POST' });
                    console.log('Servicio automático detenido debido al límite');
                } catch (e) {
                    console.error('Error al detener servicio:', e);
                }
            } else {
                showError(errorMsg);
                showNotification('Error al Enviar SMS', errorMsg, 'error');
            }
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al enviar SMS. Verifica que Twilio esté configurado.');
    }
}

async function deleteDevice(deviceId) {
    if (!confirm('¿Estás seguro de que deseas eliminar este dispositivo?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/devices/${deviceId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess('Dispositivo eliminado correctamente');
            loadDevices();
        } else {
            showError(result.error || 'Error al eliminar el dispositivo');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al eliminar el dispositivo');
    }
}

function selectDevice(deviceId) {
    // Detener seguimiento anterior si existe
    if (realTimeUpdateInterval) {
        clearInterval(realTimeUpdateInterval);
        realTimeUpdateInterval = null;
    }
    
    // Si se selecciona el mismo dispositivo, deseleccionar
    if (selectedDeviceId === deviceId) {
        stopTracking();
        return;
    }
    
    selectedDeviceId = deviceId;
    const device = allDevices.find(d => d.id === deviceId);
    
    if (!device) {
        loadDevices();
        return;
    }
    
    // Mostrar indicador de seguimiento
    const trackingStatus = document.getElementById('trackingStatus');
    if (trackingStatus) {
        trackingStatus.style.display = 'flex';
        const statusText = trackingStatus.querySelector('.status-text');
        if (statusText) {
            statusText.textContent = `Siguiendo "${device.name}" en tiempo real - Actualización cada 10 segundos`;
        }
    }
    
    // Si el dispositivo tiene ubicación, centrar el mapa
    if (device.latitude && device.longitude) {
        map.setView([device.latitude, device.longitude], 15);
        if (markers[deviceId]) {
            markers[deviceId].openPopup();
        }
    }
    
    // Actualizar la lista para mostrar el estado seleccionado
    displayDevices(allDevices);
    
    // Iniciar actualización en tiempo real cada 10 segundos
    startRealTimeTracking(deviceId);
}

function startRealTimeTracking(deviceId) {
    // Actualizar inmediatamente
    updateDeviceLocation(deviceId);
    
    // Configurar intervalo de 10 segundos
    realTimeUpdateInterval = setInterval(() => {
        updateDeviceLocation(deviceId);
    }, 10000); // 10 segundos
}

async function updateDeviceLocation(deviceId) {
    try {
        const response = await fetch('/api/devices');
        const devices = await response.json();
        
        const device = devices.find(d => d.id === deviceId);
        if (device) {
            // Actualizar en allDevices
            const index = allDevices.findIndex(d => d.id === deviceId);
            if (index !== -1) {
                allDevices[index] = device;
            }
            
            // Actualizar el mapa
            updateMap(devices);
            
            // Actualizar la lista
            displayDevices(devices);
        }
    } catch (error) {
        console.error('Error al actualizar ubicación:', error);
    }
}

function stopTracking() {
    selectedDeviceId = null;
    
    if (realTimeUpdateInterval) {
        clearInterval(realTimeUpdateInterval);
        realTimeUpdateInterval = null;
    }
    
    // Ocultar indicador de seguimiento
    const trackingStatus = document.getElementById('trackingStatus');
    if (trackingStatus) {
        trackingStatus.style.display = 'none';
    }
    
    // Recargar todos los dispositivos y actualizar vista
    loadDevices();
}

function centerOnDevice(latitude, longitude) {
    map.setView([latitude, longitude], 15);
    // Abrir popup del marcador si existe
    const marker = Object.values(markers).find(m => {
        const pos = m.getLatLng();
        return Math.abs(pos.lat - latitude) < 0.0001 && Math.abs(pos.lng - longitude) < 0.0001;
    });
    if (marker) {
        marker.openPopup();
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    return date.toLocaleString('es-ES');
}

function showError(message) {
    const devicesList = document.getElementById('devicesList');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error';
    errorDiv.textContent = message;
    devicesList.insertBefore(errorDiv, devicesList.firstChild);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

function showSuccess(message) {
    const devicesList = document.getElementById('devicesList');
    const successDiv = document.createElement('div');
    successDiv.className = 'success';
    successDiv.textContent = message;
    devicesList.insertBefore(successDiv, devicesList.firstChild);
    
    setTimeout(() => {
        successDiv.remove();
    }, 5000);
}

// Funciones de alquiler
function openRentalModal(deviceId) {
    currentRentalDeviceId = deviceId;
    const modal = document.getElementById('rentalModal');
    modal.classList.add('show');
    document.getElementById('rentalHours').focus();
}

function closeRentalModal() {
    const modal = document.getElementById('rentalModal');
    modal.classList.remove('show');
    currentRentalDeviceId = null;
    document.getElementById('rentalForm').reset();
}

async function handleStartRental(e) {
    e.preventDefault();
    
    if (!currentRentalDeviceId) {
        showError('No se ha seleccionado un vehículo');
        return;
    }
    
    const durationHours = parseInt(document.getElementById('rentalHours').value);
    
    if (!durationHours || durationHours < 1) {
        showError('La duración debe ser al menos 1 hora');
        return;
    }
    
    console.log('Iniciando alquiler para dispositivo:', currentRentalDeviceId, 'duración:', durationHours);
    
    try {
        const response = await fetch(`/api/devices/${currentRentalDeviceId}/rent`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ duration_hours: durationHours })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess(`✅ Alquiler iniciado por ${durationHours} hora(s)`);
            closeRentalModal();
            // Recargar dispositivos y forzar actualización de la sección de alquilados
            await loadDevices();
            
            // Forzar que se muestre la sección de alquilados después de cargar
            setTimeout(() => {
                const rentedCard = document.getElementById('rentedCard');
                if (rentedCard) {
                    // Forzar mostrar
                    rentedCard.style.setProperty('display', 'flex', 'important');
                    rentedCard.style.setProperty('visibility', 'visible', 'important');
                    
                    // Hacer scroll hacia la sección
                    rentedCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    
                    console.log('Sección de alquilados forzada a mostrarse');
                }
            }, 300);
            showNotification('Alquiler Iniciado', `El vehículo está en alquiler por ${durationHours} hora(s)`, 'success');
        } else {
            showError(result.error || 'Error al iniciar el alquiler');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al iniciar el alquiler');
    }
}

async function endRental(deviceId) {
    if (!confirm('¿Finalizar el alquiler de este vehículo?')) {
        return;
    }
    
    console.log('Finalizando alquiler para dispositivo:', deviceId);
    
    try {
        const response = await fetch(`/api/devices/${deviceId}/end-rental`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess('✅ Alquiler finalizado correctamente');
            // Recargar dispositivos y forzar actualización de estadísticas
            await loadDevices();
            // Esperar un momento y verificar que las estadísticas se actualizaron
            setTimeout(() => {
                if (allDevices && allDevices.length > 0) {
                    updateStats(allDevices);
                }
            }, 200);
            showNotification('Alquiler Finalizado', 'El vehículo está disponible nuevamente', 'success');
        } else {
            showError(result.error || 'Error al finalizar el alquiler');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al finalizar el alquiler');
    }
}

async function checkExpiredRentals() {
    // Función desactivada - no mostrar notificaciones de alquileres expirados
    // Solo actualizar la lista si hay cambios, pero sin notificaciones
    try {
        const response = await fetch('/api/rentals/expired');
        const expiredDevices = await response.json();
        
        // NO mostrar notificaciones - solo actualizar la lista
        // expiredDevices.forEach(device => {
        //     showNotification(
        //         '⏰ Alquiler Expirado',
        //         `El alquiler del vehículo "${device.name}" ha expirado. Ubicación: ${device.latitude?.toFixed(6)}, ${device.longitude?.toFixed(6)}`,
        //         'danger'
        //     );
        // });
        
        if (expiredDevices.length > 0) {
            loadDevices(); // Solo actualizar la lista sin notificar
        }
    } catch (error) {
        console.error('Error al verificar alquileres expirados:', error);
    }
}

function showNotification(title, message, type = 'info') {
    // Solicitar permiso para notificaciones
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, {
            body: message,
            icon: '/static/icon-192.png',
            badge: '/static/icon-192.png'
        });
    } else if ('Notification' in window && Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                new Notification(title, {
                    body: message,
                    icon: '/static/icon-192.png'
                });
            }
        });
    }
    
    // Mostrar notificación en pantalla
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.innerHTML = `
        <div class="notification-title">${title}</div>
        <div class="notification-message">${message}</div>
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'notificationSlideIn 0.3s ease-out reverse';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Solicitar permiso de notificaciones al cargar
if ('Notification' in window && Notification.permission === 'default') {
    Notification.requestPermission();
}

// Variable para el intervalo de estado del servicio de actualización automática
let autoUpdateStatusInterval = null;

// Función para iniciar automáticamente el servicio si no está corriendo
async function startAutoUpdateIfNotRunning() {
    try {
        // Verificar estado actual
        const statusResponse = await fetch('/api/auto-update/status');
        const status = await statusResponse.json();
        
        // Si no está corriendo, iniciarlo
        if (!status.is_running) {
            const startResponse = await fetch('/api/auto-update/start', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const result = await startResponse.json();
            
            if (startResponse.ok && result.status === 'started') {
                console.log('✅ Servicio de actualización automática iniciado automáticamente');
                showNotification('Actualización Automática', 'El servicio se inició automáticamente. Enviando SMS cada 10 segundos a todos los vehículos con número de SIM.', 'success');
            } else {
                console.log('⚠️ No se pudo iniciar el servicio automáticamente:', result.message);
            }
        } else {
            console.log('✅ El servicio de actualización automática ya está corriendo');
        }
    } catch (error) {
        console.error('Error al verificar/iniciar servicio de actualización:', error);
    }
}

// Funciones para controlar el servicio de actualización automática (si hay panel de control)
async function startAutoUpdate() {
    try {
        const response = await fetch('/api/auto-update/start', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (response.ok && result.status === 'started') {
            showSuccess('Actualización automática iniciada');
            // Actualizar estado cada 2 segundos
            if (autoUpdateStatusInterval) {
                clearInterval(autoUpdateStatusInterval);
            }
            autoUpdateStatusInterval = setInterval(checkAutoUpdateStatus, 2000);
        } else {
            showError(result.message || 'Error al iniciar actualización automática');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al iniciar actualización automática');
    }
}

async function stopAutoUpdate() {
    try {
        const response = await fetch('/api/auto-update/stop', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showSuccess('Actualización automática detenida');
            if (autoUpdateStatusInterval) {
                clearInterval(autoUpdateStatusInterval);
                autoUpdateStatusInterval = null;
            }
        } else {
            showError(result.message || 'Error al detener actualización automática');
        }
    } catch (error) {
        console.error('Error:', error);
        showError('Error al detener actualización automática');
    }
}

async function checkAutoUpdateStatus() {
    try {
        const response = await fetch('/api/auto-update/status');
        const status = await response.json();
        
        if (response.ok) {
            // Actualizar UI si existe el panel de control
            const statusDot = document.getElementById('statusDot');
            const statusText = document.getElementById('statusText');
            if (statusDot && statusText) {
                if (status.is_running) {
                    statusDot.style.backgroundColor = '#10b981';
                    statusText.textContent = 'Activo';
                } else {
                    statusDot.style.backgroundColor = '#ef4444';
                    statusText.textContent = 'Detenido';
                }
            }
        }
    } catch (error) {
        console.error('Error al verificar estado:', error);
    }
}

// Servicio automático desactivado - solo envío manual para evitar gastar los 50 SMS gratis
// setTimeout(async () => {
//     if (allDevices && allDevices.length > 0) {
//         const devicesWithSim = allDevices.filter(d => d.placa_gps && d.placa_gps.trim() !== '');
//         if (devicesWithSim.length > 0) {
//             console.log(`Encontrados ${devicesWithSim.length} vehículos con número de SIM. Iniciando servicio automático...`);
//             await startAutoUpdateIfNotRunning();
//         }
//     }
// }, 3000);




