"""
config.py — Corralia v3
Constantes del negocio y configuración de entorno.
Una sola fuente de verdad para valores que se usan en múltiples módulos.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─── Base de datos ────────────────────────────────────────────────────────────
# ─── Base de datos ────────────────────────────────────────────────────────────
DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "monorail.proxy.rlwy.net"),
    "port":     int(os.getenv("DB_PORT", "20771")),
    "database": os.getenv("DB_NAME",     "railway"),
    "user":     os.getenv("DB_USER",     "root"),
    "password": os.getenv("DB_PASSWORD", "nULjTZmRBHfDIHPrEkgASAOXtsUPCCdf"),
    "charset":  "utf8mb4",
    "autocommit": False,
}

# ─── Usuarios / roles ─────────────────────────────────────────────────────────
USUARIOS = {
    "saul":  {"nombre": "Saúl",  "rol": "admin"},
    "beyin": {"nombre": "Beyin", "rol": "encargado"},
}

ROL_ADMIN      = "admin"
ROL_ENCARGADO  = "encargado"

# ─── Tipos de animal ──────────────────────────────────────────────────────────
# Orden importa: refleja el ciclo de vida de crías
TIPOS_ANIMAL = [
    "Semental",
    "Pie de Cría",
    "Crías",
    "Destete",
    "Desarrollo",
    "Engorda",
    "Herniados",
    "Desecho",
]

# Animales que van en chiquero exclusivo (1 por corral, no comunal)
TIPOS_EXCLUSIVOS = {"Semental", "Pie de Cría"}

# Animales que siempre se destacan en el dashboard (consumen sin producir)
TIPOS_CRITICOS = {"Herniados", "Desecho"}

# ─── Estados del Pie de Cría ─────────────────────────────────────────────────
ESTADOS_PIE_CRIA = [
    "Disponible",
    "Cubierta",
    "Gestación",
    "Parida",
    "Desecho",
]

# Transiciones válidas (estado_actual → [estados_posibles])
TRANSICIONES_PIE_CRIA = {
    "Disponible": ["Cubierta"],
    "Cubierta":   ["Gestación", "Disponible"],   # Disponible si no quedó gestante
    "Gestación":  ["Parida"],
    "Parida":     ["Disponible", "Desecho"],
    "Desecho":    [],
}

# Estado que requiere foto de monta como evidencia obligatoria
ESTADO_REQUIERE_FOTO = "Cubierta"

# ─── Ciclo reproductivo ───────────────────────────────────────────────────────
DIAS_GESTACION = 114          # 3 meses, 3 semanas y 3 días
DIAS_CONFIRMACION_GESTACION = 21  # Sin celo a los 21 días → confirmar gestación

# ─── Capacidad de chiqueros (m² por animal según etapa) ──────────────────────
# Fuente: mapa_corralia_v3.html — reglas de chiqueros
M2_POR_ANIMAL = {
    "Crías":      0.25,   # 0.20–0.30 m² (usamos el promedio)
    "Destete":    0.25,
    "Desarrollo": 0.45,   # 0.40–0.50 m²
    "Engorda":    0.82,   # 0.65–1.00 m²
    "Semental":   3.00,   # Chiquero exclusivo
    "Pie de Cría":1.80,  # Chiquero exclusivo (área real de parideras)
    "Herniados":  0.82,   # Igual que engorda
    "Desecho":    0.82,
}

# Umbral de alerta de capacidad (% de ocupación)
ALERTA_CAPACIDAD_AMARILLO = 0.90   # 90% → amarillo
ALERTA_CAPACIDAD_ROJO     = 1.00   # 100%+ → rojo

# ─── Tipos de chiquero ────────────────────────────────────────────────────────
TIPOS_CHIQUERO = ["Comunal", "Paridera", "Semental"]

# Qué tipos de animal pueden entrar a cada tipo de chiquero
ANIMALES_PERMITIDOS_EN = {
    "Comunal":   {"Crías", "Destete", "Desarrollo", "Engorda", "Herniados", "Desecho"},
    "Paridera":  {"Pie de Cría", "Crías"},  # Madre + lechones juntos hasta el destete
    "Semental":  {"Semental"},
}

# ─── Eventos de historial ─────────────────────────────────────────────────────
TIPOS_EVENTO = ["ENTRADA", "PARTO", "TRASPASO", "VENTA", "MUERTE", "CAMBIO_ESTADO"]

# ─── Tipos de alerta ─────────────────────────────────────────────────────────
TIPOS_ALERTA = ["CAPACIDAD", "ESTADO_ANIMAL", "FOTO_PENDIENTE", "PARTO_PROXIMO"]

# ─── Cloudinary (fotos de asistencia) ────────────────────────────────────────
CLOUDINARY_CONFIG = {
    "cloud_name": os.getenv("CLOUDINARY_CLOUD_NAME", "du617gti2"),
    "api_key":    os.getenv("CLOUDINARY_API_KEY",    "487483857463937"),
    "api_secret": os.getenv("CLOUDINARY_API_SECRET", "8ObYI8HkkWM3baNEj8t1WJhTKC0"),
}