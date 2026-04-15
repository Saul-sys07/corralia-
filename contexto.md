# Corralia v3 — Contexto del Proyecto

## Qué es
SaaS de gestión porcícola para el Rancho Yáñez en Atlacomulco, Estado de México.
Stack: Python + Streamlit + MySQL.
App en producción: https://corralia.streamlit.app/
Repositorio: https://github.com/Saul-sys07/corralia-

## Base de datos
- Servidor local: MySQL en `rancho_yanez`
- Producción: Railway MySQL
  - Host: monorail.proxy.rlwy.net
  - Port: 20771
  - Database: railway
  - User: root
- Fotos: Cloudinary (cloud: du617gti2)

## Tablas en la base de datos
- `chiqueros` — corrales con medidas, tipo (Comunal/Paridera/Semental) y zona (Parideras/Gestacion/Crecimiento)
- `lotes` — animales por corral con tipo_animal, estado_pie_cria, fecha_monta, fecha_parto_estimada
- `historial_movimientos` — todos los eventos: ENTRADA, TRASPASO, MUERTE, CAMBIO_ESTADO, VENTA, PARTO
- `alertas_sistema` — alertas automáticas
- `usuarios` — 9 usuarios con PIN, rol, primer_acceso
- `asistencia` — checador de entrada/salida con fotos en Cloudinary

## Estructura de archivos
```
app.py                    — entrada, login, routing por rol
config.py                 — constantes del negocio + credenciales
database.py               — conexiones MySQL (sin pool, conexión directa)
modulos/
  mapa.py                 — mapa por zonas con semáforo
  traspaso.py             — traspasos + muertes + cambio de etapa (3 tabs)
  reportes.py             — reportes Admin (5 tabs)
  configuracion.py        — registro animales + corrales (solo Admin)
  usuarios.py             — gestión de usuarios (solo Admin)
  checador.py             — entrada/salida con foto Cloudinary
  chiqueros.py            — CRUD + validación m²
  lotes.py                — animales, estados, traspasos
  movimientos.py          — historial + alertas + verificación celo
```

## Usuarios y roles
| PIN | Usuario | Rol | Acceso |
|-----|---------|-----|--------|
| 9302 | Saúl | admin | Todo |
| 1234 | Beyin | encargado_general | Todo operativo |
| PIN propio | Araceli | parideras | Solo Parideras |
| PIN propio | Miguel | crecimiento | Solo Crecimiento |
| PIN propio | Lauro | gestacion | Solo Gestación |
| PIN propio | Toña | parideras | Solo Parideras |
| PIN propio | Angel | crecimiento | Solo Crecimiento |
| PIN propio | Diego | ayudante_general | Solo checador |
| PIN propio | Manuel | ayudante_general | Solo checador |

## Animales y ciclo de vida
Tipos: Semental, Pie de Cría, Crías, Destete, Desarrollo, Engorda, Herniados, Desecho
Estados Pie de Cría: Disponible → Cubierta → Gestación → Parida → Desecho
- Alerta automática a los 21 días para verificar si quedó gestante
- Gestación = 114 días desde fecha de monta
- Foto de monta obligatoria al registrar Cubierta

## Zonas del rancho
- Parideras: paridera 1-11 (madres pariendo + crías)
- Gestación: zona gestantes 1-10 + semental 1
- Crecimiento: chiquero 1-8 (destete, desarrollo, engorda)

## Lo que ya funciona en producción
- Login con PIN + primer acceso (trabajador crea su propio PIN)
- Mapa por zonas con semáforo de capacidad
- Traspasos con carrito multi-destino
- Cambio de etapa sin traspaso físico
- Registro de muertes con causas predefinidas y foto
- Estados pie de cría + alertas de celo a los 21 días
- Checador de asistencia con foto (Cloudinary)
- Historial con quién hizo qué y cuándo
- Autorefresh cada 60s en el mapa
- Reportes Admin: Pie de Cría, Próximos Partos, Alertas, Historial, Asistencia

## Pendiente de construir
### Inmediato
1. Ventas — sistema complejo con CRM de clientes
2. Cambio manual de estado pie de cría
3. PDF reporte mensual para el papá
4. Historial clínico y vacunas (faltan parámetros de Araceli)

### Mediano plazo
5. Módulo económico — nómina, ingresos, gastos
6. Almacén — inventario de insumos y alimento

## Lógica de ventas (diseñada, pendiente de código)
- Foto de báscula OBLIGATORIA
- Clientes identificados por número de teléfono (único)
- Cliente casado a trabajador que lo consiguió
- Tipos de cliente y comisión:
  - Nuevo: $2/kg (labor de venta activa)
  - Retenido: $1/kg (cliente fijo, ya conoce el camino)
  - Recuperado: $1.50/kg (eventual, periodo de gracia 1 año)
- Ventas de Saúl o papá: sin comisión
- Precio ejemplo: $48/kg en pie → $46 al rancho + $2 al trabajador
- Animales que se venden: principalmente Engorda, ocasionalmente Destete
- Se puede vender por unidades o por lote

## Bugs conocidos resueltos
- Bug #1: Tarjetas duplicadas en mapa → índice único (id_chiquero, tipo_animal)
- Bug #2: Traspaso vaciaba todo el corral → mover_animales() opera por tipo
- Bug #3: Pie de cría en corrales comunales → validar_ingreso() en chiqueros.py
- Pool exhausted en Railway → cambiado a conexión directa sin pool

## Notas importantes
- La app corre lento en Streamlit Cloud plan gratuito — es normal
- Las fotos de asistencia y muertes van a Cloudinary carpeta corralia/
- El autorefresh está solo en el mapa (60s) y reportes, no en todas las páginas
- git push = redeploy automático en Streamlit Cloud en ~1 minuto
- Comando para correr local: python -m streamlit run app.py