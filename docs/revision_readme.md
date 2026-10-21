# Diagnóstico y verificación del README

Revisión documental del 21 de octubre de 2026. Alcance: inspección de código, configuración, pruebas, documentación, imágenes y salidas de notebooks. No se modificó la lógica del sistema ni se ejecutaron cargas.

## 1. Diagnóstico breve del repositorio

| Elemento | Requisito esperado | Evidencia encontrada | Estado | Acción documental |
|---|---|---|---|---|
| R1–R5 | Analítica de hogares. | `src/ecv/`, ocho vistas SQL incluyendo R1–R5. | Implementado; validación integral pendiente. | Sustituir el estado antiguo «pendiente de implementación» por el estado comprobable. |
| R6–R7 | Integrar EVA y ECV. | `src/eva/`, canasta, hechos y vistas R6/R7. | Implementado; falta evidencia integral. | Documentar cálculos, comparabilidad y faltantes. |
| Arquitectura | Fuentes, calidad, almacenamiento y consumo. | DAG de 12 tareas; Compose con LocalExecutor. | Implementado. | Añadir arquitectura y flujo Mermaid; retirar referencias a Celery como arquitectura actual. |
| Calidad | Reglas trazables a riesgos. | C1–C16 y A1–A3 en `src/calidad/`. | Implementado; reportes no localizados. | Separar expectativas existentes de resultados ejecutados. |
| Perfilamiento | Cifras verificables. | Dos notebooks con 33 y 11 celdas ejecutadas, todas con salidas. | Evidencia conservada. | Atribuir cifras al perfil histórico, sin presentarlas como consulta actual. |
| Modelo | Granularidades y claves. | 11 tablas en DDL y modelo DBML. | Implementado. | Explicar siete dimensiones y cuatro hechos, sin inventar FK entre dimensiones geográficas. |
| FIES | Prevalencia coherente con código. | Probabilidades 0–100 ponderadas. | Implementado. | Distinguir del indicador binario inicialmente propuesto; sin factor 100 adicional. |
| Integración | Claves reales. | Cruce por departamento; años filtrados/fijados en código. | Implementado. | Aclarar que año no es llave del cruce final. |
| A1 | Cobertura EVA. | `min_value=32`, aunque la regla documental decía igualdad. | Discrepancia documentada. | Describir el mínimo aplicado. |
| C10 | Conservar hogares. | Contrasta hecho y transformados, no directamente fuente cruda. | Parcial respecto del control de origen a destino. | Declarar el límite del control. |
| Pruebas A/B/C | Corridas exitosas, rechazo y repetición segura. | Código de prueba y procedimientos; sin lotes/reportes completos disponibles. | No verificable como ejecución. | No certificar éxito ni 92.496 filas cargadas. |
| Tablero | Producto consultando PostgreSQL. | Guía y vistas; sin informe final. | Parcial. | Presentar visualizaciones como previstas. |
| Contexto gráfico | Fuente estadística coherente. | Imagen atribuye a ENSIN; el proyecto usa ECV. | Inconsistencia. | Enlazar y señalar revisión de la atribución, sin respaldar cifras no verificadas. |
| Equipo | Responsabilidades reales. | Nombres/asignaciones del README proporcionado. | Documentado. | Conservar sin atribuciones basadas en commits. |

**Fortalezas:** ramas separadas, compuertas previas a transformar, intercambio por rutas, manifiestos e integridad, comparabilidad explícita y carga completa transaccional.

**Límites de evidencia:** no hay CSV reales en `data/raw/ecv/`, copia en `data/profiling/`, reportes de compuertas o `carga.json` en los lotes inspeccionados. La captura del DAG solo muestra el grafo. Guías que afirman resultados exactos, tiempos o correlaciones no sustituyen reportes ejecutados.

## 2. README completo

Se actualizó directamente [README.md](../README.md) con las 25 secciones requeridas, en español, tablas, tres diagramas Mermaid y comandos ajustados a la configuración actual. Se conservaron los requisitos, el enlace de primera entrega, las fuentes y las responsabilidades válidas.

## 3. Pendientes prioritarios de documentación y validación

1. Descargar los tres CSV ECV; generar y conservar la copia EVA necesaria para las pruebas de integración.
2. Preparar el entorno de pruebas e instalar dependencias. Ejecutar pruebas unitarias, luego integración y carga contra una base de pruebas: estas últimas reemplazan tablas.
3. Ejecutar A y conservar `run_id`, fechas, estados de 12 tareas, reportes de compuertas, manifiestos, `carga.json` y consultas SQL.
4. Ejecutar B en una corrida nueva; conservar rechazo C7, bloqueo de dependientes y comparación del almacén antes/después.
5. Ejecutar C; guardar conteos y huellas de las 11 tablas antes/después, junto al resultado de pytest.
6. Fijar el commit de la primera entrega y conservar comparación de salidas R1–R5 para demostrar equivalencia.
7. Completar tablero y capturas, conexión a PostgreSQL y gráficos R6/R7; respaldar correlaciones si se incluyen.
8. Confirmar respaldo metodológico de cortes FIES y decisiones de canasta; corregir la atribución ENSIN/ECV de la imagen de contexto.
9. Revisar A1 en el catálogo, fortalecer conciliación de hogares contra fuente cruda y versionar código/referencias/canasta por corrida.

## 4. Verificación final

«Documentada» indica cobertura de la sección, no cumplimiento completo de la funcionalidad.

| N.º | Sección documentada | Respaldo | Limitación restante |
|---|---|---|---|
| 1 | Sí: problema y objetivo. | README previo, requisitos. | Sin inferencia causal. |
| 2 | Sí: línea base. | Enlace y Git local. | Falta commit congelado y comparación. |
| 3 | Sí: R1–R5. | ECV y vistas. | Falta evidencia ejecutada. |
| 4 | Sí: R6–R7. | EVA, canasta y pruebas. | Faltan gráficos/evidencia integral. |
| 5 | Sí: fuentes. | Extractores y adquisición. | API actual no consultada en esta revisión. |
| 6 | Sí: aporte API. | Indicadores y claves reales. | Asociación departamental. |
| 7 | Sí: arquitectura. | Compose, módulos y Mermaid. | Tablero previsto. |
| 8 | Sí: perfilamiento. | Notebooks con salidas. | Cifras históricas, fuente revisable. |
| 9 | Sí: riesgos/reglas. | Compuertas y catálogo. | Diferencias A1/C10 señaladas. |
| 10 | Sí: GX/trazabilidad. | Contexto, expectativas y compuertas. | Sin reportes ejecutados disponibles. |
| 11 | Sí: validación cruda. | Extractores y compuertas 1–2. | Esquema ECV no exhaustivo. |
| 12 | Sí: transformación/contrato. | Limpieza, transformaciones y modelos. | Referencias no congeladas por lote. |
| 13 | Sí: modelo. | DDL y DBML; diagrama ER. | Sin historia/migraciones. |
| 14 | Sí: preparados. | Compuerta 3. | No comprueba toda FK antes de cargar. |
| 15 | Sí: almacén/carga. | Carga y SQL. | Falta conteo ejecutado preservado. |
| 16 | Sí: DAG/interfaces. | DAG, grafo y artefactos. | Captura sin estados finales. |
| 17 | Sí: fallos/reintentos. | DAG, errores y extractor. | Sin evidencia operacional A/B. |
| 18 | Sí: éxito y faltantes. | Inventario de evidencias. | Corrida A pendiente. |
| 19 | Sí: fallo controlado. | Parámetro y pruebas B. | Reporte B pendiente. |
| 20 | Sí: repetibilidad. | Lotes, carga y prueba C. | Reporte C pendiente. |
| 21 | Sí: productos. | Vistas y guía del tablero. | Tablero no disponible. |
| 22 | Sí: trazabilidad R1–R7. | Matriz requisito–fuente–regla–código–vista. | Falta cerrar con evidencias ejecutadas. |
| 23 | Sí: instalación/ejecución. | Compose, dependencias y configuración. | Reproducción integral no ejecutada. |
| 24 | Sí: supuestos/límites. | Hallazgos y contraste de código. | Requiere decisiones del equipo. |
| 25 | Sí: integrantes. | Asignaciones del README previo. | Sin reparto individual adicional. |

### Comprobaciones realizadas

| Comprobación | Resultado |
|---|---|
| `docker compose config --quiet` | Correcto: configuración aceptada por Compose. |
| `docker compose ps -a` | Servicios detenidos; además hay contenedores antiguos fuera del diseño actual. No se iniciaron ni eliminaron. |
| `python -m pytest --version` | No disponible: falta `pytest` en el Python local. No se declara suite aprobada. |
| Catálogo de canasta | 160 filas, 139 incluidas, comprobado por lectura del CSV. |
| Salidas de notebooks | 33/33 y 11/11 celdas de código con ejecución y salidas. |
| Capturas | Grafo sin evidencia de estado final; contexto con atribución por corregir. |
| Estructura, enlaces y nombres | Verificación automatizada registrada debajo. |

No se instalaron dependencias ni se modificaron datos, servicios o código de procesamiento para producir esta documentación.

### Resultado de la comprobación documental automatizada

- 25 secciones principales consecutivas, numeradas del 1 al 25.
- 92 enlaces locales comprobados entre README y este diagnóstico: todos apuntan a archivos o carpetas existentes.
- Tres bloques Mermaid y delimitadores de código emparejados. Su estructura se inspeccionó; no se ejecutó un renderizador Mermaid.
- Tablas Markdown con número de columnas consistente.
- Las 12 tareas del DAG, 11 tablas del DDL y 8 vistas SQL aparecen en el README; nombres contrastados automáticamente con sus fuentes.
- `git diff --check`: correcto, sin errores de espacios.

Estas verificaciones documentales no sustituyen las pruebas de ejecución del sistema ni una validación estadística de resultados.
