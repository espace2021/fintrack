-- Indicateur métier : les dépenses acceptées, par catégorie
select
    category,
    count(*)                 as nb_transactions,
    round(sum(amount), 2)    as total,
    round(avg(amount), 2)    as montant_moyen
from {{ ref('transactions') }}
where direction = 'debit' and status = 'accepted'
group by category
