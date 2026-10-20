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

Se conserva el alcance de R1–R5. Su implementación analítica específica está pendiente en este repositorio.

| ID | Requerimiento | Estado actual | Trabajo pendiente |
|---|---|---|---|
| R1 | Caracterizar la distribución territorial de la inseguridad alimentaria. | Conservado. | Incorporar códigos territoriales, cruces geográficos y prevalencias por departamento y región. |
| R2 | Analizar la asociación entre servicios públicos básicos y vulnerabilidad alimentaria. | Conservado. | Integrar servicios de la vivienda y calcular indicadores por acceso a servicios. |
| R3 | Analizar la relación entre choques económicos recientes e inseguridad alimentaria. | Conservado. | Codificar choques y calcular indicadores por hogar y grupo. |
| R4 | Caracterizar las estrategias de afrontamiento según la severidad de la inseguridad alimentaria. | Conservado. | Integrar estrategias, clasificar severidad y elaborar consultas. |
| R5 | Evaluar la vulnerabilidad alimentaria según el ingreso del hogar. | Conservado. | Tratar inconsistencias, construir quintiles y calcular indicadores ponderados. |

### Avances comunes del proceso de datos

| Componente | Implementación actual |
|---|---|
| Entorno | Docker, Airflow, Celery, Redis y PostgreSQL; metadatos y almacén separados. |
| Extracción | Copia de CSV por ejecución y registro de integridad. |
| Validación inicial | Revisión de cabeceras, filas, columnas obligatorias y esquemas. |
| Transformación | Normalización de columnas, limpieza de espacios, conversión numérica y eliminación configurable de duplicados. |
| Validación posterior | Revisión de conteos, nulos, claves y rangos configurados. |
| Carga | Inserción o actualización en PostgreSQL mediante una transacción. |
| Pendiente | Integración específica de las tablas ECV, reglas de negocio, modelo estrella y consultas R1–R5. |

La implementación está en [el DAG principal](dags/etl_dag.py), [la lógica del proceso](src/pipeline.py) y [las reglas de validación](config/pipeline.json). Actualmente admite CSV con esquema homogéneo y carga genérica; todavía no reproduce el modelo de la primera entrega.

## 4. Nuevos requerimientos integrados: R6 y R7

### Fuentes e integración

| Elemento | Definición |
|---|---|
| Fuente de hogares | ECV 2025: departamento, medida FIES y factor de expansión. Confirmar nombres de variables en el diccionario. |
| Fuente agrícola | [Evaluaciones Agropecuarias Municipales (EVA) de la UPRA](https://www.datos.gov.co/Agricultura-y-Desarrollo-Rural/Evaluaciones-Agropecuarias-Municipales-EVA-2019-20/uejq-wxrr/about_data). |
| Datos agrícolas comunes | Código departamental, año, cultivo y producción; R6 añade departamento y grupo de cultivo; R7, período, área cosechada y ciclo. |
| Campos previstos de la fuente agrícola | `c_digo_dane_departamento`, `departamento`, `a_o`, `cultivo`, `grupo_cultivo`, `producci_n`, `periodo`, `rea_cosechada`, `ciclo_del_cultivo`. |
| Llave de integración | Código DIVIPOLA departamental de dos dígitos y año de referencia. |
| Preparación | Consolidar registros municipales y períodos por departamento, cultivo y año, sin duplicarlos. |
| Selección de cultivos | Lista explícita de cultivos para alimentación humana, compartida por R6 y R7. |
| Trazabilidad | Conservar fecha de extracción, datos descargados, exclusiones y revisiones; verificar campos, unidades y cobertura. |
| Estado | Requerimientos definidos; extracción agrícola, integración, indicadores y gráficos pendientes. |

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
| Prevalencia FIES departamental | `100 × Σ(peso del hogar × indicador FIES) / Σ(peso del hogar)`, sobre hogares con clasificación válida. El indicador vale 1 para inseguridad moderada o grave y 0 en otro caso. |
| Medida FIES | Confirmar si la fuente utiliza clasificación o probabilidades y documentar el cálculo correspondiente antes de implementarlo. |
| Variación por cultivo | `100 × (producción 2025 / producción 2024 − 1)`, con base 2024 positiva y datos comparables. |
| Cultivos en descenso | `100 × cultivos comparables con variación negativa / total de cultivos comparables`. |
| Valores no calculables | Marcar denominadores cero, ausencia de cultivos comparables, faltantes y bases inválidas; no asignar automáticamente cero ni registrar una caída. |
| Producción 2025 igual a cero | Representa una caída del 100 % únicamente si es un cero observado válido y la base 2024 es positiva. |
| Integración | Comprobar unicidad departamental y conservar el número de hogares de la ECV. |
| Relación con R1–R5 | R6 y R7 amplían el contexto territorial de R1; R2–R5 mantienen su alcance. Los indicadores agrícolas describen departamentos, no producción de cada hogar. |
