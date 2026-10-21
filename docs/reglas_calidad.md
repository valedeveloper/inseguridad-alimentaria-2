# Reglas de calidad de datos

Reglas que aplican las tres compuertas de Great Expectations del pipeline. Cada una protege uno o más requerimientos (R1–R7) y se apoya en un hallazgo verificado del perfilamiento.

Fuentes de evidencia:

- **H2** — [`notebooks/hallazgos_perfilamiento.md`](../notebooks/hallazgos_perfilamiento.md) (Segunda Entrega), sección indicada.
- **PE** — perfilamiento y `src/validate.py` de la Primera Entrega.

## 1. Política de severidad

| Severidad | Cuándo se usa | Acción del pipeline |
|---|---|---|
| Crítica | El error cambia una cifra de un requerimiento o rompe su grano. | **Se detiene.** La tarea falla sin reintento (el error es determinista) y no se carga nada. |
| Advertencia | Riesgo que no invalida el resultado, pero debe conocerse al interpretarlo. | **Continúa.** El resultado queda registrado en el reporte de validación. |

No hay reglas informativas: las limitaciones observadas (valores repetidos entre 2024 y 2025, variaciones de 0 %) se documentan en el README.

## 2. Resumen

| Compuerta | Datos | Críticas | Advertencias |
|---|---|---:|---:|
| 1 | ECV 2025 cruda (fuente primaria) | 2 | 0 |
| 2 | EVA cruda (API UPRA) | 7 | 2 |
| 3 | Datos preparados, antes de cargar | 7 | 1 |
| **Total** | | **16** | **3** |

## 3. Compuerta 1 — ECV cruda

| ID | Requerimientos | Riesgo | Regla y métrica | Umbral | Severidad | Evidencia |
|---|---|---|---|---|---|---|
| C1 | R1–R7 | Hogares duplicados o sin identificar inflan conteos y prevalencias. | (`DIRECTORIO`, `ORDEN`) única y sin nulos en las tablas de hogar. | 0 duplicados, 0 nulos | Crítica | PE: 87.060 hogares, 0 duplicados |
| C2 | R1, R6, R7 | Un departamento que no cruza deja hogares fuera del análisis territorial y de la integración con EVA. | `P1_DEPARTAMENTO`, tras `zfill(2)`, pertenece a DIVIPOLA. | 100 % | Crítica | H2 §13: 6.365 códigos de 1 dígito; 33 = 33 tras normalizar |

## 4. Compuerta 2 — EVA cruda (API)

| ID | Requerimientos | Riesgo | Regla y métrica | Umbral | Severidad | Evidencia |
|---|---|---|---|---|---|---|
| C3 | R6, R7 | Paginación incompleta: se pierden registros sin error visible. | Registros extraídos = `count(*)` de la API, por año. | Diferencia 0 | Crítica | H2 §2: 25.553 (2024) y 25.617 (2025), diferencia 0 |
| C4 | R6, R7 | La API cambia o retira campos. | Existen los 18 campos esperados. | 18 de 18 | Crítica | H2 §3 |
| C5 | R7 | Falta un año y la variación 2024→2025 no puede calcularse. | `a_o` ∈ {2024, 2025}, ambos presentes; `periodo` = año, año+A o año+B. | 100 %; ambos años con registros | Crítica | H2 §7: 0 inconsistencias |
| C6 | R6, R7 | Texto no numérico o negativos corrompen sumas de producción. | Áreas, producción y rendimiento con formato `^\d+(\.\d+)?$` (≥ 0). | 100 % | Crítica | H2 §3: 0 fuera de patrón |
| C7 | R6, R7 | Registros duplicados se suman dos veces. | (`c_digo_dane_municipio`, `c_digo_del_cultivo`, `periodo`) única. | 0 duplicados | Crítica | H2 §4: llave natural sin duplicados |
| C8 | R6, R7 | Códigos territoriales inválidos impiden integrar con la ECV. | Departamento de 2 dígitos en DIVIPOLA; municipio de 5 dígitos con el prefijo de su departamento. | 100 % | Crítica | H2 §4 y §10 |
| C9 | R6, R7 | Un cultivo nuevo sin clasificar altera la canasta fija sin aviso. | Todo cultivo recibido está en el catálogo de la canasta (incluido o excluido). | 100 % | Crítica | H2 §12; canasta en `config/canasta_cultivos.csv` (sección 6) |
| A1 | R6, R7 | La fuente deja de reportar un departamento. | Número de departamentos por año. | 32 | Advertencia | H2 §10: 32 en ambos años (Bogotá no está en EVA) |
| A2 | R7 | Error de unidad o digitación infla la producción de un cultivo. | Registros con rendimiento > 20 × la mediana de su código. | 0 | Advertencia | H2 §9: 0 sobre 20×; 2 sobre 10× |

## 5. Compuerta 3 — Datos preparados

| ID | Requerimientos | Riesgo | Regla y métrica | Umbral | Severidad | Evidencia |
|---|---|---|---|---|---|---|
| C10 | R1–R5 | Una unión duplica o pierde hogares (fan-out). | Filas del hecho = filas de entrada; llave del hogar única. | Igualdad exacta | Crítica | PE: 87.060 antes y después de las uniones |
| C11 | R1, R6, R7 | Errores en `FEX_C`, `PROB_*` o en la integración departamental cambian las prevalencias. | Prevalencia moderada o grave ponderada, calculada en el hecho y recompuesta desde la tabla departamental; hogares por departamento suman el total de la ECV. | 21,1 % ± 0,1 puntos; suma de hogares exacta | Crítica | H2 §13: 21,10 %; PE: tolerancia 0,1 |
| C12 | R4 | Hogares sin FIES clasificados en una severidad o incluidos en el denominador. | Severidad "Sin dato" si y solo si la probabilidad FIES es nula. | 100 % de coincidencia | Crítica | PE y H2 §13: 718 hogares |
| C13 | R3, R4 | Conteos de choques o estrategias que no corresponden a las banderas. | `numero_choques` y `numero_estrategias` = suma de sus banderas; hogar sin choque ⇔ sin estrategia. | 100 % | Crítica | PE: regla de negocio validada |
| C14 | R6, R7 | La agregación pierde o duplica producción. | Producción total antes y después de agregar a departamento × cultivo × año (nivel cultivo, no código de desagregación); llave del agregado única. | Diferencia < 1 t (redondeo a 2 decimales por fila); 0 duplicados | Crítica | H2 §11: producción conservada (diferencia observada 0) |
| C15 | R6 | Un departamento repetido o un faltante convertido en 0 sesga la asociación. | Una fila por departamento (33); Bogotá con diversidad nula, no 0. | 33 filas únicas; 0 ceros imputados | Crítica | H2 §14 |
| C16 | R7 | Divisiones por cero o casos no comparables registrados como caídas. | Variación solo con base 2024 > 0; casos no calculables con estado explícito; % en descenso entre 0 y 100 y cultivos en descenso ≤ comparables. | 0 infinitos o NaN sin marca; 100 % en rango | Crítica | H2 §11: 43 bases 0, 34 solo 2024, 24 solo 2025 |
| A3 | R6, R7 | Resultados de departamentos con poca información agrícola se interpretan como robustos. | Departamentos con menos de N cultivos comparables. | N = 15 | Advertencia | H2 §10: Guaviare, Guainía, Vaupés, San Andrés |

## 6. Canasta de cultivos alimentarios

R6 y R7 usan una canasta fija de cultivos, definida en [`config/canasta_cultivos.csv`](../config/canasta_cultivos.csv): los 160 cultivos de EVA con `incluido`, el código P3204 que les corresponde y el motivo. El pipeline la lee; cambiarla no requiere tocar código.

| Elemento | Definición |
|---|---|
| Base oficial | La pregunta **P3204** de la propia ECV 2025 (capítulo M): *"¿Cuáles de los siguientes alimentos compró el hogar o adquirió sin pago durante los últimos 7 días?"*, con 25 grupos de alimentos (catálogo en el diccionario DANE de la ECV). Es la definición de alimento de la misma encuesta de la que sale la prevalencia FIES. |
| Criterio | Entra el cultivo de EVA cuyo producto corresponde a un grupo de alimentos de P3204. |
| Nivel | Por cultivo (160), no por código de desagregación (187). |
| Resultado | **139 incluidos**, 21 excluidos. Por grupo P3204: frutas (13) 64, verduras (17) 30, condimentos (23) 10, papas/yuca/arracacha/ñame (16) 9, café/chocolate/té/aromáticas (24) 8, aceites (12) 5, granos secos (14) 5, cereales y derivados (02) 3, maní y frutos secos (21) 2, arroz (01), plátano (15) y panela (19, caña) 1 cada uno. |
| Excluidos | Sin alimento en P3204: algodón, fique, iraca, tabaco, sorgo, millo y cebada. Medicinales u ornamentales según EVA: sábila, ruda, ruscus, romero, moringa, stevia y estevia. Categorías residuales o genéricas ("Otros frutales", "Otras hortalizas", "Otras raíces y tubérculos", "Otros cultivos tropicales…", "Otros cultivos para condimentos…", "Plantas aromáticas"): su composición puede cambiar entre años y rompe la canasta fija. "Chiraran - albahaca": misma especie que Albahaca, se cuenta una sola vez. |
| Excepciones declaradas | Maíz, soya y palma se incluyen aunque parte de su producción se destine a alimento animal o industria (no separable por cultivo). Caña se incluye por la panela (19) y el azúcar y la miel (18). Quinua se asigna a "otros granos" (14), que P3204 no nombra explícitamente. |

## 7. Prueba de falla controlada (test B)

Se usará **C7**: se duplica un registro en el snapshot crudo de la API. La compuerta 2 debe fallar, el pipeline detenerse antes de transformar y la tarea no reintentarse.

## 8. Reglas evaluadas y descartadas

| Regla | Motivo |
|---|---|
| Área cosechada ≤ área sembrada | La definición de la UPRA la permite; rechazaría 6.950 registros válidos (H2 §6). |
| Rango de `PROB_*`, `FEX_C` > 0, nulos FIES en la ECV cruda | Un error ahí descuadra la reconciliación de C11. |
| Integración vivienda-hogar; dominios de servicios, choques y estrategias | Los detectan C10 y C13. |
| Llaves foráneas y banderas de servicios sin nulos | Las garantizan las restricciones `FOREIGN KEY` y `NOT NULL` del warehouse. |
| Variación recalculada; solo cultivos de la canasta; dominios de severidad y quintil | Los garantiza el código de transformación. |
| Coherencia de rendimiento; producción sin área cosechada; un código → un cultivo; conteos fijos; región y clase | Bajo impacto en los requerimientos. |
| No sumar período anual y semestral del mismo cultivo | El caso solo ocurre en "Plantas aromáticas", que quedan fuera de la canasta (H2 §7). |
| Porcentaje de valores repetidos 2024 = 2025 y de variaciones 0 % | Se documentan como limitación de R7 en el README (H2 §8). |
