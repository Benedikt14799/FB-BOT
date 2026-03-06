-- Supabase Schema V2 für das Bot-Dashboard (Streamlit)
-- Auszuführen im SQL Editor des Supabase-Dashboards

-- 1. Tabelle accounts anlegen oder erweitern
CREATE TABLE IF NOT EXISTS public.accounts (
    account_id INTEGER PRIMARY KEY,
    first_login_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    messages_sent_today INTEGER DEFAULT 0,
    last_activity_date DATE DEFAULT CURRENT_DATE,
    login_retries INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    status TEXT DEFAULT 'active',
    proxy_ip TEXT,
    daily_limit INTEGER DEFAULT 80
);

-- Falls die Tabelle schon existierte (altes Schema), fügen wir die neuen Spalten sicherheitshalber noch per ALTER hinzu:
DO $$ 
BEGIN 
    -- 1. Dashboard Spalten für accounts
    BEGIN
        ALTER TABLE public.accounts ADD COLUMN status TEXT DEFAULT 'active';
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
    BEGIN
        ALTER TABLE public.accounts ADD COLUMN proxy_ip TEXT;
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
    BEGIN
        ALTER TABLE public.accounts ADD COLUMN daily_limit INTEGER DEFAULT 80;
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
    
    -- 2. Fehlende Kern-Spalten für recipients (Falls altes Schema)
    BEGIN
        ALTER TABLE public.recipients ADD COLUMN conversation_state TEXT DEFAULT 'new';
    EXCEPTION
        WHEN duplicate_column THEN NULL;
    END;
END $$;

-- 2. Tabelle für GPT Token & Kosten Tracking
CREATE TABLE IF NOT EXISTS public.gpt_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id TEXT NOT NULL,
    type TEXT NOT NULL, -- 'msg1', 'msg2', 'offer', 'reply'
    tokens_input INTEGER NOT NULL DEFAULT 0,
    tokens_output INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(10, 6) DEFAULT 0.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.gpt_usage ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Enable all for authenticated or anon users" ON public.gpt_usage;
CREATE POLICY "Enable all for authenticated or anon users" ON public.gpt_usage FOR ALL USING (true) WITH CHECK (true);

-- 3. Tabelle für Globales Gruppen-Management
CREATE TABLE IF NOT EXISTS public.groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    url TEXT,
    category TEXT,
    status TEXT DEFAULT 'active', -- 'active', 'paused', 'blocked'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.groups ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Enable all for authenticated or anon users" ON public.groups;
CREATE POLICY "Enable all for authenticated or anon users" ON public.groups FOR ALL USING (true) WITH CHECK (true);

-- 4. Tabelle für Account <-> Group Mapping (Viele-zu-Viele)
CREATE TABLE IF NOT EXISTS public.account_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id TEXT NOT NULL,
    group_id UUID NOT NULL REFERENCES public.groups(id) ON DELETE CASCADE,
    is_active BOOLEAN DEFAULT true,
    UNIQUE(account_id, group_id)
);

ALTER TABLE public.account_groups ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Enable all for authenticated or anon users" ON public.account_groups;
CREATE POLICY "Enable all for authenticated or anon users" ON public.account_groups FOR ALL USING (true) WITH CHECK (true);

-- 5. Tabelle für System-Alerts & Warnungen
CREATE TABLE IF NOT EXISTS public.alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id TEXT,
    type TEXT NOT NULL, -- 'FACEBOOK_WARNING', 'ACCOUNT_BLOCKED', 'LOGIN_FAILED', 'PROXY_ERROR', 'LOW_REPLY_RATE'
    detail TEXT,
    resolved BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

ALTER TABLE public.alerts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Enable all for authenticated or anon users" ON public.alerts;
CREATE POLICY "Enable all for authenticated or anon users" ON public.alerts FOR ALL USING (true) WITH CHECK (true);
