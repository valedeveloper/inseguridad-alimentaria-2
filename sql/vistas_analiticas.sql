-- =====================================================================
-- Vistas analiticas del Data Warehouse (consumidas por el dashboard).
-- Se recrean al final de cada carga (src/carga.py), en la misma transaccion.
--
-- R1-R5: consultas de la Primera Entrega (sql/analytical_queries.sql),
--        sin cambios de logica, convertidas en vistas.
-- R6-R7: nuevas, sobre el modelo agricola y fact_indicadores_departamento.
--
-- Prevalencias: suma(factor_expansion x probabilidad FIES) / suma(factor)
-- sobre hogares con FIES valido; las probabilidades ya estan en escala 0-100.
-- =====================================================================

-- R1. Distribucion territorial de la inseguridad alimentaria.
DROP VIEW IF EXISTS vw_r1_distribucion_territorial;
CREATE VIEW vw_r1_distribucion_territorial AS
SELECT
	g.nombre_region AS region,
	g.nombre_departamento AS departamento,
	COUNT(*) AS hogares,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_moderada_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_moderada_grave_pct,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_grave_pct
FROM fact_seguridad_alimentaria_hogar f
JOIN dim_geografia g ON g.id_geografia = f.id_geografia
WHERE f.prob_ia_moderada_grave IS NOT NULL
GROUP BY g.nombre_region, g.nombre_departamento
ORDER BY prevalencia_moderada_grave_pct DESC;

-- R2. Asociacion entre servicios publicos y vulnerabilidad alimentaria.
DROP VIEW IF EXISTS vw_r2_servicios_publicos;
CREATE VIEW vw_r2_servicios_publicos AS
SELECT
	f.tiene_acueducto,
	f.tiene_alcantarillado,
	COUNT(*) AS hogares,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_moderada_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_moderada_grave_pct,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_grave_pct
FROM fact_seguridad_alimentaria_hogar f
WHERE f.prob_ia_moderada_grave IS NOT NULL
GROUP BY f.tiene_acueducto, f.tiene_alcantarillado
ORDER BY f.tiene_acueducto DESC, f.tiene_alcantarillado DESC;

-- R3. Relacion entre cantidad de choques economicos e inseguridad alimentaria.
DROP VIEW IF EXISTS vw_r3_choques_economicos;
CREATE VIEW vw_r3_choques_economicos AS
SELECT
	c.numero_choques,
	COUNT(*) AS hogares,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_moderada_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_moderada_grave_pct,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_grave_pct
FROM fact_seguridad_alimentaria_hogar f
JOIN dim_choque_economico c ON c.id_choque_economico = f.id_choque_economico
WHERE f.prob_ia_moderada_grave IS NOT NULL
GROUP BY c.numero_choques
ORDER BY c.numero_choques;

-- R4. Estrategias de afrontamiento segun severidad.
DROP VIEW IF EXISTS vw_r4_estrategias_severidad;
CREATE VIEW vw_r4_estrategias_severidad AS
SELECT
	s.nombre_severidad AS severidad,
	e.numero_estrategias,
	COUNT(*) AS hogares,
	ROUND(
		(SUM(f.factor_expansion) / NULLIF(SUM(SUM(f.factor_expansion)) OVER
			(PARTITION BY s.nombre_severidad), 0))::numeric * 100, 2
	) AS distribucion_ponderada_pct
FROM fact_seguridad_alimentaria_hogar f
JOIN dim_nivel_severidad_ia s
	ON s.id_nivel_severidad_ia = f.id_nivel_severidad_ia
JOIN dim_estrategia_afrontamiento e
	ON e.id_estrategia_afrontamiento = f.id_estrategia_afrontamiento
GROUP BY s.nombre_severidad, e.numero_estrategias
ORDER BY s.nombre_severidad, e.numero_estrategias;

-- R5. Gradiente de vulnerabilidad segun quintil de ingreso.
DROP VIEW IF EXISTS vw_r5_quintiles_ingreso;
CREATE VIEW vw_r5_quintiles_ingreso AS
SELECT
	i.codigo_quintil AS quintil_ingreso,
	i.nombre_quintil,
	COUNT(*) AS hogares,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_moderada_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_moderada_grave_pct,
	ROUND(
		(SUM(f.factor_expansion * f.prob_ia_grave)
		 / NULLIF(SUM(f.factor_expansion), 0))::numeric, 2
	) AS prevalencia_grave_pct
FROM fact_seguridad_alimentaria_hogar f
JOIN dim_nivel_ingreso i ON i.id_nivel_ingreso = f.id_nivel_ingreso
WHERE f.prob_ia_moderada_grave IS NOT NULL
GROUP BY i.id_nivel_ingreso, i.codigo_quintil, i.nombre_quintil
ORDER BY i.id_nivel_ingreso;

-- R6. Diversidad de cultivos alimentarios (canasta P3204) e inseguridad
-- alimentaria por departamento, 2025. Bogota sin datos agricolas: nulo.
DROP VIEW IF EXISTS vw_r6_diversidad_departamental;
CREATE VIEW vw_r6_diversidad_departamental AS
SELECT
	d.codigo_departamento,
	d.nombre_departamento,
	2025 AS anio,
	i.diversidad_cultivos_2025,
	i.prevalencia_ia_moderada_grave AS prevalencia_moderada_grave_pct,
	i.prevalencia_ia_grave AS prevalencia_grave_pct,
	i.hogares_muestra,
	i.baja_cobertura,
	(i.diversidad_cultivos_2025 IS NULL) AS sin_dato_agricola
FROM fact_indicadores_departamento i
JOIN dim_departamento d ON d.id_departamento = i.id_departamento
ORDER BY d.codigo_departamento;

-- R7 (por cultivo). Produccion 2024 y 2025, variacion y comparabilidad de
-- cada cultivo de la canasta en cada departamento.
DROP VIEW IF EXISTS vw_r7_variacion_cultivo;
CREATE VIEW vw_r7_variacion_cultivo AS
SELECT
	d.codigo_departamento,
	d.nombre_departamento,
	c.nombre_cultivo,
	c.grupo_cultivo,
	v.produccion_2024_t,
	v.produccion_2025_t,
	v.variacion_pct,
	v.estado_comparabilidad,
	v.en_descenso
FROM fact_variacion_produccion v
JOIN dim_departamento d ON d.id_departamento = v.id_departamento
JOIN dim_cultivo c ON c.id_cultivo = v.id_cultivo
ORDER BY d.codigo_departamento, c.nombre_cultivo;

-- R7 (por departamento). Porcentaje de cultivos comparables en descenso
-- 2024 -> 2025 frente a la prevalencia FIES 2025.
DROP VIEW IF EXISTS vw_r7_descenso_departamental;
CREATE VIEW vw_r7_descenso_departamental AS
SELECT
	d.codigo_departamento,
	d.nombre_departamento,
	i.cultivos_comparables,
	i.cultivos_en_descenso,
	i.pct_cultivos_en_descenso,
	i.prevalencia_ia_moderada_grave AS prevalencia_moderada_grave_pct,
	i.prevalencia_ia_grave AS prevalencia_grave_pct,
	i.baja_cobertura,
	(i.cultivos_comparables IS NULL) AS sin_dato_agricola
FROM fact_indicadores_departamento i
JOIN dim_departamento d ON d.id_departamento = i.id_departamento
ORDER BY d.codigo_departamento;
