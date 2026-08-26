# NORA — motor científico multidominio

## Objetivo
NORA debe permitir seleccionar cualquier área geográfica y construir un modelo espacial-temporal que combine variables ambientales, biológicas y humanas para detectar relaciones, anticipar cambios y generar hipótesis verificables.

## Caso inicial: agricultura + ecosistemas
Ejemplo: Eje Cafetero, Colombia.

Flujo:
1. Seleccionar AOI.
2. Construir inventario de variables disponibles y su calidad/cobertura temporal.
3. Integrar clima, agua, suelo, topografía, vegetación, uso del suelo, perturbaciones y observaciones.
4. Construir una línea base ecológica/productiva.
5. Relacionar condiciones con especies nativas, cultivos, invasoras y cambios temporales.
6. Generar mapas de aptitud/riesgo y escenarios, siempre con incertidumbre explícita.
7. Incorporar observaciones de campo y drones para validar/refinar el modelo.
8. Detectar anomalías y relaciones nuevas; separar correlación de hipótesis causal.
9. Proponer experimentos o nuevas mediciones que reduzcan incertidumbre.

## Variables prioritarias
- Clima: temperatura, precipitación, radiación, evapotranspiración, humedad atmosférica, extremos.
- Agua: agua superficial, humedad del suelo, disponibilidad y anomalías.
- Vegetación: NDVI, EVI, LAI, fenología, productividad, humedad y estructura.
- Suelo: propiedades disponibles, humedad, textura/profundidad cuando exista cobertura fiable.
- Terreno: elevación, pendiente, orientación y relieve.
- Cobertura: uso/cobertura del suelo y cambios.
- Perturbaciones: incendios, sequías, inundaciones, deforestación y fragmentación.
- Atmósfera: aerosoles y variables relevantes disponibles.
- Biodiversidad: especies nativas, cultivos, invasoras y observaciones de campo.
- Detección: Sentinel-1/2, Landsat, MODIS/VIIRS, sensores térmicos y, cuando proceda, hyperspectral/LiDAR.
- Drones: RGB/multiespectral/hiperespectral/LiDAR cuando existan datos de campo.

## Capacidades futuras
- Identificación de especies y posibles invasoras.
- Predicción de estrés y riesgo de cultivo.
- Recomendación de especies compatibles con condiciones locales.
- Detección temprana de anomalías.
- Simulación de escenarios.
- Descubrimiento de relaciones no obvias.
- Motor de hipótesis y experimentos.

## Regla científica
NORA nunca debe presentar una correlación como causalidad. Cada conclusión debe conservar sus fuentes, periodo, resolución, cobertura, calidad, incertidumbre y variables utilizadas.

## Arquitectura conceptual
OBSERVAR → INTEGRAR → RELACIONAR → DETECTAR → PREDECIR → EXPERIMENTAR → VALIDAR → APRENDER → DESCUBRIR.

El sistema debe ser multidominio desde la arquitectura, aunque el primer caso operativo sea agricultura/ecología.