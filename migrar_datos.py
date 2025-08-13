import pandas as pd
import mysql.connector
import re
from rapidfuzz import fuzz
import os
import numpy as np

# ---------- CONFIGURACIÓN DE BASE DE DATOS ----------
DB_CONFIG = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'reporte'
}

ARCHIVO = 'Lista_Ventas_Detalle.csv'

# ---------- FUNCIONES AUXILIARES ----------
def nan_to_none(value):
    """Convierte NaN a None, que MySQL puede interpretar como NULL."""
    return None if pd.isna(value) else value

# ---------- FUNCIONES DE LIMPIEZA Y CLASIFICACIÓN (DE TU CÓDIGO ORIGINAL) ----------
def limpiar_nombre(texto):
    texto = str(texto).strip().lower()
    texto = re.sub(r'\s+', ' ', texto)
    texto = re.sub(r'[^a-z0-9áéíóúüñ\s]', ' ', texto)
    return texto.strip()

def clasificar_categoria(t):
    if "mouse" in t: return "Mouse"
    if any(k in t for k in ["laptop","notebook","bateria","pantalla","cargador","memoria para laptop","servicio a laptop"]):
        return "Laptop y accesorios"
    if any(k in t for k in ["tinta","cartucho","toner","impresora","cabezal","multifuncional"]):
        return "Impresoras y consumibles"
    if any(k in t for k in ["hdmi","vga","display port","usb","cable","adaptador","otg","patch","plug","utp"]):
        return "Cables y conectores"
    if any(k in t for k in ["memoria","ssd","disco","enclosure","caddy","flash","pendrive"]):
        return "Almacenamiento"
    if any(k in t for k in ["procesador","placa madre","case","gabinete","cooler","fuente","ram","motherboard"]):
        return "Componentes y hardware PC"
    if any(k in t for k in ["teclado","parlante","hub","mochila","funda","protector","kit de limpieza"]):
        return "Periféricos y accesorios"
    if any(k in t for k in ["camara","webcam","audifono","headset","microfono"]):
        return "Cámaras y audio"
    if any(k in t for k in ["licencia","office","windows","antivirus"]):
        return "Software y licencias"
    if any(k in t for k in ["reparacion","servicio","instalacion","mantenimiento"]):
        return "Servicios técnicos"
    return "Otros"

marca_keywords = {
    "Laptop y accesorios": ["hp","lenovo","asus","acer","dell","samsung","msi","gigabyte","razer","toshiba","huawei"],
    "Mouse": ["logitech","genius","hyperx","redragon","halion","teros","microsoft","razer","hp"],
    "Impresoras y consumibles": ["epson","canon","hp","brother","kodak"],
    "Cámaras y audio": ["logitech","philips","sony","jbl","xiaomi","anker"]
}
def detectar_marca(cat, nombre):
    t = nombre.lower()
    if cat in marca_keywords:
        for kw in marca_keywords[cat]:
            if kw in t: return kw.upper()
    for g in ["hp","lenovo","asus","acer","dell","logitech","canon","epson","brother","redragon","razer","samsung","msi"]:
        if g in t: return g.upper()
    return "OTROS"

# ---------- LÓGICA DE MIGRACIÓN ----------
def migrar_datos():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✅ Conexión a la base de datos para migración exitosa.")

        # Cargar el archivo CSV
        if not os.path.exists(ARCHIVO):
            raise FileNotFoundError(f"No encontré el archivo '{ARCHIVO}'")

        cols = [ 'fecha', 'documento', 'nro_doc', 'cont_cred', 'medio_pago',
                 'doc_cliente', 'cliente', 'telefono', 'observacion', 'moneda',
                 'articulos', 'dato_extra', 'cantidad', 'importe', 'tc',
                 'importe_soles', 'vendedor' ]
        df_ventas = pd.read_csv(ARCHIVO, skiprows=2, names=cols)

        # Pre-procesamiento de datos (similar a tu script)
        df_ventas['fecha'] = pd.to_datetime(df_ventas['fecha'], dayfirst=True, errors='coerce')
        df_ventas['cantidad'] = pd.to_numeric(df_ventas['cantidad'], errors='coerce')
        df_ventas['importe_soles'] = pd.to_numeric(df_ventas['importe_soles'], errors='coerce')
        
        # EL CAMBIO CRUCIAL: Añadir 'cliente' a la lista de columnas requeridas
        df_ventas = df_ventas.dropna(subset=['fecha', 'articulos', 'importe_soles', 'cliente'])
        
        # Diccionarios para evitar duplicados y guardar IDs
        clientes_db = {}
        productos_db = {}
        
        # Iterar sobre las filas del DataFrame para insertar en la DB
        print("Iniciando la migración de datos...")
        for index, row in df_ventas.iterrows():
            # Procesar el cliente
            doc_cliente = nan_to_none(row['doc_cliente'])
            if doc_cliente not in clientes_db:
                cursor.execute(
                    "INSERT INTO clientes (doc_cliente, cliente, telefono) VALUES (%s, %s, %s)",
                    (doc_cliente, nan_to_none(row['cliente']), nan_to_none(row['telefono']))
                )
                clientes_db[doc_cliente] = cursor.lastrowid
            id_cliente = clientes_db[doc_cliente]

            # Procesar el producto
            articulo_limpio = limpiar_nombre(nan_to_none(row['articulos']))
            if articulo_limpio not in productos_db:
                categoria = clasificar_categoria(articulo_limpio)
                marca = detectar_marca(categoria, articulo_limpio)
                cursor.execute(
                    "INSERT INTO productos (nombre_original, nombre_limpio, categoria, marca, dato_extra) VALUES (%s, %s, %s, %s, %s)",
                    (nan_to_none(row['articulos']), articulo_limpio, categoria, marca, nan_to_none(row['dato_extra']))
                )
                productos_db[articulo_limpio] = cursor.lastrowid
            id_producto = productos_db[articulo_limpio]

            # Insertar en la tabla de ventas
            cursor.execute(
                "INSERT INTO ventas (fecha, documento, nro_doc, cont_cred, medio_pago, observacion, moneda, tc, vendedor, id_cliente) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (nan_to_none(row['fecha']), nan_to_none(row['documento']), nan_to_none(row['nro_doc']), nan_to_none(row['cont_cred']), nan_to_none(row['medio_pago']), nan_to_none(row['observacion']), nan_to_none(row['moneda']), nan_to_none(row['tc']), nan_to_none(row['vendedor']), id_cliente)
            )
            id_venta = cursor.lastrowid
            
            # Insertar en la tabla de detalle_venta
            cursor.execute(
                "INSERT INTO detalle_venta (id_venta, id_producto, cantidad, importe, importe_soles) VALUES (%s, %s, %s, %s, %s)",
                (id_venta, id_producto, nan_to_none(row['cantidad']), nan_to_none(row['importe']), nan_to_none(row['importe_soles']))
            )

        conn.commit()
        print(f"✅ Migración completada. Se procesaron {len(df_ventas)} registros.")

    except mysql.connector.Error as err:
        print(f"Error en la migración a MySQL: {err}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            print("Cerrando la conexión a la base de datos.")

if __name__ == '__main__':
    migrar_datos()