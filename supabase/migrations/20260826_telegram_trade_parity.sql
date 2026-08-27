ALTER TABLE public.operations_trade_cases
    DROP CONSTRAINT IF EXISTS operations_trade_cases_platform_check;

ALTER TABLE public.operations_trade_cases
    ADD CONSTRAINT operations_trade_cases_platform_check
    CHECK (platform IN ('discord', 'telegram'));

ALTER TABLE public.operations_seller_assessments
    DROP CONSTRAINT IF EXISTS operations_seller_assessments_platform_check;

ALTER TABLE public.operations_seller_assessments
    ADD CONSTRAINT operations_seller_assessments_platform_check
    CHECK (platform IN ('discord', 'telegram'));
