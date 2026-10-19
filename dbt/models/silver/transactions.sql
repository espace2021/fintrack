-- Les transactions valides, nettoyées : une ligne par transaction
select
    transaction_id, account_id, customer_id, transaction_ts, amount,
    direction, currency, category, merchant, channel, country, status,
    ingested_at
from {{ ref('transactions_preparees') }}
where motif_rejet is null
