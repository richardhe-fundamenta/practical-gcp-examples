
-- Customer Demographics by County

SELECT
WITH
  AGGREGATION_THRESHOLD -- Aggregation is enforced
  county,
  ethnic_group,
  COUNT(customer_id) AS total_customers,
  ROUND(AVG(DATE_DIFF(CURRENT_DATE(), date_of_birth, YEAR))) AS avg_age,
FROM
  cleanroom_ecommerce.customers_puid_customer_id
GROUP BY
  county,
  ethnic_group
ORDER BY
  total_customers DESC;

-- Top 5 Counties by Total Sales

SELECT
WITH
  AGGREGATION_THRESHOLD -- Aggregation is enforced
  c.county,
  ROUND(SUM(o.total_amount),2) AS total_sales
FROM
  exchange_shared_ecommerce.orders o
JOIN
  cleanroom_ecommerce.customers_puid_customer_id c
ON
  o.customer_id = c.customer_id
GROUP BY
  c.county
ORDER BY
  total_sales DESC
LIMIT
  5;

-- Product Category Contribution by Customer Demographics
SELECT
WITH
  AGGREGATION_THRESHOLD -- Aggregation is enforced
    c.gender,
    CASE
        WHEN DATE_DIFF(CURRENT_DATE(), c.date_of_birth, YEAR) < 25 THEN 'Under 25'
        WHEN DATE_DIFF(CURRENT_DATE(), c.date_of_birth, YEAR) BETWEEN 25 AND 34 THEN '25-34'
        WHEN DATE_DIFF(CURRENT_DATE(), c.date_of_birth, YEAR) BETWEEN 35 AND 44 THEN '35-44'
        WHEN DATE_DIFF(CURRENT_DATE(), c.date_of_birth, YEAR) BETWEEN 45 AND 54 THEN '45-54'
        ELSE '55+'
    END AS age_group,
    c.income_level,
    p.category,
    ROUND(SUM(oi.quantity * oi.price_each),2) AS total_revenue,
    SUM(oi.quantity) AS total_units_sold,
    ROUND((SUM(oi.quantity * oi.price_each) / SUM(SUM(oi.quantity * oi.price_each)) OVER(PARTITION BY p.category)) * 100, 2) AS category_revenue_percentage
FROM
    cleanroom_ecommerce.customers_puid_customer_id c
JOIN
    exchange_shared_ecommerce.orders o
ON
    c.customer_id = o.customer_id
JOIN
    exchange_shared_ecommerce.order_items oi
ON
    o.order_id = oi.order_id
JOIN
    exchange_shared_ecommerce.products p
ON
    oi.product_id = p.product_id
WHERE
    o.status = 'Completed'
GROUP BY
    c.gender, age_group, c.income_level, p.category
ORDER BY
    p.category, total_revenue DESC;