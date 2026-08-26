# NORA — Sistema Tierra ampliado

## Objetivo
NORA no debe limitarse a correlacionar dos variables. Debe observar el sistema como una red de procesos y buscar dónde, cuándo y bajo qué condiciones aparecen relaciones reproducibles.

## Dominios
- Vegetación: NDVI, LAI, FPAR, GPP, fenología.
- Agua: precipitación, evapotranspiración, PET, humedad superficial, humedad radicular, escorrentía, agua superficial.
- Energía: radiación solar superficial, temperatura de superficie día/noche, albedo.
- Atmósfera: temperatura, punto de rocío, VPD, viento, presión, nubosidad, altura y profundidad óptica de nubes.
- Química atmosférica: CO, NO2, CH4 y aerosoles.
- Fuego: área quemada.
- Suelo: pH, carbono orgánico, arena, arcilla y profundidad.
- Cobertura terrestre: clases de cobertura y cambios.

## Fuentes principales
- ERA5-Land: columna vertebral física de agua, energía, atmósfera y suelo.
- MODIS: vegetación, temperatura de superficie, ET, GPP, albedo y aerosoles.
- Sentinel-5P/TROPOMI: nubes y composición atmosférica.
- GPM IMERG: precipitación independiente para validación cruzada.
- SMAP: humedad superficial y de zona radicular.
- SoilGrids: contexto edáfico estático.

## Principio temporal
Las variables se conservan con su resolución nativa cuando es útil, pero se genera una capa mensual común para descubrimiento multivariable. NORA no debe rellenar silenciosamente periodos en los que una misión todavía no existía.

## Comparación espacial
Alto Xingu es el laboratorio inicial. Se registran además cajas comparativas exploratorias para Amazonia occidental, Cerrado, Pantanal, Congo y Borneo. Son cajas de benchmark, no límites hidrológicos oficiales.

## Motor de descubrimiento
1. Detectar anomalías espaciales.
2. Buscar retardos temporales.
3. Controlar estacionalidad y tendencia.
4. Comparar regiones con condiciones ambientales similares.
5. Buscar interacciones entre variables, no solo pares.
6. Generar hipótesis con evidencia y nivel de incertidumbre.
7. Intentar replicar el patrón en otra región o periodo.
8. Solo elevar una hipótesis cuando supera validaciones independientes.

## Regla científica
Una correlación es una señal, no una causa. NORA debe separar explícitamente asociación, evidencia temporal, replicación y causalidad.
