SELECT
  country_name,
  region_name,
  term,
  week,
  COUNT(*) AS num_with_high_gain

FROM
  `bigquery-public-data.google_trends.international_top_rising_terms`

WHERE
  percent_gain > 70
  AND refresh_date = '2024-10-15' -- "I ran 16 queries between 2024-10-15 and 2024-10-30"

GROUP BY
  1,
  2,
  3,
  4;