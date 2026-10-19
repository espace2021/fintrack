-- Un compte avec les informations utiles de son client
select
    a.account_id,
    a.customer_id,
    a.type     as account_type,
    c.segment,
    c.city
from {{ source('bronze', 'accounts') }} a
join {{ source('bronze', 'customers') }} c on a.customer_id = c.customer_id
