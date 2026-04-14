"""
config.py - Corralia v3
Constantes del negocio y configuracion de entorno.
Funciona tanto local (con .env) como en Streamlit Cloud (con st.secrets).
"""

import os
from dotenv import load_dotenv

load_dotenv()

def _cfg(key, default=""):
    """Lee primero de st.secrets (Streamlit Cloud), luego de os.getenv (local)."""
    try:
        import streamlit as st
        return st.secrets[key]
    except Exception:
        return os.getenv(key, default)

# Base de datos
DB_CONFIG = {
    "host":       _cfg("DB_HOST",     "monorail.proxy.rlwy.net"),
    "port":       int(_cfg("DB_PORT", "20771")),
    "database":   _cfg("DB_NAME",     "railway"),
    "user":       _cfg("DB_USER",     "root"),
    "password":   _cfg("DB_PASSWORD", "nULjTZmRBHfDIHPrEkgASAOXtsUPCCdf"),
    "charset":    "utf8mb4",
    "autocommit": False,
}

# Cloudinary
CLOUDINARY_CONFIG = {
    "cloud_name": _cfg("CLOUDINARY_CLOUD_NAME", "du617gti2"),
    "api_key":    _cfg("CLOUDINARY_API_KEY",    "487483857463937"),
    "api_secret": _cfg("CLOUDINARY_API_SECRET", "8ObYI8HkkWM3baNEj8t1WJhTKC0"),
}

# Usuarios / roles
ROL_ADMIN     = "admin"
ROL_ENCARGADO = "encargado"

# Tipos de animal
TIPOS_ANIMAL = [
    "Semental", "Pie de Cría", "Crías", "Destete",
    "Desarrollo", "Engorda", "Herniados", "Desecho",
]

TIPOS_EXCLUSIVOS = {"Semental", "Pie de Cría"}
TIPOS_CRITICOS   = {"Herniados", "Desecho"}

# Estados del Pie de Cría
ESTADOS_PIE_CRIA = ["Disponible", "Cubierta", "Gestación", "Parida", "Desecho"]

TRANSICIONES_PIE_CRIA = {
    "Disponible": ["Cubierta"],
    "Cubierta":   ["Gestación", "Disponible"],
    "Gestación":  ["Parida"],
    "Parida":     ["Disponible", "Desecho"],
    "Desecho":    [],
}

ESTADO_REQUIERE_FOTO = "Cubierta"

# Ciclo reproductivo
DIAS_GESTACION              = 114
DIAS_CONFIRMACION_GESTACION = 21

# Capacidad m² por animal
M2_POR_ANIMAL = {
    "Crías":       0.25,
    "Destete":     0.25,
    "Desarrollo":  0.45,
    "Engorda":     0.82,
    "Semental":    3.00,
    "Pie de Cría": 1.80,
    "Herniados":   0.82,
    "Desecho":     0.82,
}

ALERTA_CAPACIDAD_AMARILLO = 0.90
ALERTA_CAPACIDAD_ROJO     = 1.00

# Tipos de chiquero
TIPOS_CHIQUERO = ["Comunal", "Paridera", "Semental"]

ANIMALES_PERMITIDOS_EN = {
    "Comunal":  {"Crías", "Destete", "Desarrollo", "Engorda", "Herniados", "Desecho"},
    "Paridera": {"Pie de Cría", "Crías"},
    "Semental": {"Semental"},
}

# Eventos e historial
TIPOS_EVENTO = ["ENTRADA", "PARTO", "TRASPASO", "VENTA", "MUERTE", "CAMBIO_ESTADO"]
TIPOS_ALERTA = ["CAPACIDAD", "ESTADO_ANIMAL", "FOTO_PENDIENTE", "PARTO_PROXIMO"]