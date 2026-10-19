-- La « quarantaine » : les lignes écartées, avec leur motif et le message d'origine
select
    motif_rejet, transaction_id, account_id, raw_value,
    kafka_partition, kafka_offset, ingested_at
from {{ ref('transactions_preparees') }}
where motif_rejet is not null
