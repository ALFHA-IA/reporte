# -*- coding: utf-8 -*-
from flask import Flask, render_template_string, request, jsonify
import mysql.connector
from datetime import date
import json
from flask import render_template


# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
# Reemplaza los valores de 'user', 'password' y 'database' según tu configuración.
# --- CONFIGURACIÓN DE LA BASE DE DATOS ---
import os
from urllib.parse import urlparse

# Analiza la URL de la base de datos de Render
db_url = os.environ.get('DATABASE_URL')
if db_url:
    url = urlparse(db_url)
    DB_CONFIG = {
        'user': url.username,
        'password': url.password,
        'host': url.hostname,
        'database': url.path[1:],
        'port': url.port
    }
else:
    # Configuración local de fallback (solo para desarrollo)
    DB_CONFIG = {
        'user': 'root',
        'password': '',
        'host': 'localhost',
        'database': 'reporte'
    }

# --- FUNCIONES DE GESTIÓN (CRUD) ---
def get_db_connection():
    """Establece y retorna una conexión a la base de datos."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print("INFO: Conexión a la base de datos exitosa.")
        return conn
    except mysql.connector.Error as err:
        print(f"ERROR: Error de conexión a la base de datos: {err}")
        return None

def agregar_venta(venta_data):
    """Inserta una nueva venta en la base de datos.
    Crea el cliente y el producto si no existen."""
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        # Busca o crea el cliente
        cursor.execute("SELECT id_cliente FROM clientes WHERE doc_cliente = %s", (venta_data['doc_cliente'],))
        id_cliente = cursor.fetchone()
        if id_cliente is None:
            cursor.execute("INSERT INTO clientes (doc_cliente, cliente, telefono) VALUES (%s, %s, %s)",
                           (venta_data['doc_cliente'], venta_data['cliente'], venta_data['telefono']))
            id_cliente = (cursor.lastrowid,)
            
        # Busca o crea el producto
        cursor.execute("SELECT id_producto FROM productos WHERE nombre_original = %s", (venta_data['articulos'],))
        id_producto = cursor.fetchone()
        if id_producto is None:
            cursor.execute("INSERT INTO productos (nombre_original, nombre_limpio, categoria, marca) VALUES (%s, %s, %s, %s)",
                           (venta_data['articulos'], venta_data['articulos'].strip().lower(), 'Sin Categoría', 'Sin Marca'))
            id_producto = (cursor.lastrowid,)
            
        # Inserta la nueva venta
        cursor.execute("INSERT INTO ventas (fecha, documento, nro_doc, medio_pago, vendedor, id_cliente) VALUES (%s, %s, %s, %s, %s, %s)",
                       (venta_data['fecha'], venta_data['documento'], venta_data['nro_doc'], venta_data['medio_pago'], venta_data['vendedor'], id_cliente[0]))
        id_venta = cursor.lastrowid
        
        # Inserta el detalle de la venta
        cursor.execute("INSERT INTO detalle_venta (id_venta, id_producto, cantidad, importe_soles) VALUES (%s, %s, %s, %s)",
                       (id_venta, id_producto[0], venta_data['cantidad'], venta_data['importe_soles']))
        
        conn.commit()
        print(f"ÉXITO: Venta {id_venta} agregada con éxito.")
        return True
    except mysql.connector.Error as err:
        print(f"ERROR: Error al agregar venta: {err}")
        conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def editar_venta(id_venta, nuevos_datos):
    """Actualiza una venta existente.
    Si el artículo cambia, crea o actualiza el producto correspondiente."""
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        print(f"INFO: Editando venta con ID: {id_venta}, nuevos datos: {nuevos_datos}")

        # Lógica de actualización del producto
        cursor.execute("SELECT dv.id_producto FROM detalle_venta dv WHERE dv.id_venta = %s", (id_venta,))
        id_producto_actual_tuple = cursor.fetchone()

        if id_producto_actual_tuple:
            id_producto_actual = id_producto_actual_tuple[0]
            cursor.execute("SELECT nombre_original FROM productos WHERE id_producto = %s", (id_producto_actual,))
            nombre_original_actual_tuple = cursor.fetchone()
            nombre_original_actual = nombre_original_actual_tuple[0] if nombre_original_actual_tuple else ""

            if nombre_original_actual != nuevos_datos['articulos']:
                print("INFO: El artículo ha cambiado. Creando/actualizando producto...")
                cursor.execute("SELECT id_producto FROM productos WHERE nombre_original = %s", (nuevos_datos['articulos'],))
                id_producto_nuevo_tuple = cursor.fetchone()
                
                if id_producto_nuevo_tuple is None:
                    cursor.execute("INSERT INTO productos (nombre_original, nombre_limpio, categoria, marca) VALUES (%s, %s, %s, %s)",
                                   (nuevos_datos['articulos'], nuevos_datos['articulos'].strip().lower(), 'Sin Categoría', 'Sin Marca'))
                    id_producto_nuevo = cursor.lastrowid
                else:
                    id_producto_nuevo = id_producto_nuevo_tuple[0]
                
                # Actualiza el id_producto en la tabla detalle_venta
                cursor.execute("UPDATE detalle_venta SET id_producto = %s WHERE id_venta = %s", (id_producto_nuevo, id_venta))
        
        # Actualiza la tabla de ventas
        update_venta_query = "UPDATE ventas SET fecha = %s, documento = %s, nro_doc = %s, medio_pago = %s, vendedor = %s WHERE id_venta = %s"
        update_venta_params = (nuevos_datos['fecha'], nuevos_datos['documento'], nuevos_datos['nro_doc'], nuevos_datos['medio_pago'], nuevos_datos['vendedor'], id_venta)
        cursor.execute(update_venta_query, update_venta_params)

        # Actualiza la tabla de detalle_venta
        update_detalle_query = "UPDATE detalle_venta SET cantidad = %s, importe_soles = %s WHERE id_venta = %s"
        update_detalle_params = (nuevos_datos['cantidad'], nuevos_datos['importe_soles'], id_venta)
        cursor.execute(update_detalle_query, update_detalle_params)
        
        conn.commit()
        print(f"ÉXITO: Venta {id_venta} editada con éxito.")
        return True
    except mysql.connector.Error as err:
        print(f"ERROR: Error al editar venta: {err}")
        conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def eliminar_venta(id_venta):
    """Elimina una venta existente de la base de datos, incluyendo su detalle."""
    conn = get_db_connection()
    if not conn: return False
    cursor = conn.cursor()
    try:
        print(f"INFO: Eliminando venta con ID: {id_venta}...")
        
        # Elimina de la tabla de detalle
        cursor.execute("DELETE FROM detalle_venta WHERE id_venta = %s", (id_venta,))
        
        # Elimina de la tabla de ventas
        cursor.execute("DELETE FROM ventas WHERE id_venta = %s", (id_venta,))
        
        conn.commit()
        print(f"ÉXITO: Venta {id_venta} eliminada con éxito.")
        return True
    except mysql.connector.Error as err:
        print(f"ERROR: Error al eliminar venta: {err}")
        conn.rollback()
        return False
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def obtener_ventas(search_term=None):
    """
    Obtiene todas las ventas de la base de datos, uniendo tablas.
    Permite filtrar por un término de búsqueda.
    """
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
        SELECT
            v.id_venta,
            v.fecha,
            v.documento,
            v.nro_doc,
            v.medio_pago,
            v.vendedor,
            c.doc_cliente,
            c.cliente,
            c.telefono,
            p.nombre_original AS articulos,
            dv.cantidad,
            dv.importe_soles
        FROM ventas v
        JOIN clientes c ON v.id_cliente = c.id_cliente
        JOIN detalle_venta dv ON v.id_venta = dv.id_venta
        JOIN productos p ON dv.id_producto = p.id_producto
        """
        params = []
        if search_term:
            query += """
            WHERE c.cliente LIKE %s OR c.doc_cliente LIKE %s OR p.nombre_original LIKE %s OR v.documento LIKE %s OR v.nro_doc LIKE %s OR v.vendedor LIKE %s
            """
            search_pattern = f"%{search_term}%"
            params = [search_pattern] * 6
            
        query += " ORDER BY v.fecha DESC, v.id_venta DESC"

        cursor.execute(query, params)
        ventas = cursor.fetchall()
        for venta in ventas:
            if isinstance(venta['fecha'], date):
                venta['fecha'] = venta['fecha'].isoformat()
        print(f"INFO: Se obtuvieron {len(ventas)} registros de ventas.")
        return ventas
    except mysql.connector.Error as err:
        print(f"ERROR: Error al obtener ventas: {err}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def obtener_ventas_agregadas_por_vendedor():
    """Obtiene el total de ventas (importe) por cada vendedor."""
    conn = get_db_connection()
    if not conn: return []
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
        SELECT
            v.vendedor,
            SUM(dv.importe_soles) AS total_ventas
        FROM ventas v
        JOIN detalle_venta dv ON v.id_venta = dv.id_venta
        GROUP BY v.vendedor
        ORDER BY total_ventas DESC
        """
        cursor.execute(query)
        ventas_agregadas = cursor.fetchall()
        print(f"INFO: Se obtuvieron {len(ventas_agregadas)} datos agregados para el gráfico.")
        return ventas_agregadas
    except mysql.connector.Error as err:
        print(f"ERROR: Error al obtener ventas agregadas: {err}")
        return []
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# --- CÓDIGO DEL SERVIDOR FLASK ---
app = Flask(__name__)

# Plantilla HTML y JavaScript integrados para la página principal
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gestión de Ventas</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-7xl mx-auto bg-white p-6 rounded-xl shadow-lg">
        <!-- Contenedor del título y el nuevo botón de reporte -->
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Gestión de Ventas</h1>
            <!-- Botón para ver el reporte -->
            <a href="/reporte" target="_blank" class="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition ease-in-out duration-150">Ver Reporte</a>
        </div>

        <!-- Formulario para Añadir/Editar Ventas -->
        <div class="mb-8">
            <h2 class="text-2xl font-semibold text-gray-700 mb-4" id="form-title">Añadir Nueva Venta</h2>
            <form id="venta-form" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                <input type="hidden" id="venta-id">
                <div>
                    <label for="fecha" class="block text-sm font-medium text-gray-700">Fecha</label>
                    <input type="date" id="fecha" name="fecha" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="documento" class="block text-sm font-medium text-gray-700">Documento</label>
                    <input type="text" id="documento" name="documento" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="nro_doc" class="block text-sm font-medium text-gray-700">Nro. Doc</label>
                    <input type="text" id="nro_doc" name="nro_doc" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="medio_pago" class="block text-sm font-medium text-gray-700">Medio de Pago</label>
                    <input type="text" id="medio_pago" name="medio_pago" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="doc_cliente" class="block text-sm font-medium text-gray-700">Doc. Cliente</label>
                    <input type="text" id="doc_cliente" name="doc_cliente" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="cliente" class="block text-sm font-medium text-gray-700">Cliente</label>
                    <input type="text" id="cliente" name="cliente" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="telefono" class="block text-sm font-medium text-gray-700">Teléfono</label>
                    <input type="text" id="telefono" name="telefono" class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="articulos" class="block text-sm font-medium text-gray-700">Artículos</label>
                    <input type="text" id="articulos" name="articulos" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="cantidad" class="block text-sm font-medium text-gray-700">Cantidad</label>
                    <input type="number" id="cantidad" name="cantidad" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="importe_soles" class="block text-sm font-medium text-gray-700">Importe en Soles</label>
                    <input type="number" id="importe_soles" name="importe_soles" step="0.01" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div>
                    <label for="vendedor" class="block text-sm font-medium text-gray-700">Vendedor</label>
                    <input type="text" id="vendedor" name="vendedor" required class="mt-1 block w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                </div>
                <div class="col-span-1 md:col-span-2 lg:col-span-3 flex justify-end space-x-4">
                    <button type="submit" class="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition ease-in-out duration-150">Guardar Venta</button>
                    <button type="button" id="cancel-edit-btn" class="hidden px-6 py-2 bg-gray-300 text-gray-800 font-semibold rounded-md shadow-md hover:bg-gray-400 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 transition ease-in-out duration-150">Cancelar</button>
                </div>
            </form>
        </div>
        
        <!-- Sección de Gráficos -->
        <div class="mb-8">
            <h2 class="text-2xl font-semibold text-gray-700 mb-4">Gráfico de Ventas por Vendedor</h2>
            <div class="p-4 bg-gray-50 rounded-xl shadow-inner">
                <canvas id="ventasChart"></canvas>
            </div>
        </div>

        <!-- Tabla de Ventas con buscador -->
        <div>
            <div class="flex flex-col sm:flex-row justify-between items-center mb-4">
                <h2 class="text-2xl font-semibold text-gray-700 mb-2 sm:mb-0">Registro de Ventas</h2>
                <div class="flex w-full sm:w-auto">
                    <input type="text" id="search-input" placeholder="Buscar..." class="w-full sm:w-64 px-4 py-2 border border-gray-300 rounded-l-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500">
                    <button id="search-button" class="px-4 py-2 bg-indigo-600 text-white font-semibold rounded-r-md shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition ease-in-out duration-150">Buscar</button>
                </div>
            </div>
            <div class="overflow-x-auto overflow-y-auto max-h-[500px] bg-white rounded-xl shadow-lg">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50 sticky top-0">
                        <tr>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Documento</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nro. Doc</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cliente</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Artículo</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cantidad</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Importe S/</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vendedor</th>
                            <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Acciones</th>
                        </tr>
                    </thead>
                    <tbody id="ventas-body" class="bg-white divide-y divide-gray-200">
                        <!-- Las filas de la tabla se insertarán aquí por JavaScript -->
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Modal de Confirmación de Eliminación -->
        <div id="delete-modal" class="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full hidden">
            <div class="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
                <div class="mt-3 text-center">
                    <h3 class="text-lg leading-6 font-medium text-gray-900">Confirmar Eliminación</h3>
                    <div class="mt-2 px-7 py-3">
                        <p class="text-sm text-gray-500">¿Estás seguro de que deseas eliminar esta venta?</p>
                    </div>
                    <div class="items-center px-4 py-3">
                        <button id="confirm-delete-btn" class="px-4 py-2 bg-red-600 text-white text-base font-medium rounded-md w-24 mr-2 hover:bg-red-700">Eliminar</button>
                        <button id="cancel-delete-btn" class="px-4 py-2 bg-gray-300 text-gray-800 text-base font-medium rounded-md w-24 hover:bg-gray-400">Cancelar</button>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Contenedor para mensajes de notificación -->
        <div id="notification-container" class="fixed bottom-5 right-5 z-50"></div>
    </div>

    <script>
        const ventasBody = document.getElementById('ventas-body');
        const form = document.getElementById('venta-form');
        const formTitle = document.getElementById('form-title');
        const ventaIdInput = document.getElementById('venta-id');
        const cancelEditBtn = document.getElementById('cancel-edit-btn');
        const deleteModal = document.getElementById('delete-modal');
        const confirmDeleteBtn = document.getElementById('confirm-delete-btn');
        const cancelDeleteBtn = document.getElementById('cancel-delete-btn');
        const notificationContainer = document.getElementById('notification-container');
        const searchInput = document.getElementById('search-input');
        const searchButton = document.getElementById('search-button');
        const ventasChartCtx = document.getElementById('ventasChart').getContext('2d');
        let ventasChartInstance;
        let currentDeleteId = null;

        // Función para mostrar mensajes de notificación
        function showNotification(message, isSuccess = true) {
            const notification = document.createElement('div');
            notification.className = `p-4 mb-2 text-white rounded-md shadow-lg transition-opacity duration-300 ${isSuccess ? 'bg-green-500' : 'bg-red-500'}`;
            notification.textContent = message;
            notificationContainer.appendChild(notification);

            setTimeout(() => {
                notification.classList.add('opacity-0');
                notification.addEventListener('transitionend', () => notification.remove());
            }, 3000);
        }

        // Función para renderizar la tabla con los datos de ventas
        async function renderVentas(searchTerm = '') {
            try {
                const url = searchTerm ? `/ventas?q=${encodeURIComponent(searchTerm)}` : '/ventas';
                const response = await fetch(url);
                if (!response.ok) throw new Error('Error al obtener ventas');
                const ventas = await response.json();
                
                ventasBody.innerHTML = '';
                ventas.forEach(venta => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">${venta.id_venta}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.fecha}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.documento}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.nro_doc}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.cliente}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.articulos}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.cantidad}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.importe_soles}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">${venta.vendedor}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                            <button onclick="editarVenta(${venta.id_venta})" class="text-indigo-600 hover:text-indigo-900 mr-2">Editar</button>
                            <button onclick="confirmarEliminar(${venta.id_venta})" class="text-red-600 hover:text-red-900">Eliminar</button>
                        </td>
                    `;
                    ventasBody.appendChild(row);
                });
            } catch (error) {
                console.error('Error al renderizar ventas:', error);
                showNotification('Error al cargar las ventas.', false);
            }
        }
        
        // Función para renderizar el gráfico
        async function renderChart() {
            try {
                const response = await fetch('/ventas-grafico');
                if (!response.ok) throw new Error('Error al obtener datos para el gráfico');
                const data = await response.json();

                const labels = data.map(item => item.vendedor);
                const values = data.map(item => item.total_ventas);

                if (ventasChartInstance) {
                    ventasChartInstance.destroy(); // Destruye el gráfico anterior si existe
                }

                ventasChartInstance = new Chart(ventasChartCtx, {
                    type: 'bar',
                    data: {
                        labels: labels,
                        datasets: [{
                            label: 'Total de Ventas en Soles (S/)',
                            data: values,
                            backgroundColor: 'rgba(75, 192, 192, 0.6)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        scales: {
                            y: {
                                beginAtZero: true,
                                title: {
                                    display: true,
                                    text: 'Importe en Soles'
                                }
                            },
                            x: {
                                title: {
                                    display: true,
                                    text: 'Vendedor'
                                }
                            }
                        }
                    }
                });
            } catch (error) {
                console.error('Error al renderizar el gráfico:', error);
                showNotification('Error al cargar el gráfico de ventas.', false);
            }
        }


        // Manejar la búsqueda
        function handleSearch() {
            const searchTerm = searchInput.value;
            renderVentas(searchTerm);
        }

        // Cargar los datos al iniciar la página
        document.addEventListener('DOMContentLoaded', () => {
            renderVentas();
            renderChart(); // Carga el gráfico al iniciar
            
            // Agregar listeners para el buscador
            searchButton.addEventListener('click', handleSearch);
            searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    handleSearch();
                }
            });
        });

        // Manejar el envío del formulario (Añadir/Editar)
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            // Convertir cantidad e importe a números
            data.cantidad = parseFloat(data.cantidad);
            data.importe_soles = parseFloat(data.importe_soles);

            const ventaId = ventaIdInput.value;
            const url = ventaId ? '/editar-venta' : '/agregar-venta';
            const method = 'POST';

            if (ventaId) {
                data.id_venta = parseInt(ventaId);
            }

            try {
                const response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                });
                
                const result = await response.json();
                if (result.success) {
                    showNotification(result.message, true);
                    form.reset();
                    ventaIdInput.value = '';
                    formTitle.textContent = 'Añadir Nueva Venta';
                    cancelEditBtn.classList.add('hidden');
                    renderVentas();
                    renderChart(); // Actualiza el gráfico después de una operación exitosa
                } else {
                    showNotification('Error: ' + result.message, false);
                }
            } catch (error) {
                console.error('Error en la operación:', error);
                showNotification('Ocurrió un error inesperado.', false);
            }
        });

        // Llenar el formulario para editar una venta
        window.editarVenta = async (id) => {
            try {
                const response = await fetch('/ventas');
                const ventas = await response.json();
                const venta = ventas.find(v => v.id_venta === id);

                if (venta) {
                    ventaIdInput.value = venta.id_venta;
                    formTitle.textContent = `Editar Venta #${venta.id_venta}`;
                    document.getElementById('fecha').value = venta.fecha;
                    document.getElementById('documento').value = venta.documento;
                    document.getElementById('nro_doc').value = venta.nro_doc;
                    document.getElementById('medio_pago').value = venta.medio_pago;
                    document.getElementById('doc_cliente').value = venta.doc_cliente;
                    document.getElementById('cliente').value = venta.cliente;
                    document.getElementById('telefono').value = venta.telefono;
                    document.getElementById('articulos').value = venta.articulos;
                    document.getElementById('cantidad').value = venta.cantidad;
                    document.getElementById('importe_soles').value = venta.importe_soles;
                    document.getElementById('vendedor').value = venta.vendedor;
                    cancelEditBtn.classList.remove('hidden');
                } else {
                    showNotification('Venta no encontrada.', false);
                }
            } catch (error) {
                console.error('Error al cargar datos para editar:', error);
                showNotification('Ocurrió un error al cargar los datos.', false);
            }
        };

        // Cancelar la edición
        cancelEditBtn.addEventListener('click', () => {
            form.reset();
            ventaIdInput.value = '';
            formTitle.textContent = 'Añadir Nueva Venta';
            cancelEditBtn.classList.add('hidden');
        });

        // Mostrar modal de confirmación para eliminar
        window.confirmarEliminar = (id) => {
            currentDeleteId = id;
            deleteModal.classList.remove('hidden');
        };

        // Ocultar modal de confirmación
        cancelDeleteBtn.addEventListener('click', () => {
            deleteModal.classList.add('hidden');
            currentDeleteId = null;
        });

        // Eliminar la venta
        confirmDeleteBtn.addEventListener('click', async () => {
            if (!currentDeleteId) return;

            try {
                const response = await fetch('/eliminar-venta', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id_venta: currentDeleteId })
                });

                const result = await response.json();
                if (result.success) {
                    showNotification(result.message, true);
                    renderVentas();
                    renderChart();
                } else {
                    showNotification('Error: ' + result.message, false);
                }
            } catch (error) {
                console.error('Error al eliminar la venta:', error);
                showNotification('Ocurrió un error al eliminar la venta.', false);
            } finally {
                deleteModal.classList.add('hidden');
                currentDeleteId = null;
            }
        });
    </script>
</body>
</html>
"""

# Plantilla HTML para la página de reporte de ventas
REPORTE_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte de Ventas</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
        body { font-family: 'Inter', sans-serif; }
    </style>
</head>
<body class="bg-gray-100 p-8">
    <div class="max-w-7xl mx-auto bg-white p-6 rounded-xl shadow-lg">
        <div class="flex justify-between items-center mb-6">
            <h1 class="text-3xl font-bold text-gray-800">Reporte de Ventas</h1>
            <a href="/" class="px-6 py-2 bg-indigo-600 text-white font-semibold rounded-md shadow-md hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition ease-in-out duration-150">Volver a la Gestión</a>
        </div>
        <div class="overflow-x-auto overflow-y-auto max-h-[700px] bg-white rounded-xl shadow-lg">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50 sticky top-0">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">ID</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fecha</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Documento</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Nro. Doc</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cliente</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Artículo</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Cantidad</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Importe S/</th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Vendedor</th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    {% for venta in ventas %}
                    <tr>
                        <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">{{ venta.id_venta }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.fecha }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.documento }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.nro_doc }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.cliente }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.articulos }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.cantidad }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.importe_soles }}</td>
                        <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">{{ venta.vendedor }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

# Rutas de la aplicación Flask
@app.route('/')
def index():
    """Ruta para la página principal de gestión de ventas."""
    return render_template_string(HTML_TEMPLATE)


@app.route('/reporte')
def reporte():
    """Ruta para la página del reporte de ventas."""
    return render_template('categorias_marcas_productos.html')

@app.route('/ventas', methods=['GET'])
def get_ventas():
    """API para obtener todas las ventas con filtro de búsqueda."""
    search_term = request.args.get('q')
    ventas = obtener_ventas(search_term)
    return jsonify(ventas)

@app.route('/ventas-grafico', methods=['GET'])
def get_ventas_grafico():
    """API para obtener los datos agregados para el gráfico."""
    ventas_agregadas = obtener_ventas_agregadas_por_vendedor()
    return jsonify(ventas_agregadas)

@app.route('/agregar-venta', methods=['POST'])
def add_venta():
    """API para agregar una nueva venta."""
    venta_data = request.json
    if agregar_venta(venta_data):
        return jsonify({"success": True, "message": "Venta agregada con éxito."})
    else:
        return jsonify({"success": False, "message": "Error al agregar la venta."})

@app.route('/editar-venta', methods=['POST'])
def edit_venta():
    """API para editar una venta existente."""
    data = request.json
    id_venta = data.get('id_venta')
    if not id_venta:
        return jsonify({"success": False, "message": "ID de venta no proporcionado."})
    if editar_venta(id_venta, data):
        return jsonify({"success": True, "message": "Venta editada con éxito."})
    else:
        return jsonify({"success": False, "message": "Error al editar la venta."})

@app.route('/eliminar-venta', methods=['POST'])
def delete_venta():
    """API para eliminar una venta."""
    data = request.json
    id_venta = data.get('id_venta')
    if not id_venta:
        return jsonify({"success": False, "message": "ID de venta no proporcionado."})
    if eliminar_venta(id_venta):
        return jsonify({"success": True, "message": "Venta eliminada con éxito."})
    else:
        return jsonify({"success": False, "message": "Error al eliminar la venta."})

# Iniciar la aplicación
if __name__ == '__main__':
    app.run(debug=True)

