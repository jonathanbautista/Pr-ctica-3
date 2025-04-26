#Práctica 3: Integración del sistema de aviso al conductor 
#Alumnos:
#Jonathan Bautista Cando , bk0008
#Jorge Veleriano Marín   , bq0063
#bk0008_bq0063

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk
import threading
import queue
import serial
import pyproj
import time
import math

# -------- TRANSFORMACIONES Y UTILIDADES --------
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

def distancia(p1, p2):
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])

def calcular_velocidad(punto_anterior, punto_actual, tiempo_anterior, tiempo_actual):
    dist_metros = distancia(punto_anterior, punto_actual)
    tiempo_segundos = tiempo_actual - tiempo_anterior
    if tiempo_segundos == 0:
        return 0
    velocidad_m_s = dist_metros / tiempo_segundos
    return velocidad_m_s * 3.6  # km/h

# -------- MAPA Y LÓGICA DE VELOCIDAD --------
mapa_velocidades = []

def cargar_mapa_velocidades(ruta_mapa):
    with open(ruta_mapa, 'r') as archivo:
        for linea in archivo:
            partes = linea.strip().split()
            if len(partes) == 3:
                norte = float(partes[0])
                este = float(partes[1])
                v_max = float(partes[2])
                mapa_velocidades.append(((este, norte), v_max))

def obtener_velocidad_maxima(posicion_actual):
    distancia_min = float('inf')
    velocidad_limite = 0
    for posicion_mapa, v_max in mapa_velocidades:
        dist = distancia(posicion_actual, posicion_mapa)
        if dist < distancia_min:
            distancia_min = dist
            velocidad_limite = v_max
    return velocidad_limite

# -------- INTERFAZ Y DIBUJO --------
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

# Función para mostrar la imagen actualizada en la interfaz gráfica
def mostrar_imagen(imagen, etiqueta):
    imagen_tk = ImageTk.PhotoImage(imagen)
    etiqueta.configure(image=imagen_tk)
    etiqueta.image = imagen_tk

def actualizar_etiquetas(velocidad_actual, limite, etiqueta_estado, etiqueta_velocidad):
    texto_vel = f"Velocidad actual: {velocidad_actual:.1f} km/h (Límite: {limite:.1f})"
    etiqueta_velocidad.config(text=texto_vel)
    
    if velocidad_actual < limite * 0.9:
        etiqueta_estado.config(text="VELOCIDAD OK", background="green")
    elif velocidad_actual <= limite * 1.1:
        etiqueta_estado.config(text="VELOCIDAD MODERADA", background="yellow")
    else:
        etiqueta_estado.config(text="¡EXCESO DE VELOCIDAD!", background="red")

# -------- PROCESAMIENTO GPS --------
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
                cola_datos.put((easting, northing, time.time()))

# Función para actualizar la interfaz gráfica con los nuevos datos
def actualizar_grafico(ventana, cola_datos, imagen_base, etiqueta_imagen, ultimo_punto, etiqueta_estado, etiqueta_velocidad):
    try:
        while True:
            # Procesar todos los elementos en la cola
            easting, northing, tiempo_actual = cola_datos.get_nowait()
            nuevo_punto = (easting, northing)

            # Solo actualizar si el nuevo punto es diferente al último
            if ultimo_punto[0] is not None:
                velocidad = calcular_velocidad(ultimo_punto[0], nuevo_punto, ultimo_punto[1], tiempo_actual)
                limite = obtener_velocidad_maxima(nuevo_punto)
                actualizar_etiquetas(velocidad, limite, etiqueta_estado, etiqueta_velocidad)
            imagen_actualizada = dibujar_punto(nuevo_punto, imagen_base)
            mostrar_imagen(imagen_actualizada, etiqueta_imagen)
            ultimo_punto[0] = nuevo_punto
            ultimo_punto[1] = tiempo_actual

    except queue.Empty:
        pass
    finally:
        # Llamar nuevamente a la función para actualizar la interfaz
        ventana.after(100, actualizar_grafico, ventana, cola_datos, imagen_base, etiqueta_imagen, ultimo_punto, etiqueta_estado, etiqueta_velocidad)


# -------- INICIO DE LA APLICACIÓN --------
# Configuración inicial de la interfaz gráfica
ventana_principal = tk.Tk()
ventana_principal.title("Visualización de Coordenadas GPS + Control de Velocidad")
 
# Cargar la imagen base sobre la cual se dibujarán los puntos
ruta_imagen = "Fotos/insia.png"
imagen_base = Image.open(ruta_imagen)
imagen_tk = ImageTk.PhotoImage(imagen_base)

# Crear la etiqueta donde se mostrará la imagen
etiqueta_imagen = ttk.Label(ventana_principal, image=imagen_tk)
etiqueta_imagen.pack()

# Cargar mapa de velocidades
cargar_mapa_velocidades('mapa_referenciaINSIA.txt')

# Etiquetas para estado y velocidad
etiqueta_estado = tk.Label(ventana_principal, text="Estado", width=40, background="gray")
etiqueta_estado.pack()
etiqueta_velocidad = tk.Label(ventana_principal, text="Velocidad actual: ", width=40)
etiqueta_velocidad.pack()

# Configuración de la cola y el puerto serie COM7
cola_datos = queue.Queue()
puerto_serial = serial.Serial('COM7', 4800, timeout=1)

# Iniciar un hilo para leer los datos GPS
hilo_gps = threading.Thread(target=leer_gps, args=(cola_datos, puerto_serial), daemon=True)
hilo_gps.start()

# Variable para almacenar el último punto dibujado
ultimo_punto = [None, None]

# Iniciar la actualización de la interfaz gráfica
actualizar_grafico(ventana_principal, cola_datos, imagen_base, etiqueta_imagen, ultimo_punto, etiqueta_estado, etiqueta_velocidad)

# Ejecutar el bucle principal de la interfaz
ventana_principal.mainloop()
