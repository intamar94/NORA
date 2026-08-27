# NORA — arquitectura global

## Principio

NORA no está diseñada alrededor de un territorio. El territorio es una entrada libre al motor.

`zona → objetivo → variables necesarias → fuentes → ingesta → control de calidad → mapas → relaciones → robustez → hipótesis → comprobación del objetivo`

Alto Xingu es únicamente el piloto de validación del sistema.

## Entrada de zona

El motor debe aceptar:

- coordenadas / punto;
- bounding box;
- polígono GeoJSON;
- área administrativa;
- zona guardada previamente.

No se debe crear una tabla específica por territorio nuevo. Las observaciones nuevas deben entrar en el modelo común de NORA.

## Descubrimiento automático de variables

El registro `nora_variables` describe qué significa una variable. `nora_sources` identifica la fuente. `nora_source_capabilities` indica cómo puede obtenerse, cobertura, resolución, periodo y prioridad.

El motor debe escoger las mejores fuentes disponibles para cada variable y mantener trazabilidad hasta el resultado.

## Calidad

Cada variable debe pasar controles antes de llegar al motor de descubrimiento:

1. cobertura espacial;
2. cobertura temporal;
3. porcentaje de datos válidos;
4. valores fuera de rango;
5. duplicados;
6. coherencia temporal;
7. coherencia espacial;
8. incertidumbre de la fuente;
9. compatibilidad de resolución;
10. trazabilidad de origen.

Los datos que no pasan no desaparecen: quedan marcados y no pueden alimentar una conclusión de alta confianza.

## Mapeo

Cada zona genera capas por variable y periodo. Una capa conserva resolución, fechas, cantidad de celdas válidas, faltantes, estadísticas y fuente.

El mapa no debe mostrar valores inventados para rellenar huecos.

## Motor científico

Una correlación es solo una señal. NORA debe probar:

- retardos temporales;
- tendencias;
- estacionalidad;
- anomalías;
- consistencia entre subzonas;
- consistencia entre periodos;
- variables de confusión;
- sensibilidad a la fuente/resolución;
- validación fuera de muestra cuando sea posible.

Después puede crear una hipótesis exploratoria. Una hipótesis no se convierte automáticamente en descubrimiento.

## Criterio de finalización

NORA debe terminar una línea de investigación cuando:

- el objetivo está respaldado con la evidencia definida; o
- la evidencia es insuficiente y ya no hay una acción razonable disponible con los datos actuales.

En ambos casos debe explicar el motivo y guardar el siguiente paso.

## Estado del sistema

`nora_zone_jobs` representa el trabajo de una zona.

`nora_goal_runs` representa el objetivo y su estado.

`nora_quality_checks` guarda las comprobaciones de datos.

`nora_map_layers` guarda el inventario de capas calculadas.

Esto permite que Mando vea qué está haciendo NORA sin obligar al usuario a entrar en GitHub.
