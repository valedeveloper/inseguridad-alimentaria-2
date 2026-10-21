# Guía para el dashboard

Cómo conectar el dashboard al Data Warehouse, qué contiene cada vista y qué tener en cuenta para no interpretar mal los resultados.

El enunciado exige que el dashboard **consulte el Data Warehouse** (PostgreSQL). No se aceptan conexiones a CSV, a la respuesta de la API ni a archivos intermedios (sección 21).

## 1. Conexión

| Parámetro | Valor |
|---|---|
| Motor | PostgreSQL 16 |
| Servidor | `localhost` |
| Puerto | `5434` |
| Base de datos | `warehouse` |
| Usuario | `warehouse` |
| Contraseña | La de `WAREHOUSE_PASSWORD` en `.env` (por defecto `warehouse`) |

1. Levantar el warehouse: `docker compose up -d warehouse` (o el stack completo).
2. El warehouse se llena al ejecutar el DAG `inseguridad_alimentaria_etl` hasta la tarea `cargar` ([orquestacion.md](orquestacion.md)).
3. En Power BI: *Obtener datos → Base de datos PostgreSQL*, servidor `localhost:5434`, base `warehouse`. Se recomienda el modo **Importar**.
4. Cada ejecución del DAG reemplaza los datos completos (`TRUNCATE` + `INSERT`) y recrea las vistas. Después de una ejecución basta con **actualizar** el informe.

## 2. Vistas disponibles

Las vistas ya traen los cálculos ponderados. Lo recomendado es usarlas directamente, sin rehacer uniones entre tablas. El SQL está en [`sql/vistas_analiticas.sql`](../sql/vistas_analiticas.sql).

| Vista | Requerimiento | Una fila es… | Columnas principales |
|---|---|---|---|
| `vw_r1_distribucion_territorial` | R1 | Región × departamento (34 filas) | `region`, `departamento`, `hogares`, `prevalencia_moderada_grave_pct`, `prevalencia_grave_pct` |
| `vw_r2_servicios_publicos` | R2 | Combinación de acceso a acueducto y alcantarillado (4) | `tiene_acueducto`, `tiene_alcantarillado`, `hogares`, prevalencias |
| `vw_r3_choques_economicos` | R3 | Número de choques económicos (10) | `numero_choques`, `hogares`, prevalencias |
| `vw_r4_estrategias_severidad` | R4 | Severidad × número de estrategias (37) | `severidad`, `numero_estrategias`, `hogares`, `distribucion_ponderada_pct` |
| `vw_r5_quintiles_ingreso` | R5 | Quintil de ingreso (6, incluye "Dato inconsistente") | `quintil_ingreso`, `nombre_quintil`, `hogares`, prevalencias |
| `vw_r6_diversidad_departamental` | R6 | Departamento (33) | `codigo_departamento`, `nombre_departamento`, `diversidad_cultivos_2025`, `prevalencia_moderada_grave_pct`, `prevalencia_grave_pct`, `hogares_muestra`, `baja_cobertura`, `sin_dato_agricola` |
| `vw_r7_variacion_cultivo` | R7 por cultivo | Departamento × cultivo de la canasta (1.493) | `nombre_departamento`, `nombre_cultivo`, `grupo_cultivo`, `produccion_2024_t`, `produccion_2025_t`, `variacion_pct`, `estado_comparabilidad`, `en_descenso` |
| `vw_r7_descenso_departamental` | R7 por departamento | Departamento (33) | `cultivos_comparables`, `cultivos_en_descenso`, `pct_cultivos_en_descenso`, prevalencias, `baja_cobertura`, `sin_dato_agricola` |

R1 a R5 reproducen exactamente los resultados de la primera entrega.

## 3. Qué tener en cuenta

| Tema | Regla |
|---|---|
| Prevalencias ya ponderadas | Cada fila ya está ponderada por el factor de expansión. **No promediar porcentajes entre filas** (por ejemplo, el promedio de los departamentos no es la prevalencia nacional). La cifra nacional es **21,10 %** moderada o grave y 3,42 % grave. |
| `hogares` | Es el número de hogares encuestados (muestra), no la población. Sirve para mostrar el tamaño de muestra, no para sumar población. |
| R1 tiene 34 filas | Un departamento aparece en dos regiones porque la región depende también de la clase (cabecera o resto). Para un gráfico por departamento, usar `vw_r6_diversidad_departamental`, que trae la prevalencia por departamento en una sola fila. |
| R4 es una distribución | `distribucion_ponderada_pct` suma 100 dentro de cada severidad. No es una prevalencia. Va bien en barras apiladas al 100 %. |
| Bogotá en R6 y R7 | No tiene datos agrícolas en la fuente EVA: sus indicadores agrícolas son **nulos**, no cero (`sin_dato_agricola = true`). Se excluye de los gráficos de dispersión, pero su prevalencia sí se muestra en R1. |
| Baja cobertura | `baja_cobertura = true` marca departamentos con menos de 15 cultivos comparables (hoy, Guaviare). Conviene resaltarlos, por ejemplo con otro color o un ícono, sin excluirlos. |
| Variación por cultivo | Solo las filas con `estado_comparabilidad = 'comparable'` tienen variación. Los demás estados (`base_cero`, `solo_2024`, `solo_2025`) no son caídas: filtrarlos o mostrarlos aparte. Un −100 % es una caída real (producción 2025 en 0 con base positiva). |
| Variaciones extremas | Bases pequeñas producen variaciones muy altas (hasta +3.142 %). En tablas, ordenar o filtrar con cuidado. |
| 0 % de variación | Cerca de una de cada cinco combinaciones municipio-cultivo trae cifras idénticas en 2024 y 2025 en la fuente. Un 0 % no prueba estabilidad. |
| Unidades | Producción en toneladas y áreas en hectáreas. Sumar toneladas de cultivos distintos no representa calorías ni suficiencia alimentaria. |
| Interpretación | R6 y R7 son **asociaciones descriptivas** entre departamentos, no relaciones causales. La correlación observada es débil (Spearman entre −0,11 y −0,15). Evitar títulos como "la diversidad reduce la inseguridad". |
| Canasta | R6 y R7 usan 139 cultivos alimentarios de EVA, definidos con la lista de alimentos de la propia ECV (pregunta P3204). Ver [reglas_calidad.md](reglas_calidad.md), sección 6. |

## 4. Visualizaciones sugeridas

| Requerimiento | Visual | Fuente |
|---|---|---|
| R1 | Barras ordenadas o mapa por departamento con la prevalencia moderada o grave | `vw_r6_diversidad_departamental` (una fila por departamento) o `vw_r1_distribucion_territorial` (por región) |
| R2 | Barras por combinación de acueducto y alcantarillado | `vw_r2_servicios_publicos` |
| R3 | Línea o barras según el número de choques | `vw_r3_choques_economicos` |
| R4 | Barras apiladas al 100 % por severidad | `vw_r4_estrategias_severidad` |
| R5 | Barras por quintil (gradiente de ingreso) | `vw_r5_quintiles_ingreso` |
| R6 | **Dispersión**: diversidad de cultivos (eje X) frente a prevalencia (eje Y), un punto por departamento, sin Bogotá y con la baja cobertura resaltada | `vw_r6_diversidad_departamental` |
| R7 | **Dispersión**: % de cultivos en descenso (X) frente a prevalencia (Y), y una tabla de variación por cultivo con filtro de departamento | `vw_r7_descenso_departamental`, `vw_r7_variacion_cultivo` |

El enunciado pide **al menos un KPI y una visualización que muestren el valor de integrar la API**. Las dispersiones de R6 y R7 cumplen la parte visual. Para el KPI, una opción es una tarjeta por departamento seleccionado con su diversidad de cultivos, su % de cultivos en descenso y su prevalencia. Esa información solo existe gracias a cruzar la ECV con EVA.

## 5. Para evitar errores comunes

- Usar las vistas y no las tablas de hechos directamente, salvo que se necesite un nivel de detalle que las vistas no tienen.
- Si se usan las tablas: las prevalencias se calculan como `SUM(factor_expansion × prob) / SUM(factor_expansion)` **excluyendo** los hogares con probabilidad nula (718).
- No escribir datos en el warehouse desde Power BI: la siguiente ejecución del DAG reemplaza todo.
