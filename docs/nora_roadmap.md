# NORA — hoja de ruta de plataforma

NORA es un motor general de análisis científico espacio-temporal. Agricultura es un caso de uso inicial, no su límite.

## Objetivo
Convertir datos heterogéneos en conocimiento accionable y descubrimiento: **observar → integrar → comparar → modelar → detectar anomalías → formular hipótesis → comprobar → aprender**.

## Módulos de dominio
- Agricultura y cultivos
- Bosques y reforestación
- Biodiversidad, fauna y hábitats
- Agua y cuencas
- Suelo y degradación
- Clima y microclimas
- Incendios y perturbaciones
- Enfermedades y plagas
- Ecosistemas acuáticos
- Entornos urbanos
- Observación terrestre
- Energía y recursos
- Interacciones biológicas
- Campo personalizado

## Variables y fuentes
La arquitectura debe aceptar capas satelitales, meteorológicas, topográficas, hidrológicas, de cobertura/uso del suelo, biodiversidad y sensores de campo/dron. Cada variable debe conservar fuente, periodo, resolución, unidad, cobertura, calidad y método de procesamiento.

No se incorporan variables solo por volumen: cada nueva variable debe demostrar cobertura, calidad y utilidad analítica.

## Selección territorial
El usuario puede dibujar/seleccionar un área. NORA crea un perfil espacio-temporal y permite comparar zonas, periodos y escenarios.

## Modo ecosistema primero
Antes de recomendar una intervención, NORA evalúa si existe una solución compatible con las condiciones naturales del territorio. En restauración/productividad prioriza especies nativas y diversidad funcional cuando la evidencia lo respalda. No optimiza una única métrica a costa del ecosistema.

## Agricultura
Evaluar compatibilidad territorio-especie, cultivos, productividad, agua, suelo, clima, riesgos, invasoras y escenarios futuros. Identificar cambios mediante satélite y, cuando sea necesario, priorizar inspecciones de dron/sensores.

## Energía
Buscar ubicaciones donde el recurso energético exista naturalmente y pueda aprovecharse con mínimo impacto. Comparar solar, viento, hidráulica, biomasa sostenible y otras hipótesis. La función objetivo debe incluir recurso + estabilidad + infraestructura + restricciones ambientales + impacto, no solo energía bruta.

## Sistema satélite → dron → sensor
1. Satélite/modelo detecta un cambio o anomalía.
2. NORA calcula qué observación adicional tiene mayor valor informativo.
3. Prioriza puntos para dron/sensor.
4. La observación de mayor resolución confirma, refuta o matiza la hipótesis.
5. NORA actualiza el modelo y registra el resultado.

## Zona inexplorada / inconclusa
Cada dominio debe mantener una cola de:
- evidencia insuficiente;
- resultados contradictorios;
- zona poco estudiada;
- relación desconocida;
- anomalía;
- hipótesis de NORA.

Cada elemento incluye evidencia, variables, incertidumbre, posibles explicaciones, datos faltantes y prueba propuesta.

## Descubrimiento científico
NORA puede buscar patrones temporales, espaciales y multivariables que no estén explicados por modelos conocidos. Un patrón solo se eleva como **anomalía**; nunca como descubrimiento confirmado sin validación independiente.

Debe distinguir estrictamente:
**dato observado → correlación → hipótesis → predicción → validación → conocimiento confirmado**.

## Resultados sorprendentes, pero verificables
La optimización de NORA debe favorecer descubrimientos que sean simultáneamente:
- inesperados;
- reproducibles;
- explicables o investigables;
- útiles;
- compatibles con las restricciones del entorno.

No se busca producir respuestas llamativas: se busca encontrar relaciones que merezcan ser comprobadas.
