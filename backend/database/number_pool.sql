-- Execute this in the Supabase SQL Editor to create the number_pool table

CREATE TABLE IF NOT EXISTS public.number_pool (
    phone_number TEXT PRIMARY KEY,
    is_assigned BOOLEAN DEFAULT FALSE NOT NULL,
    assigned_to UUID REFERENCES public.businesses(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.number_pool ENABLE ROW LEVEL SECURITY;

-- Allow reading the pool (so the backend can find unassigned numbers)
CREATE POLICY "Allow read access to number_pool"
    ON public.number_pool
    FOR SELECT
    TO authenticated, service_role
    USING (true);

-- Allow service role to update the pool (when assigning a number)
CREATE POLICY "Allow service role to update number_pool"
    ON public.number_pool
    FOR UPDATE
    TO service_role
    USING (true);

-- Insert a few sample Exotel numbers into the pool for testing!
INSERT INTO public.number_pool (phone_number, is_assigned)
VALUES 
    ('+9108047361419', false),
    ('+9108047361420', false),
    ('+9108047361421', false),
    ('+9108047361422', false)
ON CONFLICT (phone_number) DO NOTHING;
