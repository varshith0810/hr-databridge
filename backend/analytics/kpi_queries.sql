-- analytics/kpi_queries.sql
-- Workforce KPI queries using CTEs, window functions, and date arithmetic.
-- All queries accept a :snapshot_date parameter (today's date).
-- Results are written to kpi_snapshots by kpi_engine.py.


-- ============================================================
-- 1. HEADCOUNT BY DEPARTMENT (current active employees)
-- ============================================================
-- Name: headcount | Dimension: department name
-- Returns one row per department with active employee count.

-- [headcount_by_department]
SELECT
    department,
    COUNT(*) AS headcount
FROM employees
WHERE status = 'active'
  AND department IS NOT NULL
GROUP BY department
ORDER BY headcount DESC;


-- ============================================================
-- 2. MONTHLY ATTRITION RATE (rolling last 12 months)
-- ============================================================
-- Name: attrition_rate | Dimension: YYYY-MM
-- Attrition rate = terminations in month / avg headcount × 100

-- [attrition_rate_monthly]
WITH monthly_terminations AS (
    SELECT
        TO_CHAR(termination_date, 'YYYY-MM') AS month,
        COUNT(*) AS terminations
    FROM employees
    WHERE termination_date IS NOT NULL
      AND termination_date >= (CURRENT_DATE - INTERVAL '12 months')
    GROUP BY TO_CHAR(termination_date, 'YYYY-MM')
),
monthly_headcount AS (
    SELECT
        TO_CHAR(gs::date, 'YYYY-MM') AS month,
        COUNT(e.id) AS headcount
    FROM
        GENERATE_SERIES(
            DATE_TRUNC('month', CURRENT_DATE - INTERVAL '12 months'),
            DATE_TRUNC('month', CURRENT_DATE),
            '1 month'
        ) AS gs
    LEFT JOIN employees e
        ON e.hire_date <= gs::date
        AND (e.termination_date IS NULL OR e.termination_date > gs::date)
    GROUP BY gs
),
combined AS (
    SELECT
        h.month,
        h.headcount,
        COALESCE(t.terminations, 0) AS terminations
    FROM monthly_headcount h
    LEFT JOIN monthly_terminations t ON h.month = t.month
)
SELECT
    month,
    terminations,
    headcount,
    ROUND(
        CASE WHEN headcount > 0
             THEN (terminations::NUMERIC / headcount) * 100
             ELSE 0
        END, 2
    ) AS attrition_rate_pct
FROM combined
ORDER BY month;


-- ============================================================
-- 3. DIVERSITY BREAKDOWN (gender × department)
-- ============================================================
-- Name: diversity_pct | Dimension: department::gender
-- Returns gender percentage share within each department.

-- [diversity_by_department]
WITH dept_totals AS (
    SELECT
        department,
        COUNT(*) AS dept_total
    FROM employees
    WHERE status = 'active'
      AND department IS NOT NULL
    GROUP BY department
),
dept_gender AS (
    SELECT
        e.department,
        COALESCE(e.gender, 'Not Disclosed') AS gender,
        COUNT(*) AS gender_count
    FROM employees e
    WHERE e.status = 'active'
      AND e.department IS NOT NULL
    GROUP BY e.department, COALESCE(e.gender, 'Not Disclosed')
)
SELECT
    dg.department,
    dg.gender,
    dg.gender_count,
    dt.dept_total,
    ROUND((dg.gender_count::NUMERIC / dt.dept_total) * 100, 1) AS pct_of_dept
FROM dept_gender dg
JOIN dept_totals dt ON dg.department = dt.department
ORDER BY dg.department, pct_of_dept DESC;


-- ============================================================
-- 4. AVERAGE TENURE BY DEPARTMENT
-- ============================================================
-- Name: avg_tenure_months | Dimension: department name
-- Uses AGE() and EXTRACT for date arithmetic.

-- [avg_tenure_by_department]
SELECT
    department,
    COUNT(*) AS employee_count,
    ROUND(
        AVG(
            EXTRACT(YEAR FROM AGE(COALESCE(termination_date, CURRENT_DATE), hire_date)) * 12 +
            EXTRACT(MONTH FROM AGE(COALESCE(termination_date, CURRENT_DATE), hire_date))
        ), 1
    ) AS avg_tenure_months
FROM employees
WHERE hire_date IS NOT NULL
  AND department IS NOT NULL
GROUP BY department
ORDER BY avg_tenure_months DESC;


-- ============================================================
-- 5. HEADCOUNT TREND (monthly snapshot, last 12 months)
-- ============================================================
-- Name: headcount_trend | Dimension: YYYY-MM
-- Shows how total headcount evolved month-over-month.

-- [headcount_trend_monthly]
SELECT
    TO_CHAR(gs::date, 'YYYY-MM') AS month,
    COUNT(e.id) AS headcount,
    COUNT(e.id) - LAG(COUNT(e.id)) OVER (ORDER BY gs) AS headcount_delta
FROM
    GENERATE_SERIES(
        DATE_TRUNC('month', CURRENT_DATE - INTERVAL '12 months'),
        DATE_TRUNC('month', CURRENT_DATE),
        '1 month'
    ) AS gs
LEFT JOIN employees e
    ON e.hire_date <= gs::date
    AND (e.termination_date IS NULL OR e.termination_date > gs::date)
GROUP BY gs
ORDER BY gs;


-- ============================================================
-- 6. TOP ROLES BY HEADCOUNT
-- ============================================================
-- Name: top_roles | Dimension: job_title
-- Shows the 10 most common active job titles.

-- [top_roles]
SELECT
    job_title,
    COUNT(*) AS headcount,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 1) AS pct_of_total
FROM employees
WHERE status = 'active'
  AND job_title IS NOT NULL
GROUP BY job_title
ORDER BY headcount DESC
LIMIT 10;


-- ============================================================
-- 7. NEW HIRES THIS MONTH
-- ============================================================
-- Name: new_hires_mtd | Dimension: all
-- Simple count of employees hired in the current calendar month.

-- [new_hires_mtd]
SELECT
    COUNT(*) AS new_hires,
    TO_CHAR(CURRENT_DATE, 'YYYY-MM') AS month
FROM employees
WHERE hire_date >= DATE_TRUNC('month', CURRENT_DATE)
  AND hire_date <= CURRENT_DATE;


-- ============================================================
-- 8. DATA QUALITY: MISSING FIELDS AUDIT
-- ============================================================
-- Name: data_quality_score | Dimension: source_system
-- Tracks completeness % of key fields per source system.
-- Useful for PSE-style implementation health reporting.

-- [data_quality_by_source]
SELECT
    source_system,
    COUNT(*) AS total_records,
    ROUND(100.0 * SUM(CASE WHEN email IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS email_completeness_pct,
    ROUND(100.0 * SUM(CASE WHEN department IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS dept_completeness_pct,
    ROUND(100.0 * SUM(CASE WHEN gender IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS gender_completeness_pct,
    ROUND(100.0 * SUM(CASE WHEN hire_date IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS hiredate_completeness_pct
FROM employees
GROUP BY source_system;
