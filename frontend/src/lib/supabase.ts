/**
 * Supabase client for realtime subscriptions.
 *
 * In mock mode (no Supabase credentials), the client is created
 * but realtime subscriptions will silently fail — which is fine
 * for local development where we don't need live updates.
 */

import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_KEY || import.meta.env.VITE_SUPABASE_ANON_KEY || 'placeholder-key';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
