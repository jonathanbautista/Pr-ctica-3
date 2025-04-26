#Práctica 2: Desarrollo del mapa electrónico de la carretera
#Alumnos:
#Jonathan Bautista Cando ,, bk0008
#Jorge Veleriano Marín   ,, bq0063
#bk0008_bq0063

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk
import threading
import queue
import serial
import pyproj


# Función para transformar las coordenadas GGA a UTM: 
def transformar_gga_a_utm(latitud_gga, longitud_gga):
    # Convertir latitud y longitud a grados decimales
    latitud_decimal = float(latitud_gga[:2]) + float(latitud_gga[2:]) / 60
    longitud_decimal = -1 * (float(longitud_gga[:3]) + float(longitud_gga[3:]) / 60)

    # Definición de los sistemas de coordenadas WGS84 y UTM
    sistema_wgs84 = pyproj.CRS('EPSG:4326')
    sistema_utm = pyproj.CRS.from_epsg(32630)

    # Crear el transformador entre sistemas de coordenadas
    transformador = pyproj.Transformer.from_crs(sistema_wgs84, sistema_utm, always_xy=True)

    # Transformar las coordenadas
    easting, northing = transformador.transform(longitud_decimal, latitud_decimal)
    return easting, northing, '30T'

# Función para convertir las coordenadas UTM a píxeles en la imagen:
def convertir_utm_a_imagen(coordenadas_utm, imagen_objeto):
    x_utm, y_utm = coordenadas_utm
    
    esquina_noroeste = (446175.44, 4471052.89)  # Coordenadas UTM de la esquina superior izquierda
    esquina_sureste = (446573.82, 4470710.86)  # Coordenadas UTM de la esquina inferior derecha
    
    ancho_imagen, alto_imagen = imagen_objeto.size
    
    x_pixel = (x_utm - esquina_noroeste[0]) / (esquina_sureste[0] - esquina_noroeste[0]) * ancho_imagen
    y_pixel = (1 - (y_utm - esquina_sureste[1]) / (esquina_noroeste[1] - esquina_sureste[1])) * alto_imagen
    
    return x_pixel, y_pixel


# Función para dibujar un punto en la imagen:
def dibujar_punto(coordenadas_utm, imagen_actual):
    # Crear un objeto de dibujo en la imagen
    diseño = ImageDraw.Draw(imagen_actual)
    tamaño_punto = 3  # Tamaño del punto que se dibujará

    # Mapear las coordenadas UTM a las coordenadas de la imagen
    x_pixel, y_pixel = convertir_utm_a_imagen(coordenadas_utm, imagen_actual)

    # Dibujar un círculo rojo en la imagen
    diseño.ellipse([x_pixel - tamaño_punto, y_pixel - tamaño_punto, x_pixel + tamaño_punto, y_pixel + tamaño_punto], fill="red", outline="red")

    return imagen_actual

# Función para leer datos GPS desde el puerto serie 
def leer_gps(cola_datos, puerto_serial):
    while True:
        # Leer una línea de datos GPS desde el puerto
        linea_gps = puerto_serial.readline().decode('utf-8').strip()

        # Verificar si es una trama 'GPGGA'
        if 'GPGGA' in linea_gps:
            partes = linea_gps.split(',')
            print("Tramas recibidas:", partes)

            # Verificar que los datos de la latitud y la longitud sean válidos
            if len(partes) > 5 and partes[2] and partes[4]:
                latitud = partes[2]
                longitud = partes[4]

                # Conversión a UTM y poner las coordenadas en la cola
                easting, northing, zona = transformar_gga_a_utm(latitud, longitud)
                cola_datos.put((easting, northing))

# Función para actualizar la interfaz gráfica con los nuevos datos
def actualizar_grafico(ventana, cola_datos, imagen_base, etiqueta_imagen, ultimo_punto):
    try:
        while True:
            # Procesar todos los elementos en la cola
            easting, northing = cola_datos.get_nowait()
            nuevo_punto = (easting, northing)

            # Solo actualizar si el nuevo punto es diferente al último
            if nuevo_punto != ultimo_punto[0]:
                imagen_actualizada = dibujar_punto(nuevo_punto, imagen_base)
                mostrar_imagen(imagen_actualizada, etiqueta_imagen)
                ultimo_punto[0] = nuevo_punto  # Actualizar el último punto

    except queue.Empty:
        pass
    finally:
        # Llamar nuevamente a la función para actualizar la interfaz
        ventana.after(100, actualizar_grafico, ventana, cola_datos, imagen_base, etiqueta_imagen, ultimo_punto)

# Función para mostrar la imagen actualizada en la interfaz gráfica
def mostrar_imagen(imagen, etiqueta):
    imagen_tk = ImageTk.PhotoImage(imagen)
    etiqueta.configure(image=imagen_tk)
    etiqueta.image = imagen_tk

# Configuración inicial de la interfaz gráfica
ventana_principal = tk.Tk()
ventana_principal.title("Visualización de Coordenadas GPS")
 
# Cargar la imagen base sobre la cual se dibujarán los puntos
ruta_imagen = "Fotos/insia.png"
imagen_base = Image.open(ruta_imagen)
imagen_tk = ImageTk.PhotoImage(imagen_base)

# Crear la etiqueta donde se mostrará la imagen
etiqueta_imagen = ttk.Label(ventana_principal, image=imagen_tk)
etiqueta_imagen.pack()

# Configuración de la cola y el puerto serie COM7
cola_datos = queue.Queue()
puerto_serial = serial.Serial('COM7', 4800, timeout=1)

# Iniciar un hilo para leer los datos GPS
hilo_gps = threading.Thread(target=leer_gps, args=(cola_datos, puerto_serial), daemon=True)
hilo_gps.start()

# Variable para almacenar el último punto dibujado
ultimo_punto = [None]

# Iniciar la actualización de la interfaz gráfica
actualizar_grafico(ventana_principal, cola_datos, imagen_base, etiqueta_imagen, ultimo_punto)

# Ejecutar el bucle principal de la interfaz
ventana_principal.mainloop()
