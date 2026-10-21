# Hallazgos del perfilamiento — Segunda Entrega

Hallazgos verificados con código sobre los datos completos. Cada cifra sale de un notebook ejecutado; la sección del notebook se indica entre corchetes.

| Notebook | Fuente | Alcance |
|---|---|---|
| [`01_profiling_eva.ipynb`](01_profiling_eva.ipynb) | API EVA (UPRA), años 2024 y 2025 | Perfil completo de la nueva fuente. |
| [`02_profiling_ecv_departamental.ipynb`](02_profiling_ecv_departamental.ipynb) | ECV 2025 (DANE) | Lo que la integración departamental necesita. El perfil a nivel hogar está en la Primera Entrega. |

Regla seguida: **observar sin limpiar**. Ningún dato se modificó; las conversiones se hicieron sobre copias.

---

## 1. Fuente API: identificación

| Elemento | Valor |
|---|---|
| Dataset | Evaluaciones Agropecuarias Municipales – EVA. 2019-2025. Base Agrícola (`uejq-wxrr`) |
| Productor | UPRA |
| Endpoint | `https://www.datos.gov.co/resource/uejq-wxrr.json` (Socrata SODA) |
| Autenticación | No requiere |
| Licencia | Creative Commons Attribution-ShareAlike 4.0 |
| Última actualización de filas | 2026-08-28 |
| Fecha de extracción usada | 2026-10-20 23:37 UTC |
| Advertencia del productor | "Las cifras de los dos últimos años son susceptibles de modificación". Hoy son **2024 y 2025**, justo los años del proyecto. [26] |

## 2. EVA: extracción y conciliación [2–4]

| Año | Conteo de la API (`count(*)`) | Registros extraídos | Diferencia | Páginas de 5.000 |
|---|---:|---:|---:|---|
| 2024 | 25.553 | 25.553 | 0 | 5 completas + 553 |
| 2025 | 25.617 | 25.617 | 0 | 5 completas + 617 |
| **Total** | **51.170** | **51.170** | **0** | |

- La paginación con `$order=:id`, `$limit` y `$offset` no pierde ni duplica registros.
- Una sola página no basta: cada año necesita 6.

## 3. EVA: esquema y formato [5–7]

| Hallazgo | Evidencia | Implicación |
|---|---|---|
| 18 campos, todos presentes en los 51.170 registros | 0 ausentes por campo | Esquema estable. |
| Todo llega como texto | Incluso `a_o`, áreas, producción, rendimiento y código de cultivo, que la API declara `number` | Convertir tipos en la transformación, no confiar en el JSON. |
| Formato numérico limpio | 0 valores fuera del patrón `^\d+(\.\d+)?$`; punto decimal; sin comas; máximo 2 decimales | Conversión directa con punto decimal (la ECV usa coma; no mezclar reglas). |
| Sin negativos ni valores no convertibles | 0 en los 4 campos numéricos | |
| Único marcador "sin dato" | `nombre_cient_fico_del_cultivo = "No aplica"` en 815 registros (categorías "Otros…" y "Plantas aromáticas") | Campo no usado en R6/R7. |

## 4. EVA: llaves y unicidad [8, 14]

| Prueba | Resultado |
|---|---|
| Filas duplicadas exactas | 0 |
| (`c_digo_dane_municipio`, `c_digo_del_cultivo`, `periodo`) | **Única**: 0 duplicados → llave natural del registro |
| (`c_digo_dane_municipio`, `cultivo`, `periodo`) | No única: 10.684 filas en 4.757 grupos (un cultivo tiene varias desagregaciones) |
| Código de departamento | Siempre 2 dígitos |
| Código de municipio | Siempre 5 dígitos; los 2 primeros coinciden con el departamento en el 100 % |
| Código ↔ nombre (departamento y municipio) | 1:1 en ambos |
| Nombres de municipio | 1.020 nombres para 1.102 códigos (homónimos) → integrar siempre por código |

**Grano de la fuente:** un registro = municipio × código de cultivo × período.

## 5. EVA: dominios y jerarquía del cultivo [10–13]

| Variable | Valores | Detalle |
|---|---:|---|
| `grupo_cultivo` | 8 | Cereales, Condimentos/medicinales/aromáticas, Tropicales tradicionales, Frutales, Hortalizas, Leguminosas, Oleaginosas, Raíces y tubérculos |
| `ciclo_del_cultivo` | 2 | Permanente 19.778 · Transitorio 31.392 |
| `estado_f_sico_del_cultivo` | 10 | "En fresco" 33.718; el resto: grano seco, paddy, pergamino, caña o verde, aceite crudo, fibra, algodón semilla, etc. |
| `periodo` | 6 | Anual (`2024`, `2025`) y semestral (`2024A`, `2024B`, `2025A`, `2025B`) |
| `cultivo` | 160 | |
| `c_digo_del_cultivo` | 187 | Identifica la **desagregación**, no el cultivo |

| Relación | Resultado |
|---|---|
| Código → desagregación, cultivo, grupo, ciclo, estado físico | 1 a 1 (sin excepciones) |
| Cultivo → código | Hasta 5 códigos; **16 cultivos** tienen más de uno (ej. Maíz: amarillo/blanco × tecnificado/tradicional; Arroz: riego/secano; Caña: azúcar/panela/miel) |
| Cultivo → estado físico | **Siempre 1**: sumar dentro de un cultivo no mezcla unidades |
| Mismo cultivo con dos códigos y nombres distintos | `Stevia` (2022900) y `Estevia` (2020900), ambos *Stevia rebaudiana*; `Albahaca` (2020200) y `Chiraran - albahaca` (1020600), ambos *Ocimum basilicum* |

## 6. EVA: coherencia numérica [15–17, 26]

| Hallazgo | Registros | Interpretación |
|---|---:|---|
| Producción, área cosechada y rendimiento en 0 a la vez | 2024: 1.850 (7,2 %) · 2025: 1.686 (6,6 %) | Sembrado sin cosecha en el período. Coinciden exactamente las mismas filas. |
| Producción > 0 con área cosechada 0 | 0 | |
| Área cosechada > 0 con producción 0 | 0 | |
| Área sembrada 0 con cosecha > 0 | 1.412 | Cosecha de siembras anteriores. |
| Todo en 0 | 3 | Registro sin actividad. |
| Rendimiento ≠ producción / área cosechada | 15 con diferencia > 1 %; **0 con diferencia > 5 %** | Diferencias por redondeo. |
| **Área cosechada > área sembrada** | **6.950** (Transitorio: 3.298 en 2024 y 3.648 en 2025; Permanente: 4) | **No es error.** La UPRA define que desde 2022, en transitorios, cosechada y producción son las **cosechas efectivas del período**, que pueden venir de siembras anteriores. |

## 7. EVA: períodos [11, 18, 27]

| Ciclo | Anual | Semestre A | Semestre B |
|---|---:|---:|---:|
| Permanente | 19.778 | 0 | 0 |
| Transitorio | 106 | 16.084 | 15.202 |

- Todos los períodos empiezan por su año (0 inconsistencias).
- Los 106 transitorios con período anual son **todos "Plantas aromáticas"** (56 en 2024, 50 en 2025).
- En **8** municipio-cultivo-año, "Plantas aromáticas" trae período anual **y** semestres a la vez. El anual no es la suma de los semestres (ej. Chipaque 2024: anual 576 t; A 78 t + B 90 t). Sumarlos todos sería doble conteo.

## 8. EVA: valores repetidos entre 2024 y 2025 [28–30]

Se compararon los mismos municipio-código-tipo de período en ambos años (23.071 pares con producción 2024 > 0).

| Medida | Resultado |
|---|---:|
| Producción idéntica 2024 = 2025 | 5.923 (25,7 %) |
| Área sembrada, área cosechada y producción idénticas | 4.373 (19,0 %) |
| — en cultivos permanentes | 2.575 (27,5 %) |
| — en cultivos transitorios | 1.798 (13,1 %) |
| Rango por departamento (pares idénticos) | 10,2 % (Vichada) a 40,0 % (San Andrés) |
| Producción comparable de 2025 que repite exactamente 2024 | 24,5 % |
| Variaciones departamento-cultivo exactamente 0 % | 181 de 1.530 (11,8 %) |

Ejemplo: Candelaria (Valle), caña de azúcar: 25.391 ha y 3.097.702 t en ambos años.

**Implicación para R7:** no se puede distinguir producción estable de cifra arrastrada del año anterior. Una variación de 0 % no es evidencia de estabilidad. Debe reportarse como limitación y monitorearse.

## 9. EVA: valores atípicos [19]

| Hallazgo | Detalle |
|---|---|
| Mayores producciones | Todas caña de azúcar en Valle del Cauca (máx. Palmira 2025: 4.758.600 t; rendimiento 140 t/ha). Plausibles para el cultivo. |
| Rendimiento > 5× la mediana de su código | 29 registros |
| Rendimiento > 10× | 2 (Agraz-mortiño, Sonsón: 30 t/ha frente a mediana 2 t/ha, ambos años) |
| Rendimiento > 20× | 0 |

## 10. EVA: cobertura territorial [9, 20, 21]

| Hallazgo | Resultado |
|---|---|
| Departamentos | 32 en ambos años. **Falta Bogotá (11)** frente a DIVIPOLA (33). Ningún código EVA está fuera de DIVIPOLA. |
| Nombres de departamento | Coinciden con DIVIPOLA en los 32 (ignorando mayúsculas). |
| Municipios | 1.101 en 2024 y 1.102 en 2025 (Manaure, La Guajira, solo en 2025). |

Departamentos con menor información agrícola (2025):

| Departamento | Municipios | Códigos de cultivo | Registros |
|---|---:|---:|---:|
| San Andrés | 2 | 21 | 37 |
| Guainía | 2 | 17 | 38 |
| Vaupés | 3 | 18 | 44 |
| Guaviare | 4 | 14 | 51 |
| Vichada | 4 | 22 | 63 |
| Amazonas | 2 | 31 | 70 |

En el otro extremo: Boyacá (123 municipios, 2.709 registros), Antioquia (125; 2.278), Cundinamarca (116; 2.361).

## 11. EVA: agregación y comparabilidad 2024–2025 [22–24]

**Agregación** a departamento × código × año (suma de municipios y períodos): 3.876 filas; la producción total se conserva exactamente; 82 combinaciones suman 0.

**Comparabilidad** por departamento:

| Clasificación | Por cultivo (160) | Por código (187) |
|---|---:|---:|
| Comparable (ambos años, base 2024 > 0) | 1.527 | 1.850 |
| Comparable con producción 2025 = 0 (caída del 100 %) | 3 | 6 |
| Base 2024 = 0 (variación no calculable) | 43 | 48 |
| Solo en 2024 | 34 | 41 |
| Solo en 2025 | 24 | 27 |

**Variación % por departamento-cultivo** (1.530 comparables):

| Mín | P1 | P5 | P25 | Mediana | P75 | P95 | P99 | Máx |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| −100 | −78,2 | −44,2 | −7,7 | 0,0 | 11,9 | 67,5 | 222,6 | 3.142,9 |

Variaciones > +500 %: 7. Bases pequeñas producen variaciones extremas.

**Diversidad preliminar 2025** (todos los grupos, antes de filtrar la canasta): cultivos con producción > 0 por departamento: mín 10 (Guaviare), mediana 45, máx 97. Los más bajos coinciden con los departamentos de menor cobertura (sección 10).

## 12. EVA: catálogo de cultivos (insumo para la canasta alimentaria) [25, 31, 32]

| Grupo | Cultivos | Producción 2025 (t) |
|---|---:|---:|
| Tropicales tradicionales | 8 | 47.966.664 |
| Frutales | 64 | 14.208.739 |
| Raíces y tubérculos | 11 | 7.785.595 |
| Cereales | 8 | 5.459.678 |
| Hortalizas | 31 | 3.058.076 |
| Oleaginosas | 5 | 2.622.640 |
| Leguminosas | 8 | 227.934 |
| Condimentos, bebidas medicinales y aromáticas | 25 | 18.762 |

Cultivos que exigen decisión explícita (no son alimento directo o su destino es dudoso):

| Grupo | Cultivo / desagregación | Producción 2025 (t) | Observación |
|---|---|---:|---|
| Tropicales tradicionales | Caña de azúcar | 33.007.826 | Industria azucarera; domina el grupo |
| Tropicales tradicionales | Caña panelera, Caña miel | (dentro de Caña: 46.963.397) | Panela es alimento |
| Tropicales tradicionales | Café (pergamino) | 820.825 | Bebida |
| Tropicales tradicionales | Cacao (grano seco) | 150.899 | |
| Tropicales tradicionales | Algodón, Fique, Tabaco, Iraca | 15.911 · 10.126 · 4.554 · 552 | No alimentarios |
| Oleaginosas | Palma de aceite (aceite crudo) | 2.360.532 | Aceite comestible e industrial |
| Oleaginosas | Soya, Ajonjolí, Sacha inchi, Olivo | 255.381 · 3.995 · 2.665 · 66 | |
| Medicinales | Sábila, Ruscus, Ruda, Romero, Stevia/Estevia, Moringa | 3.337 · 1.414 · 293 · 95 · 19 · 0 | Ruscus es follaje ornamental |
| Frutales | Banano de exportación | 2.174.248 | Destino exportación |
| Frutales | Plátano de exportación | 441.645 | Destino exportación |
| Raíces y tubérculos | Yuca industrial | 208.538 | Destino industria |

El catálogo completo (160 cultivos con grupo, subgrupo, estado físico, departamentos y producción) se genera en la sección 25 del notebook (`data/profiling/catalogo_cultivos_eva.csv`, no versionado).

---

## 13. ECV 2025 a nivel departamental [`02`, 1–10]

| Hallazgo | Resultado | Implicación |
|---|---|---|
| Integración hogar → vivienda por `DIRECTORIO` | 87.060 antes y después; 0 sin pareja | Se mantiene la regla de la Primera Entrega. |
| `P1_DEPARTAMENTO` | 80.695 con 2 dígitos; **6.365 con 1 dígito** (`5`, `8`) | Normalizar con `zfill(2)` antes de cruzar. |
| Departamentos (normalizados) | 33 = DIVIPOLA 33 | Cruce completo. |
| `FEX_C` | Coma decimal en los 87.060; sin nulos; mín 1,55; máx 4.843,5; suma 18.952.290 hogares | |
| `FEX_C` hogar vs vivienda | **Difieren en 419 hogares** | Usar el `FEX_C` de la tabla de hogar (Condiciones de vida), como en la Primera Entrega. |
| `PROB_IAMG`, `PROB_IAG` | 718 nulos cada una; coinciden 100 % con "no sabe" en FIES; rango 0–100; `PROB_IAG ≤ PROB_IAMG` siempre | Excluir los 718 del denominador. |
| Prevalencia nacional | **21,10 %** moderada o grave; 3,42 % grave | Reconcilia con el DANE (21,1 %). |
| Contraste con R1 de la Primera Entrega | 32 departamentos con diferencia ≤ 0,01 puntos; Bogotá 0,17 (en R1 está en dos regiones y aquí se combinaron por hogares de muestra) | Misma fuente y misma fórmula. |
| Muestra por departamento | Mín 889 (San Andrés); máx 3.732 (Antioquia) | Todos los departamentos tienen muestra suficiente. |
| Hogares sin FIES por departamento | Máx 3,09 % (Chocó) | |
| Prevalencia por departamento | Mín 5,21 % (San Andrés); máx 56,76 % (Chocó) | Rango amplio: hay variación para analizar. |
| Municipios en la muestra | 634; mediana 67 hogares; 4 con menos de 30 | La ECV no permite estimar por municipio → **integrar por departamento**. |

## 14. Compatibilidad entre fuentes

| Aspecto | ECV 2025 | EVA | Resultado |
|---|---|---|---|
| Llave | `P1_DEPARTAMENTO` (1–2 dígitos) | `c_digo_dane_departamento` (2 dígitos) | Compatible tras `zfill(2)` |
| Departamentos | 33 | 32 | **Bogotá sin dato agrícola** |
| Peso de Bogotá | 2.947 hogares en muestra; **16,77 % de los hogares del país**; prevalencia 9,62 % | — | R6 y R7 cubren 32 departamentos (83,2 % de los hogares). Bogotá queda como "sin dato", nunca 0. |
| Año | 2025 | 2024 y 2025 | R6 usa 2025; R7 usa 2024→2025 |
| Grano | Hogar | Municipio × código × período | Ambas se llevan a departamento antes de unir |
| Formato decimal | Coma | Punto | Conversión distinta por fuente |
| Cardinalidad de la unión | 1 fila por departamento | 1 fila por departamento (tras agregar) | 1:1 por departamento; la unión no toca los hogares |

## 15. Reglas de calidad candidatas (insumo para la Fase 2)

La severidad es una sugerencia; los umbrales y severidades definitivos se deciden en la Fase 2.

| Compuerta | Regla candidata | Evidencia | Severidad sugerida |
|---|---|---|---|
| EVA raw | Registros extraídos = `count(*)` de la API por año | Sección 2 | Crítica |
| EVA raw | Los 18 campos esperados existen | Sección 3 | Crítica |
| EVA raw | Áreas, producción y rendimiento cumplen formato numérico y son ≥ 0 | Sección 3 | Crítica |
| EVA raw | (`municipio`, `código`, `período`) única | Sección 4 | Crítica |
| EVA raw | Código de departamento de 2 dígitos dentro de DIVIPOLA; municipio de 5 dígitos con prefijo del departamento | Secciones 4 y 10 | Crítica |
| EVA raw | `a_o` ∈ años solicitados y `periodo` = año + {"", A, B} | Sección 7 | Crítica |
| EVA raw | Producción > 0 solo si área cosechada > 0 | Sección 6 | Crítica |
| EVA raw | Rendimiento ≈ producción / área cosechada (tolerancia 5 %) | Sección 6 | Advertencia |
| EVA raw | Dominios conocidos de grupo, ciclo y estado físico | Sección 5 | Advertencia |
| EVA raw | Un código de cultivo pertenece a un solo cultivo y estado físico | Sección 5 | Crítica |
| EVA raw | 32 departamentos por año | Sección 10 | Advertencia |
| EVA raw | % de pares 2024 = 2025 idénticos | Sección 8 | Informativa |
| ECV raw | (`DIRECTORIO`, `ORDEN`) única; `FEX_C` > 0 sin nulos; `PROB_*` en 0–100; nulos FIES solo con "no sabe"; `PROB_IAG ≤ PROB_IAMG` | Sección 13 y Primera Entrega | Crítica |
| Preparados | Prevalencia nacional reconcilia con 21,1 % (± tolerancia) | Sección 13 | Crítica |
| Preparados | Una fila por departamento en la tabla integrada; hogares de la ECV sin cambios | Sección 14 | Crítica |
| Preparados | Departamento sin dato agrícola queda nulo, no 0 | Sección 14 | Crítica |
| Preparados | Variación solo con base 2024 > 0; casos no calculables marcados | Sección 11 | Crítica |

Regla **descartada**: "área cosechada ≤ área sembrada". La definición oficial la permite (sección 6); aplicarla rechazaría 6.950 registros válidos.

## 16. Implicaciones para el pipeline

| Etapa | Implicación |
|---|---|
| Extracción API | Paginar con `$order=:id`, `$limit`/`$offset`; conciliar contra `count(*)`; guardar la respuesta cruda con su fecha de extracción (la UPRA puede revisar 2024 y 2025). |
| Extracción API | Errores de red o 5xx son transitorios (reintento acotado). Respuesta vacía, esquema distinto o conteo que no concilia son deterministas (sin reintento). |
| Transformación EVA | Convertir texto a número (punto decimal); agregar municipio y período a departamento × cultivo × año. "Plantas aromáticas" queda fuera de la canasta, así que no hay doble conteo de períodos. |
| Transformación ECV | `zfill(2)` al departamento; coma decimal; `FEX_C` de la tabla de hogar; excluir los 718 sin FIES del denominador. |
| Integración | Unir por código de departamento; Bogotá con indicadores agrícolas nulos. |
| Modelo | Grano EVA de análisis: departamento × cultivo × año (`fact_produccion_agricola` en `docs/modelo_dimensional.dbml`). |

## 17. Decisiones tomadas

Las decisiones que este perfilamiento dejó abiertas se cerraron así:

| # | Decisión | Resolución | Dónde quedó |
|---|---|---|---|
| 1 | Canasta de cultivos alimentarios | UPRA, FAO y la COICOP del DANE no separan cultivos alimentarios. Se ancla en la lista oficial de alimentos de la propia ECV 2025 (pregunta **P3204**): entra el cultivo cuyo producto corresponde a un alimento de esa lista. **139 de 160 cultivos.** | `config/canasta_cultivos.csv`; `docs/reglas_calidad.md` §6 |
| 2 | Desagregaciones de exportación e industria | Banano, plátano y yuca quedan dentro de su cultivo. La caña entra completa: panela, azúcar y miel son alimentos de P3204. | `config/canasta_cultivos.csv` |
| 3 | Nivel de comparación | **Por cultivo (160)**, no por código de desagregación. | Reglas C9, C14 y C16; `dim_cultivo` |
| 4 | `Stevia`/`Estevia` y `Albahaca`/`Chiraran - albahaca` | Stevia y Estevia quedan fuera (medicinales según EVA). Albahaca entra; "Chiraran - albahaca" se excluye para no contar dos veces la misma especie. | `config/canasta_cultivos.csv` |
| 5 | "Plantas aromáticas" con período anual y semestral | Fuera de la canasta por ser una categoría genérica; el doble conteo no afecta R6 ni R7. | `docs/reglas_calidad.md` §8 |
| 6 | Valores repetidos entre 2024 y 2025 | Se reportan como limitación de R7 en el README, sin regla de calidad. | `docs/reglas_calidad.md` §8 |
| 7 | Cobertura mínima | Se incluyen todos los departamentos; se marcan los de menos de 15 cultivos comparables. | Regla A3; `fact_indicadores_departamento.baja_cobertura` |
| — | Bogotá sin datos en EVA | Indicadores agrícolas nulos ("sin dato"), nunca 0. | Regla C15 |

## 18. Reproducción

1. Descargar los tres CSV de la ECV y colocarlos en `data/raw/ecv/` (instrucciones en `data/raw/README.md`). DIVIPOLA ya está en `data/reference/`.
2. Clonar el repositorio de la Primera Entrega (rama `dev`) en la misma carpeta que este. Solo el notebook 02 lo usa, para leer `results/R1_distribucion_territorial.csv` y contrastar con R1.
3. Crear el entorno local (Python 3.13) e instalar `requirements.txt`.
4. Ejecutar `01_profiling_eva.ipynb` (consulta la API y guarda una copia en `data/profiling/`; con `FORZAR_EXTRACCION = True` vuelve a consultar).
5. Ejecutar `02_profiling_ecv_departamental.ipynb`.

Las cifras de EVA pueden cambiar si la UPRA revisa 2024 o 2025; la fecha de extracción queda registrada en la copia local.
