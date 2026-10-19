-- Étape intermédiaire : chaque transaction de bronze, nettoyée,
-- avec la raison de son rejet éventuel (NULL = transaction valide).
{{ config(materialized='ephemeral') }}
 
with bronze as (
    select
        *,
        row_number() over (partition by transaction_id
                           order by kafka_partition, kafka_offset) as rang
    from {{ source('bronze', 'transactions') }}
),
 
nettoyees as (
    select
        b.transaction_id,
        b.account_id,
        c.customer_id,
        try_cast(replace(b.amount, ',', '.') as double) as amount,
        coalesce(   -- format ISO, sinon format français
            try_to_timestamp(b.`timestamp`),
            try_to_timestamp(b.`timestamp`, 'dd/MM/yyyy HH:mm')
        ) as transaction_ts,
        lower(trim(b.direction)) as direction,
        upper(trim(b.currency)) as currency,
        lower(trim(b.category)) as category,
        coalesce(b.merchant, 'inconnu') as merchant,
        lower(trim(b.channel)) as channel,
        upper(trim(b.country)) as country,
        lower(trim(b.status)) as status,
        b.raw_value,
        b.kafka_partition,
        b.kafka_offset,
        b.ingested_at,
        b.rang,
        c.account_id is not null as compte_connu
    from bronze b
    left join {{ ref('comptes') }} c on b.account_id = c.account_id
)
 
select
    *,
    case
        when transaction_id is null then 'message_illisible'
        when rang > 1               then 'doublon'
        when amount is null         then 'montant_illisible'
        when amount <= 0            then 'montant_impossible'
        when transaction_ts is null then 'date_illisible'
        when not compte_connu       then 'compte_inconnu'
    end as motif_rejet
from nettoyees
