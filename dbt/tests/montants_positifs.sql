-- Test « maison » : il échoue s'il renvoie au moins une ligne.
select transaction_id, amount
from {{ ref('transactions') }}
where amount <= 0
