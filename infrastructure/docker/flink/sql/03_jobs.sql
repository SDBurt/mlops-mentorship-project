-- Step 6: Submit all streaming jobs with validation logic
EXECUTE STATEMENT SET
BEGIN
    -- VALID payment_charges (pass validation rules)
    INSERT INTO polaris_catalog.payments_db.payment_charges
    SELECT
        event_id,
        event_type,
        provider,
        charge_id,
        customer_id,
        -- Normalize null amounts and validate bounds
        CASE
            WHEN amount IS NULL OR amount <= 0 OR amount > 1000000.00 THEN NULL
            ELSE amount
        END as amount,
        -- Normalize currency nulls and convert to uppercase
        CASE
            WHEN currency IS NULL OR UPPER(currency) IN ('NULL', '') THEN NULL
            ELSE UPPER(currency)
        END as currency,
        status,
        failure_code,
        failure_message,
        payment_method_id,
        payment_method_type,
        card_brand,
        card_last4,
        card_exp_month,
        card_exp_year,
        card_country,
        billing_country,
        billing_postal_code,
        merchant_id,
        merchant_name,
        description,
        metadata,
        risk_score,
        risk_level,
        `3ds_authenticated`,
        created_at,
        updated_at,
        -- Flag suspicious patterns
        CASE
            WHEN amount = 0 AND status = 'succeeded' THEN true
            WHEN customer_id IS NULL THEN true
            WHEN status = 'failed' AND failure_code IS NULL THEN true
            ELSE false
        END as validation_flag
    FROM kafka_catalog.payments_db.payment_charges
    WHERE
        -- Only accept valid currency codes
        (currency IS NULL OR UPPER(currency) IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        -- Amount must be positive and within bounds
        AND (amount IS NULL OR (amount > 0 AND amount <= 1000000.00))
        -- Customer ID must exist
        AND customer_id IS NOT NULL;

    -- QUARANTINE payment_charges (failed validation)
    INSERT INTO polaris_catalog.payments_db.quarantine_payment_charges
    SELECT
        event_id,
        event_type,
        provider,
        charge_id,
        customer_id,
        amount,
        currency,
        status,
        failure_code,
        failure_message,
        payment_method_id,
        payment_method_type,
        card_brand,
        card_last4,
        card_exp_month,
        card_exp_year,
        card_country,
        billing_country,
        billing_postal_code,
        merchant_id,
        merchant_name,
        description,
        metadata,
        risk_score,
        risk_level,
        `3ds_authenticated`,
        created_at,
        updated_at,
        CURRENT_TIMESTAMP as quarantine_timestamp,
        -- Determine rejection reason
        CASE
            WHEN customer_id IS NULL THEN 'MISSING_CUSTOMER_ID'
            WHEN currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY')
                THEN 'INVALID_CURRENCY'
            WHEN amount IS NOT NULL AND amount <= 0 THEN 'INVALID_AMOUNT_NEGATIVE'
            WHEN amount IS NOT NULL AND amount > 1000000.00 THEN 'INVALID_AMOUNT_TOO_LARGE'
            ELSE 'UNKNOWN_VALIDATION_FAILURE'
        END as rejection_reason
    FROM kafka_catalog.payments_db.payment_charges
    WHERE
        -- Reject if any validation rule fails
        customer_id IS NULL
        OR (currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        OR (amount IS NOT NULL AND (amount <= 0 OR amount > 1000000.00));

    -- VALID payment_refunds
    INSERT INTO polaris_catalog.payments_db.payment_refunds
    SELECT
        event_id,
        event_type,
        provider,
        refund_id,
        charge_id,
        customer_id,
        CASE
            WHEN amount IS NULL OR amount <= 0 OR amount > 1000000.00 THEN NULL
            ELSE amount
        END as amount,
        CASE
            WHEN currency IS NULL OR UPPER(currency) IN ('NULL', '') THEN NULL
            ELSE UPPER(currency)
        END as currency,
        status,
        reason,
        failure_reason,
        merchant_id,
        metadata,
        created_at,
        updated_at,
        CASE
            WHEN amount = 0 THEN true
            WHEN customer_id IS NULL THEN true
            WHEN charge_id IS NULL THEN true
            WHEN status = 'failed' AND failure_reason IS NULL THEN true
            ELSE false
        END as validation_flag
    FROM kafka_catalog.payments_db.payment_refunds
    WHERE
        (currency IS NULL OR UPPER(currency) IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        AND (amount IS NULL OR (amount > 0 AND amount <= 1000000.00))
        AND customer_id IS NOT NULL
        AND charge_id IS NOT NULL;

    -- QUARANTINE payment_refunds
    INSERT INTO polaris_catalog.payments_db.quarantine_payment_refunds
    SELECT
        event_id,
        event_type,
        provider,
        refund_id,
        charge_id,
        customer_id,
        amount,
        currency,
        status,
        reason,
        failure_reason,
        merchant_id,
        metadata,
        created_at,
        updated_at,
        CURRENT_TIMESTAMP as quarantine_timestamp,
        CASE
            WHEN customer_id IS NULL THEN 'MISSING_CUSTOMER_ID'
            WHEN charge_id IS NULL THEN 'MISSING_CHARGE_ID'
            WHEN currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY')
                THEN 'INVALID_CURRENCY'
            WHEN amount IS NOT NULL AND amount <= 0 THEN 'INVALID_AMOUNT_NEGATIVE'
            WHEN amount IS NOT NULL AND amount > 1000000.00 THEN 'INVALID_AMOUNT_TOO_LARGE'
            ELSE 'UNKNOWN_VALIDATION_FAILURE'
        END as rejection_reason
    FROM kafka_catalog.payments_db.payment_refunds
    WHERE
        customer_id IS NULL
        OR charge_id IS NULL
        OR (currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        OR (amount IS NOT NULL AND (amount <= 0 OR amount > 1000000.00));

    -- VALID payment_disputes
    INSERT INTO polaris_catalog.payments_db.payment_disputes
    SELECT
        event_id,
        event_type,
        provider,
        dispute_id,
        charge_id,
        customer_id,
        CASE
            WHEN amount IS NULL OR amount <= 0 OR amount > 1000000.00 THEN NULL
            ELSE amount
        END as amount,
        CASE
            WHEN currency IS NULL OR UPPER(currency) IN ('NULL', '') THEN NULL
            ELSE UPPER(currency)
        END as currency,
        status,
        reason,
        evidence_due_by,
        is_charge_refundable,
        merchant_id,
        metadata,
        network_reason_code,
        created_at,
        updated_at,
        CASE
            WHEN customer_id IS NULL THEN true
            WHEN charge_id IS NULL THEN true
            WHEN reason IS NULL THEN true
            ELSE false
        END as validation_flag
    FROM kafka_catalog.payments_db.payment_disputes
    WHERE
        (currency IS NULL OR UPPER(currency) IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        AND (amount IS NULL OR (amount > 0 AND amount <= 1000000.00))
        AND customer_id IS NOT NULL
        AND charge_id IS NOT NULL;

    -- QUARANTINE payment_disputes
    INSERT INTO polaris_catalog.payments_db.quarantine_payment_disputes
    SELECT
        event_id,
        event_type,
        provider,
        dispute_id,
        charge_id,
        customer_id,
        amount,
        currency,
        status,
        reason,
        evidence_due_by,
        is_charge_refundable,
        merchant_id,
        metadata,
        network_reason_code,
        created_at,
        updated_at,
        CURRENT_TIMESTAMP as quarantine_timestamp,
        CASE
            WHEN customer_id IS NULL THEN 'MISSING_CUSTOMER_ID'
            WHEN charge_id IS NULL THEN 'MISSING_CHARGE_ID'
            WHEN currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY')
                THEN 'INVALID_CURRENCY'
            WHEN amount IS NOT NULL AND amount <= 0 THEN 'INVALID_AMOUNT_NEGATIVE'
            WHEN amount IS NOT NULL AND amount > 1000000.00 THEN 'INVALID_AMOUNT_TOO_LARGE'
            ELSE 'UNKNOWN_VALIDATION_FAILURE'
        END as rejection_reason
    FROM kafka_catalog.payments_db.payment_disputes
    WHERE
        customer_id IS NULL
        OR charge_id IS NULL
        OR (currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        OR (amount IS NOT NULL AND (amount <= 0 OR amount > 1000000.00));

    -- VALID payment_subscriptions
    INSERT INTO polaris_catalog.payments_db.payment_subscriptions
    SELECT
        event_id,
        event_type,
        provider,
        subscription_id,
        customer_id,
        plan_id,
        plan_name,
        CASE
            WHEN amount IS NULL OR amount < 0 OR amount > 1000000.00 THEN NULL
            ELSE amount
        END as amount,
        CASE
            WHEN currency IS NULL OR UPPER(currency) IN ('NULL', '') THEN NULL
            ELSE UPPER(currency)
        END as currency,
        `interval`,
        interval_count,
        status,
        cancel_at_period_end,
        canceled_at,
        trial_start,
        trial_end,
        current_period_start,
        current_period_end,
        payment_method_id,
        merchant_id,
        metadata,
        discount,
        created_at,
        updated_at,
        CASE
            WHEN customer_id IS NULL THEN true
            WHEN plan_id IS NULL THEN true
            WHEN `interval` IS NULL THEN true
            ELSE false
        END as validation_flag
    FROM kafka_catalog.payments_db.payment_subscriptions
    WHERE
        (currency IS NULL OR UPPER(currency) IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        AND (amount IS NULL OR (amount >= 0 AND amount <= 1000000.00))
        AND customer_id IS NOT NULL
        AND plan_id IS NOT NULL;

    -- QUARANTINE payment_subscriptions
    INSERT INTO polaris_catalog.payments_db.quarantine_payment_subscriptions
    SELECT
        event_id,
        event_type,
        provider,
        subscription_id,
        customer_id,
        plan_id,
        plan_name,
        amount,
        currency,
        `interval`,
        interval_count,
        status,
        cancel_at_period_end,
        canceled_at,
        trial_start,
        trial_end,
        current_period_start,
        current_period_end,
        payment_method_id,
        merchant_id,
        metadata,
        discount,
        created_at,
        updated_at,
        CURRENT_TIMESTAMP as quarantine_timestamp,
        CASE
            WHEN customer_id IS NULL THEN 'MISSING_CUSTOMER_ID'
            WHEN plan_id IS NULL THEN 'MISSING_PLAN_ID'
            WHEN currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY')
                THEN 'INVALID_CURRENCY'
            WHEN amount IS NOT NULL AND amount < 0 THEN 'INVALID_AMOUNT_NEGATIVE'
            WHEN amount IS NOT NULL AND amount > 1000000.00 THEN 'INVALID_AMOUNT_TOO_LARGE'
            ELSE 'UNKNOWN_VALIDATION_FAILURE'
        END as rejection_reason
    FROM kafka_catalog.payments_db.payment_subscriptions
    WHERE
        customer_id IS NULL
        OR plan_id IS NULL
        OR (currency IS NOT NULL AND UPPER(currency) NOT IN ('USD', 'CAD', 'GBP', 'EUR', 'JPY'))
        OR (amount IS NOT NULL AND (amount < 0 OR amount > 1000000.00));
END;
