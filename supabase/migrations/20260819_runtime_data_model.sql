CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS public.community_members (
    member_id UUID PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    community_id VARCHAR(200) NOT NULL,
    platform_user_id VARCHAR(200) NOT NULL,
    display_name VARCHAR(200),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (platform, community_id, platform_user_id)
);

CREATE TABLE IF NOT EXISTS public.operations_messages (
    message_id VARCHAR(200) PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    community_id VARCHAR(200) NOT NULL,
    channel_id VARCHAR(200) NOT NULL,
    thread_key VARCHAR(200),
    parent_message_id VARCHAR(200),
    author_id VARCHAR(200) NOT NULL,
    author_member_id UUID REFERENCES public.community_members(member_id) ON DELETE SET NULL,
    text TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    source_url TEXT,
    raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision VARCHAR(40),
    category VARCHAR(80),
    severity VARCHAR(20),
    risk_score DOUBLE PRECISION,
    confidence DOUBLE PRECISION,
    explanation TEXT,
    model_used VARCHAR(200),
    incident_id VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_incidents (
    incident_id VARCHAR(200) PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    community_id VARCHAR(200) NOT NULL,
    channel_id VARCHAR(200) NOT NULL,
    thread_key VARCHAR(200),
    status VARCHAR(30) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    categories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    message_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    first_seen TIMESTAMPTZ NOT NULL,
    last_seen TIMESTAMPTZ NOT NULL,
    assigned_to VARCHAR(200),
    assigned_user_id UUID REFERENCES public.app_users(user_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source_url TEXT
);

ALTER TABLE public.operations_messages
    ADD COLUMN IF NOT EXISTS author_member_id UUID REFERENCES public.community_members(member_id) ON DELETE SET NULL;
ALTER TABLE public.operations_messages
    ADD COLUMN IF NOT EXISTS incident_id VARCHAR(200);
ALTER TABLE public.operations_incidents
    ADD COLUMN IF NOT EXISTS assigned_user_id UUID REFERENCES public.app_users(user_id) ON DELETE SET NULL;
ALTER TABLE public.operations_incidents
    ADD COLUMN IF NOT EXISTS source_url TEXT;

CREATE TABLE IF NOT EXISTS public.operations_gate_runs (
    run_id VARCHAR(200) PRIMARY KEY,
    message_id VARCHAR(200) NOT NULL,
    gate VARCHAR(30) NOT NULL,
    passed BOOLEAN NOT NULL,
    label VARCHAR(200) NOT NULL,
    category VARCHAR(80) NOT NULL,
    risk_score DOUBLE PRECISION NOT NULL,
    evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    explanation TEXT NOT NULL,
    model_used VARCHAR(200) NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_audit (
    audit_id VARCHAR(200) PRIMARY KEY,
    incident_id VARCHAR(200),
    message_id VARCHAR(200),
    event_type VARCHAR(100) NOT NULL,
    actor VARCHAR(200) NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_policies (
    policy_id VARCHAR(200) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(80) NOT NULL,
    action VARCHAR(40) NOT NULL,
    trigger_terms_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_moderation_marks (
    mark_id VARCHAR(200) PRIMARY KEY,
    incident_id VARCHAR(200) NOT NULL,
    message_id VARCHAR(200) NOT NULL,
    text TEXT NOT NULL,
    normalized_text TEXT NOT NULL,
    category VARCHAR(80) NOT NULL,
    decision VARCHAR(40) NOT NULL,
    reason TEXT NOT NULL,
    marked_by VARCHAR(200) NOT NULL,
    marked_at TIMESTAMPTZ NOT NULL,
    source_url TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_moderation_embeddings (
    mark_id VARCHAR(200) PRIMARY KEY,
    text_hash VARCHAR(64) NOT NULL,
    model VARCHAR(100) NOT NULL,
    vector_json VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_knowledge_imports (
    import_id VARCHAR(200) PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    format VARCHAR(20) NOT NULL,
    target VARCHAR(30) NOT NULL,
    normalized_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    normalized_by VARCHAR(200) NOT NULL,
    source_hash VARCHAR(64),
    status VARCHAR(30) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE public.operations_knowledge_imports ADD COLUMN IF NOT EXISTS source_hash VARCHAR(64);
ALTER TABLE public.operations_knowledge_imports ADD COLUMN IF NOT EXISTS status VARCHAR(30) NOT NULL DEFAULT 'completed';

CREATE TABLE IF NOT EXISTS public.knowledge_import_raw (
    import_id VARCHAR(200) PRIMARY KEY REFERENCES public.operations_knowledge_imports(import_id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    source_hash VARCHAR(64) NOT NULL,
    content BYTEA NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.knowledge_normalized_records (
    import_id VARCHAR(200) NOT NULL REFERENCES public.operations_knowledge_imports(import_id) ON DELETE CASCADE,
    record_index INTEGER NOT NULL,
    record_type VARCHAR(30) NOT NULL,
    document_id VARCHAR(200),
    policy_id VARCHAR(200),
    canonical_json JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (import_id, record_index)
);

ALTER TABLE public.knowledge_documents
    ADD COLUMN IF NOT EXISTS import_id VARCHAR(200) REFERENCES public.operations_knowledge_imports(import_id) ON DELETE SET NULL;
ALTER TABLE public.knowledge_documents
    ADD COLUMN IF NOT EXISTS source_file VARCHAR(255);
ALTER TABLE public.knowledge_documents
    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);
ALTER TABLE public.knowledge_documents
    ADD COLUMN IF NOT EXISTS normalization_version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE public.knowledge_documents
    ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR(50) NOT NULL DEFAULT 'supabase-v1';

CREATE TABLE IF NOT EXISTS public.operations_faqs (
    faq_id VARCHAR(200) PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    tags_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    source_cluster_id VARCHAR(200),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE public.operations_faqs ADD COLUMN IF NOT EXISTS source_cluster_id VARCHAR(200);

CREATE TABLE IF NOT EXISTS public.operations_faq_embeddings (
    faq_id VARCHAR(200) PRIMARY KEY REFERENCES public.operations_faqs(faq_id) ON DELETE CASCADE,
    text_hash VARCHAR(64) NOT NULL,
    model VARCHAR(100) NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_faq_questions (
    question_id VARCHAR(200) PRIMARY KEY,
    message_id VARCHAR(200) UNIQUE,
    question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    platform VARCHAR(20) NOT NULL,
    community_id VARCHAR(200) NOT NULL DEFAULT 'community-001',
    channel_id VARCHAR(200) NOT NULL DEFAULT 'general',
    author_id VARCHAR(200) NOT NULL,
    outcome_stage VARCHAR(30),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE public.operations_faq_questions ADD COLUMN IF NOT EXISTS community_id VARCHAR(200) NOT NULL DEFAULT 'community-001';
ALTER TABLE public.operations_faq_questions ADD COLUMN IF NOT EXISTS channel_id VARCHAR(200) NOT NULL DEFAULT 'general';
ALTER TABLE public.operations_faq_questions ADD COLUMN IF NOT EXISTS outcome_stage VARCHAR(30);

CREATE TABLE IF NOT EXISTS public.faq_question_embeddings (
    question_id VARCHAR(200) PRIMARY KEY REFERENCES public.operations_faq_questions(question_id) ON DELETE CASCADE,
    text_hash VARCHAR(64) NOT NULL,
    model VARCHAR(100) NOT NULL,
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.faq_topic_clusters (
    cluster_id VARCHAR(200) PRIMARY KEY,
    topic_label VARCHAR(500) NOT NULL,
    normalized_label TEXT NOT NULL,
    representative_question TEXT NOT NULL,
    question_count INTEGER NOT NULL DEFAULT 0,
    sample_questions JSONB NOT NULL DEFAULT '[]'::jsonb,
    centroid_embedding VECTOR(1536) NOT NULL,
    embedding_model VARCHAR(100) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'open' CHECK (status IN ('open','approved','dismissed')),
    approved_faq_id VARCHAR(200) REFERENCES public.operations_faqs(faq_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.faq_topic_members (
    cluster_id VARCHAR(200) NOT NULL REFERENCES public.faq_topic_clusters(cluster_id) ON DELETE CASCADE,
    question_id VARCHAR(200) NOT NULL REFERENCES public.operations_faq_questions(question_id) ON DELETE CASCADE,
    similarity_score DOUBLE PRECISION NOT NULL,
    llm_verified BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cluster_id, question_id)
);

CREATE OR REPLACE VIEW public.faq_top_10_topics AS
SELECT
    cluster_id,
    topic_label,
    representative_question,
    question_count,
    sample_questions,
    status,
    approved_faq_id,
    updated_at
FROM public.faq_topic_clusters
WHERE status = 'open'
ORDER BY question_count DESC, updated_at DESC
LIMIT 10;

CREATE TABLE IF NOT EXISTS public.operations_faq_suggestions (
    suggestion_id VARCHAR(200) PRIMARY KEY,
    representative_question TEXT NOT NULL,
    normalized_question TEXT NOT NULL,
    question_count INTEGER NOT NULL DEFAULT 1,
    samples_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_command_content (
    command VARCHAR(100) PRIMARY KEY,
    body TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    platforms_json JSONB NOT NULL DEFAULT '["telegram","discord"]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_member_reports (
    report_id VARCHAR(200) PRIMARY KEY,
    platform VARCHAR(20) NOT NULL,
    reporter_id VARCHAR(200) NOT NULL,
    channel_id VARCHAR(200) NOT NULL,
    details TEXT NOT NULL,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS public.operations_notification_preferences (
    platform VARCHAR(20) NOT NULL,
    member_id VARCHAR(200) NOT NULL,
    daily_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    weekly_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (platform, member_id)
);

CREATE TABLE IF NOT EXISTS public.reviews (
    review_id VARCHAR(200) PRIMARY KEY,
    user_id VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    channel VARCHAR(200) NOT NULL,
    recent_context JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_action VARCHAR(40) NOT NULL,
    model_category VARCHAR(80) NOT NULL,
    model_risk_level VARCHAR(20) NOT NULL,
    model_reason TEXT NOT NULL,
    model_confidence DOUBLE PRECISION NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_used VARCHAR(200) NOT NULL DEFAULT 'unknown',
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    admin_action VARCHAR(40),
    admin_note TEXT,
    reviewer VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS public.audit_logs (
    audit_id VARCHAR(200) PRIMARY KEY,
    review_id VARCHAR(200) NOT NULL,
    user_id VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    channel VARCHAR(200) NOT NULL,
    model_action VARCHAR(40) NOT NULL,
    model_category VARCHAR(80) NOT NULL,
    model_risk_level VARCHAR(20) NOT NULL,
    model_reason TEXT NOT NULL,
    model_confidence DOUBLE PRECISION NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    model_used VARCHAR(200) NOT NULL DEFAULT 'unknown',
    fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
    admin_action VARCHAR(40) NOT NULL,
    admin_note TEXT NOT NULL,
    reviewer VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL
);
DO $$ BEGIN
    ALTER TABLE public.audit_logs ADD CONSTRAINT fk_audit_logs_review
        FOREIGN KEY (review_id) REFERENCES public.reviews(review_id) ON DELETE CASCADE NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_operations_messages_context
    ON public.operations_messages(platform, community_id, channel_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_operations_messages_incident ON public.operations_messages(incident_id);
CREATE INDEX IF NOT EXISTS idx_operations_incidents_status ON public.operations_incidents(status, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_operations_moderation_category ON public.operations_moderation_marks(category, active);
CREATE INDEX IF NOT EXISTS idx_faq_questions_created_at ON public.operations_faq_questions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_faq_clusters_rank ON public.faq_topic_clusters(status, question_count DESC);
CREATE INDEX IF NOT EXISTS idx_knowledge_sections_document ON public.knowledge_sections(document_id, chunk_index);

DO $$ BEGIN
    ALTER TABLE public.operations_messages ADD CONSTRAINT fk_operations_messages_incident
        FOREIGN KEY (incident_id) REFERENCES public.operations_incidents(incident_id) ON DELETE SET NULL NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_gate_runs ADD CONSTRAINT fk_gate_runs_message
        FOREIGN KEY (message_id) REFERENCES public.operations_messages(message_id) ON DELETE CASCADE NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_audit ADD CONSTRAINT fk_operations_audit_incident
        FOREIGN KEY (incident_id) REFERENCES public.operations_incidents(incident_id) ON DELETE SET NULL NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_audit ADD CONSTRAINT fk_operations_audit_message
        FOREIGN KEY (message_id) REFERENCES public.operations_messages(message_id) ON DELETE SET NULL NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_moderation_marks ADD CONSTRAINT fk_moderation_marks_incident
        FOREIGN KEY (incident_id) REFERENCES public.operations_incidents(incident_id) ON DELETE CASCADE NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_moderation_marks ADD CONSTRAINT fk_moderation_marks_message
        FOREIGN KEY (message_id) REFERENCES public.operations_messages(message_id) ON DELETE CASCADE NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_moderation_embeddings ADD CONSTRAINT fk_moderation_embedding_mark
        FOREIGN KEY (mark_id) REFERENCES public.operations_moderation_marks(mark_id) ON DELETE CASCADE NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_faq_questions ADD CONSTRAINT fk_faq_question_message
        FOREIGN KEY (message_id) REFERENCES public.operations_messages(message_id) ON DELETE SET NULL NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE public.operations_faqs ADD CONSTRAINT fk_faq_source_cluster
        FOREIGN KEY (source_cluster_id) REFERENCES public.faq_topic_clusters(cluster_id) ON DELETE SET NULL NOT VALID;
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE OR REPLACE FUNCTION public.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;
