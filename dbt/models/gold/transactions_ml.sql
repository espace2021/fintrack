-- Jeu de données pour l'atelier 5 : une ligne par dépense,
-- quelques caractéristiques simples et l'étiquette est_fraude (0 ou 1)
select
    t.transaction_id,
    t.customer_id,
    t.amount,
    t.category,
    t.channel,
    t.country,
    c.segment,
    hour(t.transaction_ts)                                       as heure,
    case when t.country <> 'FR' then 1 else 0 end                as est_etranger,
    case when t.channel = 'carte_en_ligne' then 1 else 0 end     as est_en_ligne,
    case when f.transaction_id is not null then 1 else 0 end     as est_fraude
from {{ ref('transactions') }} t
left join {{ ref('comptes') }} c on t.account_id = c.account_id
left join (select distinct transaction_id
           from {{ source('bronze', 'fraud_reports') }}) f
       on t.transaction_id = f.transaction_id
where t.direction = 'debit'
