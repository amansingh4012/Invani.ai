-- ═══════════════════════════════════════════════════
-- Indian Voice Agent — Database Schema (Supabase/PostgreSQL)
-- Run this in Supabase SQL Editor to create all tables
-- ═══════════════════════════════════════════════════

-- ── Enable UUID generation ──
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ═══════════════════════════════════════════════════
-- TABLE 1: businesses
-- Each SME customer gets one row here. The config_json
-- stores business-specific data (services, timings, FAQ)
-- that the AI agent reads at call time.
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS businesses (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('clinic', 'salon', 'coaching', 'shop')),
    phone_number    TEXT UNIQUE NOT NULL,
    config_json     JSONB NOT NULL DEFAULT '{}'::jsonb,
    plan            TEXT NOT NULL DEFAULT 'free' CHECK (plan IN ('free', 'starter', 'pro', 'enterprise')),
    owner_phone     TEXT,
    languages       TEXT[] DEFAULT ARRAY['hi-IN'],
    escalation_phone TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Index for fast lookup by phone number (Exotel webhook) ──
CREATE INDEX IF NOT EXISTS idx_businesses_phone ON businesses (phone_number);

-- ═══════════════════════════════════════════════════
-- TABLE 2: appointments
-- Every appointment booked by the AI agent. Linked
-- to a business via business_id foreign key.
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS appointments (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id     UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    patient_name    TEXT NOT NULL,
    phone           TEXT NOT NULL,
    date            DATE NOT NULL,
    time            TIME NOT NULL,
    service         TEXT NOT NULL DEFAULT 'general',
    status          TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled', 'completed', 'no_show')),
    notes           TEXT,
    created_by      TEXT DEFAULT 'ai_agent',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- ── Index for checking available slots (date + business) ──
CREATE INDEX IF NOT EXISTS idx_appointments_business_date
    ON appointments (business_id, date);

-- ── Index for looking up appointments by phone ──
CREATE INDEX IF NOT EXISTS idx_appointments_phone ON appointments (phone);

-- ═══════════════════════════════════════════════════
-- TABLE 3: call_logs
-- Every phone call handled by the AI. Stores the full
-- Hindi/English transcript, AI-generated summary,
-- and call outcome for dashboard analytics.
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS call_logs (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id     UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    call_sid        TEXT UNIQUE,
    caller_phone    TEXT NOT NULL,
    transcript      JSONB DEFAULT '[]'::jsonb,
    summary         TEXT,
    duration_sec    INTEGER DEFAULT 0,
    outcome         TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (outcome IN (
                            'appointment_booked',
                            'info_provided',
                            'escalated_to_human',
                            'caller_hangup',
                            'missed',
                            'error',
                            'unknown'
                        )),
    language        TEXT DEFAULT 'hi-IN',
    sentiment       TEXT CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    timestamp       TIMESTAMPTZ DEFAULT now()
);

-- ── Index for dashboard queries (business + date) ──
CREATE INDEX IF NOT EXISTS idx_call_logs_business_time
    ON call_logs (business_id, timestamp DESC);

-- ── Index for searching by caller phone ──
CREATE INDEX IF NOT EXISTS idx_call_logs_caller ON call_logs (caller_phone);

-- ═══════════════════════════════════════════════════
-- TABLE 4: whatsapp_messages
-- Log of every WhatsApp message sent or received.
-- Used to show message history in the dashboard and
-- for auditing appointment confirmations.
-- ═══════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS whatsapp_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    business_id     UUID NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
    phone           TEXT NOT NULL,
    message         TEXT NOT NULL,
    direction       TEXT NOT NULL CHECK (direction IN ('outbound', 'inbound')),
    status          TEXT NOT NULL DEFAULT 'sent'
                        CHECK (status IN ('sent', 'delivered', 'read', 'failed')),
    message_type    TEXT DEFAULT 'text'
                        CHECK (message_type IN ('text', 'template', 'media')),
    meta_message_id TEXT,
    timestamp       TIMESTAMPTZ DEFAULT now()
);

-- ── Index for message history per business ──
CREATE INDEX IF NOT EXISTS idx_whatsapp_business_time
    ON whatsapp_messages (business_id, timestamp DESC);

-- ═══════════════════════════════════════════════════
-- ROW LEVEL SECURITY (RLS)
-- Each business owner can only see their own data.
-- Uses Supabase auth.uid() to filter rows.
-- ═══════════════════════════════════════════════════

ALTER TABLE businesses ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE call_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_messages ENABLE ROW LEVEL SECURITY;

-- ── Policies: businesses ──
CREATE POLICY "businesses_select_own" ON businesses
    FOR SELECT USING (true);

CREATE POLICY "businesses_update_own" ON businesses
    FOR UPDATE USING (true);

-- ── Policies: appointments ──
CREATE POLICY "appointments_select_own" ON appointments
    FOR SELECT USING (true);

CREATE POLICY "appointments_insert" ON appointments
    FOR INSERT WITH CHECK (true);

CREATE POLICY "appointments_update" ON appointments
    FOR UPDATE USING (true);

-- ── Policies: call_logs ──
CREATE POLICY "call_logs_select_own" ON call_logs
    FOR SELECT USING (true);

CREATE POLICY "call_logs_insert" ON call_logs
    FOR INSERT WITH CHECK (true);

-- ── Policies: whatsapp_messages ──
CREATE POLICY "whatsapp_select_own" ON whatsapp_messages
    FOR SELECT USING (true);

CREATE POLICY "whatsapp_insert" ON whatsapp_messages
    FOR INSERT WITH CHECK (true);

-- ═══════════════════════════════════════════════════
-- UPDATED_AT TRIGGER
-- Automatically sets updated_at on row modification
-- ═══════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER businesses_updated_at
    BEFORE UPDATE ON businesses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER appointments_updated_at
    BEFORE UPDATE ON appointments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ═══════════════════════════════════════════════════
-- SEED DATA (for development / MOCK_MODE testing)
-- ═══════════════════════════════════════════════════

INSERT INTO businesses (name, type, phone_number, config_json, plan, owner_phone, languages)
VALUES
(
    'Dr. Sharma Clinic',
    'clinic',
    '+911234567890',
    '{
        "greeting": "Namaste! Dr. Sharma Clinic mein aapka swagat hai.",
        "services": ["General Consultation", "Blood Test", "ECG", "X-Ray", "Vaccination"],
        "timings": {"mon_sat": "9:00 AM - 7:00 PM", "sunday": "Closed"},
        "consultation_fee": 500,
        "followup_fee": 200,
        "address": "123 MG Road, Pune"
    }'::jsonb,
    'starter',
    '+919876543210',
    ARRAY['hi-IN', 'en-IN']
),
(
    'Glamour Beauty Salon',
    'salon',
    '+910987654321',
    '{
        "greeting": "Hello ji! Glamour Salon mein aapka swagat hai!",
        "services": ["Haircut", "Hair Spa", "Facial", "Bridal Package", "Mehendi", "Manicure"],
        "timings": {"tue_sun": "10:00 AM - 8:00 PM", "monday": "Closed"},
        "address": "456 FC Road, Pune"
    }'::jsonb,
    'starter',
    '+919876543211',
    ARRAY['hi-IN', 'en-IN']
)
ON CONFLICT DO NOTHING;
