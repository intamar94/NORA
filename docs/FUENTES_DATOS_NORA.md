# Fuentes de datos NORA

## Regla

NORA prioriza fuentes oficiales, mantiene la fuente asociada a cada observación y conserva incertidumbre/metadatos cuando el producto los ofrece.

## Núcleo global

| Dominio | Fuente principal | Uso |
|---|---|---|
| Óptico | Copernicus Sentinel-2 | vegetación, suelo, agua, cambios finos |
| Óptico histórico | USGS Landsat Collection 2 | series largas y cambios de superficie |
| Vegetación | NASA MODIS | NDVI, EVI, LAI, FPAR, GPP, albedo, ET |
| Clima | ECMWF/Copernicus ERA5 | temperatura, precipitación, viento, presión, radiación y atmósfera |
| Humedad suelo | NASA SMAP | humedad superficial y zona radicular |
| Agua superficial | EC JRC Global Surface Water | ocurrencia, estacionalidad y cambios de agua |
| Fuego | NASA FIRMS MODIS/VIIRS | focos activos y anomalías térmicas |
| Suelo | ISRIC SoilGrids | pH, carbono, textura, densidad y otras propiedades |
| Biodiversidad | GBIF | observaciones de especies y taxones |

## Reglas de confianza

- Sentinel/Landsat: aplicar máscaras de calidad y nubes antes de calcular índices.
- FIRMS: una detección de fuego no equivale automáticamente a un incendio; conservar confianza y contexto del píxel.
- ERA5: es reanálisis, no una medición local; conservar resolución y representatividad espacial.
- SoilGrids: son predicciones espaciales; conservar sus intervalos de incertidumbre cuando estén disponibles.
- GBIF: los registros son observaciones y tienen sesgo de muestreo; no deben tratarse como mapas completos de distribución.
- JRC Global Surface Water describe agua superficial; no debe interpretarse como agua subterránea.

## Acceso

La capa de conectores de NORA debe abstraer el proveedor. El motor no debe depender de una sola API. Cuando una fuente no esté disponible, NORA debe marcar la variable como no disponible y buscar una alternativa compatible, sin sustituir silenciosamente una fuente por otra.

## Fuentes investigadas

- Copernicus Data Space: acceso abierto y gratuito a datos Sentinel.
- USGS Landsat: archivo global y productos Collection 2.
- ECMWF ERA5: reanálisis global desde 1940 hasta el presente.
- ISRIC SoilGrids: mapas globales a 250 m y seis profundidades con incertidumbre.
- JRC Global Surface Water: historial de agua superficial 1984–2021 a partir de Landsat.
- NASA FIRMS: datos globales de fuego activo MODIS/VIIRS.
- GBIF: API de ocurrencias y descargas de biodiversidad.
