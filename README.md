# Factores socioeconómicos asociados a la inseguridad alimentaria en los hogares colombianos

## 1. Problema y objetivo analítico

| Elemento | Descripción |
|---|---|
| Problema | Diferencias territoriales y socioeconómicas en la inseguridad alimentaria de los hogares colombianos. |
| Pregunta central | ¿Cómo se relaciona la inseguridad alimentaria con el territorio, los servicios públicos, los choques económicos, el afrontamiento, el ingreso y la producción agrícola? |
| Objetivo | Analizar estas asociaciones integrando información de los hogares y del contexto agrícola departamental. |
| Fuente principal | Encuesta Nacional de Calidad de Vida (ECV) 2025 del DANE. |
| Unidad de análisis | Hogar, identificado por `DIRECTORIO` y `ORDEN`; contexto agrícola agregado por departamento. |
| Alcance | Análisis descriptivo de asociaciones, sin establecer causalidad. |

## 2. Línea base de la primera entrega y repositorio

**Repositorio:** [Primera entrega — rama de desarrollo](https://github.com/Sxg0673/etl-inseguridad-alimentaria-colombia/tree/dev).

| Componente | Línea base documentada |
|---|---|
| Requerimientos | R1–R5: territorio, servicios, choques, afrontamiento e ingreso. |
| Datos | Información de vivienda, servicios y condiciones de vida de la ECV 2025. |
| Preparación | Perfilamiento, decisiones de limpieza y reglas de integración por vivienda y hogar. |
| Modelo | Hecho por hogar y dimensiones de geografía, ingreso, severidad, choques y afrontamiento. |
| Continuidad en esta entrega | Orquestación con Docker y Airflow, controles de calidad y definición de R6–R7 con datos agrícolas. |

## 3. Estado y cambios de R1–R5

Se conserva el alcance de R1–R5. Su extracción, limpieza, transformación y modelo dimensional están portados a este repositorio (`src/ecv/`) y producen los mismos resultados que la primera entrega (87.060 hogares; prevalencia nacional 21,10 %). Sus consultas analíticas están en el warehouse como vistas ([sql/vistas_analiticas.sql](sql/vistas_analiticas.sql)) y reproducen exactamente los resultados de la primera entrega.

| ID | Requerimiento | Estado actual | Trabajo pendiente |
|---|---|---|---|
| R1 | Caracterizar la distribución territorial de la inseguridad alimentaria. | Implementado. | Vista `vw_r1_distribucion_territorial`; falta el dashboard. |
| R2 | Analizar la asociación entre servicios públicos básicos y vulnerabilidad alimentaria. | Implementado. | Vista `vw_r2_servicios_publicos`; falta el dashboard. |
| R3 | Analizar la relación entre choques económicos recientes e inseguridad alimentaria. | Implementado. | Vista `vw_r3_choques_economicos`; falta el dashboard. |
| R4 | Caracterizar las estrategias de afrontamiento según la severidad de la inseguridad alimentaria. | Implementado. | Vista `vw_r4_estrategias_severidad`; falta el dashboard. |
| R5 | Evaluar la vulnerabilidad alimentaria según el ingreso del hogar. | Implementado. | Vista `vw_r5_quintiles_ingreso`; falta el dashboard. |

### Avances comunes del proceso de datos

| Componente | Implementación actual |
|---|---|
| Entorno | Docker, Airflow 3.1.8 con LocalExecutor y PostgreSQL; metadatos y almacén separados. |
| Extracción | ECV: copia de los CSV a un lote por ejecución con su sha256. EVA: API de datos.gov.co paginada, conciliada contra el conteo oficial y guardada con su fecha de extracción. |
| Validación inicial | Great Expectations sobre cada fuente cruda (compuertas 1 y 2). |
| Transformación | ECV: módulos de la primera entrega. EVA: agregación a departamento × cultivo × año y canasta de cultivos. |
| Validación posterior | Great Expectations sobre los datos preparados (compuerta 3) antes de cargar. |
| Carga | Modelo dimensional completo (11 tablas) con `TRUNCATE` + `INSERT` en una sola transacción. |
| Pendiente | Dashboard y evidencia de ejecución en Airflow (tests A, B y C). |

La lógica está en `src/` (`ecv/`, `eva/`, `calidad/`, `comun/` y `carga.py`), las reglas de calidad en [docs/reglas_calidad.md](docs/reglas_calidad.md) y el modelo en [docs/modelo_dimensional.dbml](docs/modelo_dimensional.dbml) y [sql/create_tables.sql](sql/create_tables.sql). El DAG ([dags/etl_dag.py](dags/etl_dag.py)) orquesta estas etapas; su diseño está en [docs/orquestacion.md](docs/orquestacion.md).

## 4. Nuevos requerimientos integrados: R6 y R7

### Fuentes e integración

| Elemento | Definición |
|---|---|
| Fuente de hogares | ECV 2025: departamento (`P1_DEPARTAMENTO`), probabilidad FIES de inseguridad moderada o grave (`PROB_IAMG`) y factor de expansión del hogar (`FEX_C`). |
| Fuente agrícola | [Evaluaciones Agropecuarias Municipales (EVA) de la UPRA](https://www.datos.gov.co/Agricultura-y-Desarrollo-Rural/Evaluaciones-Agropecuarias-Municipales-EVA-2019-20/uejq-wxrr/about_data). |
| Datos agrícolas comunes | Código departamental, año, cultivo y producción; R6 añade departamento y grupo de cultivo; R7, período, área cosechada y ciclo. |
| Campos utilizados de la fuente agrícola | `c_digo_dane_departamento`, `departamento`, `c_digo_dane_municipio`, `a_o`, `periodo`, `cultivo`, `grupo_cultivo`, `subgrupo`, `ciclo_del_cultivo`, `estado_f_sico_del_cultivo`, `rea_sembrada`, `rea_cosechada`, `producci_n`. La extracción conserva los 18 campos de la API. |
| Llave de integración | Código DIVIPOLA departamental de dos dígitos. La ECV es de 2025, así que el año no es llave: R6 usa EVA 2025 y R7 compara 2024 con 2025. Bogotá no tiene datos en EVA y queda "sin dato", nunca 0. |
| Preparación | Consolidar registros municipales y períodos por departamento, cultivo y año, sin duplicarlos. |
| Selección de cultivos | Canasta fija anclada en la lista oficial de alimentos de la ECV 2025 (pregunta P3204): 139 de 160 cultivos, en [config/canasta_cultivos.csv](config/canasta_cultivos.csv) con el motivo de cada uno. |
| Trazabilidad | Conservar fecha de extracción, datos descargados, exclusiones y revisiones; verificar campos, unidades y cobertura. |
| Estado | Extracción agrícola, integración, indicadores y vistas (`vw_r6_diversidad_departamental`, `vw_r7_variacion_cultivo`, `vw_r7_descenso_departamental`) implementados; dashboard pendiente. |

### R6. Diversificación agrícola e inseguridad alimentaria

| Elemento | Especificación |
|---|---|
| Pregunta | ¿Qué relación existe entre la diversidad de cultivos alimentarios de cada departamento en 2025 y la prevalencia de inseguridad alimentaria moderada o grave de sus hogares? |
| Requerimiento | Integrar ECV 2025 y EVA mediante código DIVIPOLA y año para analizar la asociación entre diversidad agrícola e inseguridad alimentaria. |
| Procesamiento | Filtrar EVA 2025, seleccionar cultivos alimentarios, consolidar producción y contar cultivos distintos con producción positiva; cruzar con la prevalencia FIES departamental. |
| Indicador agrícola | Número de cultivos alimentarios distintos con producción positiva por departamento. |
| Indicador alimentario | Prevalencia FIES ponderada por el factor de expansión del hogar. |
| Resultado | Tabla por departamento con código DIVIPOLA, año, diversidad agrícola y prevalencia FIES. |
| Visualización | Dispersión: diversidad agrícola en el eje horizontal y prevalencia FIES en el vertical. |
| Aceptación | Una fila por departamento; no duplicar hogares; conservar faltantes agrícolas sin convertirlos en cero. |
| Interpretación | Asociación descriptiva; no demuestra consumo local de los alimentos producidos ni causalidad. |

### R7. Variación de la producción agrícola e inseguridad alimentaria

| Elemento | Especificación |
|---|---|
| Pregunta | ¿Los departamentos donde cayó la producción alimentaria entre 2024 y 2025 presentan mayor prevalencia de inseguridad alimentaria en la ECV 2025? |
| Requerimiento | Comparar una canasta fija de cultivos alimentarios entre 2024 y 2025 y relacionar su variación con la prevalencia FIES departamental de 2025. |
| Procesamiento | Consolidar producción por departamento, cultivo y año; comparar observaciones válidas de ambos años y calcular el porcentaje de cultivos en descenso. |
| Indicador por cultivo | Variación porcentual de la producción entre 2024 y 2025. |
| Indicador departamental | Porcentaje de cultivos comparables cuya producción disminuyó. |
| Resultados | Tabla por departamento y cultivo con ambas producciones, variación y comparabilidad; tabla departamental con porcentaje en descenso, cultivos comparables y prevalencia FIES. |
| Visualización | Dispersión: porcentaje de cultivos en descenso en el eje horizontal y prevalencia FIES en el vertical. |
| Aceptación | Misma canasta de referencia; documentar exclusiones y revisiones; marcar bases cero y faltantes; evitar divisiones por cero y duplicación de hogares. |
| Interpretación | Asociación descriptiva; una suma de toneladas no representa calorías ni suficiencia alimentaria. |

### Cálculo y reglas de calidad

| Indicador o regla | Definición |
|---|---|
| Prevalencia FIES departamental | `Σ(FEX_C × PROB_IAMG) / Σ(FEX_C)` sobre hogares con FIES válido (se excluyen 718 hogares sin dato). `PROB_IAMG` ya está en escala 0–100. Reproduce el 21,1 % nacional publicado por el DANE. |
| Medida FIES | La ECV entrega probabilidades (`PROB_IAMG`, `PROB_IAG`), no una clasificación; se usan como en la primera entrega. |
| Variación por cultivo | `100 × (producción 2025 / producción 2024 − 1)`, con base 2024 positiva y datos comparables. |
| Cultivos en descenso | `100 × cultivos comparables con variación negativa / total de cultivos comparables`. |
| Valores no calculables | Marcar denominadores cero, ausencia de cultivos comparables, faltantes y bases inválidas; no asignar automáticamente cero ni registrar una caída. |
| Producción 2025 igual a cero | Representa una caída del 100 % únicamente si es un cero observado válido y la base 2024 es positiva. |
| Integración | Comprobar unicidad departamental y conservar el número de hogares de la ECV. |
| Relación con R1–R5 | R6 y R7 amplían el contexto territorial de R1; R2–R5 mantienen su alcance. Los indicadores agrícolas describen departamentos, no producción de cada hogar. |

### Despliegue del entorno

Desde la raíz del proyecto, en una terminal: crear `.env` a partir de `.env.example` y colocar los CSV de la ECV en `data/raw/ecv/` (ver [data/raw/README.md](data/raw/README.md)). Luego:

```bash
docker compose config --quiet
docker compose up -d --build
```