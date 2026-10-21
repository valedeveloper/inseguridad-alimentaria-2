# Guía para la documentación

Resumen del funcionamiento del sistema, de las decisiones tomadas y de dónde está la información de cada sección del README final (sección 24 del enunciado). Las cifras citadas están verificadas con código sobre los datos reales.

## 1. Qué hace el sistema

Integra dos fuentes para estudiar la inseguridad alimentaria de los hogares colombianos:

| Fuente | Qué aporta | Cómo entra |
|---|---|---|
| ECV 2025 (DANE) | Hogares: territorio, servicios, choques, estrategias, ingreso y probabilidad FIES | 3 CSV que cada integrante descarga en `data/raw/ecv/` |
| EVA 2024–2025 (UPRA) | Producción agrícola por municipio, cultivo y período | API Socrata de datos.gov.co (`uejq-wxrr`), sin autenticación |

Flujo de una ejecución (DAG de Airflow con 12 tareas):

1. **Extracción.** Las dos fuentes se copian a un lote propio de la corrida (`data/batches/<id>/`), con su sha256. La API se descarga paginada y se concilia con su conteo oficial.
2. **Validación cruda.** Una compuerta de Great Expectations por fuente. Si falla una regla crítica, la corrida se detiene.
3. **Transformación.** Solo cuando ambas compuertas pasan. La ECV usa la misma lógica de la primera entrega. EVA se agrega a departamento × cultivo × año y se aplica la canasta de cultivos.
4. **Modelo e integración.** Se construyen las dimensiones y los hechos, y se cruzan ECV y EVA por departamento.
5. **Validación de preparados.** Tercera compuerta de Great Expectations, antes de cargar.
6. **Carga.** Las 11 tablas del modelo dimensional van a PostgreSQL en una sola transacción (`TRUNCATE` + `INSERT`), y se recrean las 8 vistas analíticas.

## 2. Mapa del README (sección 24 del enunciado)

| # | Sección | Fuente en el repositorio | Estado |
|---|---|---|---|
| 1 | Problema y objetivo | README actual, sección 1 | Listo |
| 2 | Línea base y enlace a la primera entrega | README actual, sección 2 | Listo |
| 3 | Estado de R1–R5 | README actual, sección 3. Las vistas R1–R5 reproducen exactamente la primera entrega | Listo |
| 4 | R6 y R7 | README actual, sección 4 | Listo |
| 5 | Fuente primaria y API | [`notebooks/hallazgos_perfilamiento.md`](../notebooks/hallazgos_perfilamiento.md) §1–2; [`data/raw/README.md`](../data/raw/README.md) | Redactar |
| 6 | Valor analítico de la API | Este documento, sección 3 (R6 y R7 no son posibles solo con la ECV) | Redactar |
| 7 | Arquitectura | Este documento, sección 1. **Falta el diagrama de arquitectura** | Pendiente |
| 8 | Hallazgos del perfilamiento | [`notebooks/hallazgos_perfilamiento.md`](../notebooks/hallazgos_perfilamiento.md); notebooks 01 y 02 | Listo |
| 9 | Riesgos y reglas de calidad | [`docs/reglas_calidad.md`](reglas_calidad.md) §1–5 y §8 | Listo |
| 10 | Diseño de Great Expectations y trazabilidad | `src/calidad/`; cada expectativa lleva su ID de regla; reportes en `data/batches/<id>/calidad/` | Redactar |
| 11 | Validación cruda de ambas fuentes | Compuertas 1 y 2 en `reglas_calidad.md` §3–4 | Redactar |
| 12 | Transformación y contrato de integración | Este documento, sección 4; `src/ecv/`, `src/eva/` | Redactar |
| 13 | Modelo dimensional refinado | [`docs/modelo_dimensional.dbml`](modelo_dimensional.dbml), [`sql/create_tables.sql`](../sql/create_tables.sql); decisiones en la sección 3 | Redactar |
| 14 | Validación de preparados | Compuerta 3 en `reglas_calidad.md` §5 | Redactar |
| 15 | Warehouse y carga | `src/carga.py`; `sql/`; [`docs/orquestacion.md`](orquestacion.md) §6 | Redactar |
| 16 | DAG e interfaces de tareas | [`docs/orquestacion.md`](orquestacion.md) §1–3 | Listo |
| 17 | Fallas y reintentos | [`docs/orquestacion.md`](orquestacion.md) §4 | Listo |
| 18 | Evidencia de corrida exitosa (test A) | Capturas de Airflow | **Pendiente** (ejecutar) |
| 19 | Evidencia de falla controlada (test B) | Capturas de Airflow + `compuerta_2.json` | **Pendiente** (ejecutar) |
| 20 | Re-ejecución segura (test C) | Estrategia en `orquestacion.md` §6; capturas antes y después | **Pendiente** (ejecutar) |
| 21 | Dashboard | [`docs/guia_dashboard.md`](guia_dashboard.md) | Pendiente (dashboard) |
| 22 | Trazabilidad requerimiento → KPI y de punta a punta | Armar con las vistas de `guia_dashboard.md` §2 y las reglas | **Pendiente** |
| 23 | Instalación y ejecución | README actual ("Despliegue"); `orquestacion.md` §6; `.env.example` | Redactar |
| 24 | Supuestos y limitaciones | Este documento, sección 6 | Redactar |
| 25 | Integrantes y responsabilidades | Equipo | Pendiente |

## 3. Decisiones tomadas

| Tema | Decisión | Justificación |
|---|---|---|
| Fuente API | EVA de la UPRA, vía la API Socrata de datos.gov.co | Fuente oficial, pública, con código DIVIPOLA para integrar con la ECV y años 2024 y 2025 |
| R6 | Diversidad de cultivos alimentarios 2025 por departamento frente a la prevalencia FIES | Contexto agrícola territorial que la ECV no tiene |
| R7 | % de cultivos comparables cuya producción cayó entre 2024 y 2025 frente a la prevalencia | Añade la dimensión temporal de la oferta agrícola |
| Prevalencia | `Σ(FEX_C × PROB_IAMG) / Σ(FEX_C)` sobre hogares con FIES válido | Igual que la primera entrega. Reproduce el 21,1 % del DANE, que la define como "proporción de hogares" |
| Base del código | Se reutilizan los módulos de la primera entrega (ECV) y el patrón de lotes con sha256 | El enunciado pide complementar. Los resultados son idénticos a la primera entrega |
| Integración | Por código DIVIPOLA de departamento. El año no es llave (la ECV es solo de 2025) | La ECV no permite estimar por municipio (634 municipios, mediana 67 hogares) |
| Bogotá | Indicadores agrícolas nulos ("sin dato"), nunca 0 | EVA no tiene datos de Bogotá (16,8 % de los hogares del país) |
| Nivel de comparación | Por cultivo (160), no por código de desagregación (187) | La diversidad cuenta especies, no variedades, y no depende de cambios de código |
| Canasta | 139 de 160 cultivos, anclada en la lista oficial de alimentos de la ECV (pregunta P3204) | UPRA, FAO y DANE-COICOP no separan cultivos alimentarios. P3204 es la definición de alimento de la misma encuesta. Archivo: `config/canasta_cultivos.csv` |
| Excepciones de la canasta | Maíz, soya y palma entran aunque parte vaya a alimento animal o industria. Quinua como "otros granos". Fuera: medicinales según EVA, categorías residuales y "Chiraran - albahaca" (duplicado de Albahaca) | No se pueden separar por cultivo; se declaran explícitamente |
| Valores repetidos 2024 = 2025 | Se reportan como limitación, sin regla | Cerca del 19 % de los pares municipio-cultivo son idénticos; no se puede distinguir estabilidad de arrastre |
| Baja cobertura | Advertencia (A3) si el departamento tiene menos de 15 cultivos comparables | Con menos de 15, un solo cultivo mueve el % en descenso más de 6,7 puntos. Hoy: Guaviare |
| Área cosechada > sembrada | No es error; no se valida | La definición de la UPRA lo permite (6.950 registros válidos) |
| Modelo dimensional | Se conserva el modelo de hogares. Se agregan `dim_departamento` (conformada con `dim_geografia`, sin llave foránea física), `dim_cultivo`, `fact_produccion_agricola` (departamento × cultivo × año, los 160 cultivos con `en_canasta`) y dos hechos consolidados (`fact_variacion_produccion` y `fact_indicadores_departamento`) | Un hecho por grano. Los resultados de R6 y R7 se validan en la compuerta 3 antes de cargar. El año es una dimensión degenerada (solo 2 valores) |
| Reglas de calidad | 19 reglas: 16 críticas y 3 advertencias, sin informativas | Se priorizaron las que protegen los requerimientos. Las descartadas están justificadas en `reglas_calidad.md` §8 |
| Test B | Registro duplicado en la extracción de la API → la regla C7 detiene el pipeline | Falla determinista, fácil de activar (parámetro `falla_controlada`) y fácil de explicar |
| Carga | `TRUNCATE` + `INSERT` de las 11 tablas en una transacción | Las fuentes son fotos completas. Re-ejecutar deja los mismos datos y una falla revierte todo |
| Datos entre tareas | Parquet dentro del lote; por XCom solo viaja la ruta | El enunciado prohíbe mover datasets por XCom. Parquet conserva tipos y nulos |
| Executor de Airflow | LocalExecutor (sin Celery, Redis ni worker) | Pasa de 8 a 6 contenedores y reduce el uso de memoria. Suficiente para un DAG manual |
| Reintentos | Solo `extraer_eva` (2 cada 5 min) y `cargar` (2 cada 1 min). Los errores deterministas nunca se reintentan | El enunciado rechaza reintentos genéricos |

## 4. Contrato de integración (resumen)

| Elemento | ECV | EVA | Resultado |
|---|---|---|---|
| Llave | `P1_DEPARTAMENTO` normalizado con `zfill(2)` | `c_digo_dane_departamento` (2 dígitos) | Código DIVIPOLA de departamento |
| Grano de origen | Hogar | Municipio × código de cultivo × período | Ambas se llevan a departamento |
| Cardinalidad | 1 fila por departamento (agregando hogares) | 1 fila por departamento (agregando cultivos) | 1:1; la unión no toca los hogares |
| Cobertura | 33 departamentos | 32 (sin Bogotá) | 33 filas; Bogotá con agrícolas nulos |
| Controles | Los hogares por departamento suman 87.060 y la prevalencia recompuesta da 21,1 % ± 0,1 (C11) | La producción se conserva al agregar (C14) | Compuerta 3 |

## 5. Cifras clave verificadas

| Cifra | Valor |
|---|---|
| Hogares de la ECV | 87.060 (718 sin FIES válido) |
| Prevalencia nacional moderada o grave / grave | 21,10 % / 3,42 % |
| Registros de la API | 25.553 (2024) + 25.617 (2025) = 51.170; diferencia con la API: 0 |
| Departamentos con datos en EVA | 32 por año |
| Cultivos en EVA / en la canasta | 160 / 139 |
| Filas cargadas en el warehouse | 92.496 en 11 tablas (87.060 hogares; 3.204 de producción; 1.493 de variación; 33 de indicadores; dimensiones) |
| Pares departamento-cultivo comparables (R7) | 1.409 de 1.493 |
| Correlación con la prevalencia (descriptiva) | R6: −0,11; R7: −0,15 (Spearman, 32 departamentos) |
| Tiempo de una corrida local | ~65 s hasta la compuerta 3 y ~17 s la carga |
| Pruebas automatizadas | 20 (`pytest`), incluidos el test B y el test C |

## 6. Supuestos y limitaciones

- R6 y R7 son asociaciones descriptivas entre departamentos. No prueban causalidad ni que lo producido se consuma localmente.
- Una suma de toneladas de cultivos distintos no representa calorías ni suficiencia alimentaria.
- Las cifras 2024 y 2025 de EVA pueden ser revisadas por la UPRA. Cada lote guarda su fecha de extracción.
- Cerca del 19 % de los pares municipio-cultivo trae cifras idénticas en ambos años: una variación de 0 % no prueba estabilidad.
- La canasta es un criterio del proyecto anclado en una lista oficial (P3204), con excepciones declaradas.
- Bogotá (16,8 % de los hogares) no tiene datos agrícolas: R6 y R7 cubren 32 departamentos.
- En `fact_produccion_agricola`, la producción de "Plantas aromáticas" puede estar sobrestimada en 8 casos (la fuente trae período anual y semestral a la vez). Está fuera de la canasta y no afecta R6 ni R7.
- Para reproducir el perfilamiento (notebooks), el notebook 02 lee un CSV de resultados del repositorio de la primera entrega. El pipeline no depende de ese repositorio.

## 7. Pendientes para cerrar la entrega

| Pendiente | Qué se necesita |
|---|---|
| Evidencia de los tests A, B y C | Ejecutar el DAG en Airflow según [`orquestacion.md`](orquestacion.md) §6 y tomar capturas recortadas, cada una con su interpretación (sección 19 del enunciado) |
| Carpeta de evidencia | `docs/evidence/` con capturas y reportes de las compuertas de esas corridas, referenciados desde el README |
| Diagrama de arquitectura | Fuentes → lote → compuertas → modelo → warehouse → dashboard, con Airflow orquestando |
| Matrices | Matriz de requerimientos integrados R6–R7, matriz requerimiento → KPI y matriz de trazabilidad de punta a punta (sección 25) |
| Dashboard | Ver [`guia_dashboard.md`](guia_dashboard.md) |
| README final | Las 25 secciones, partiendo del mapa de la sección 2 |
