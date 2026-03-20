/**
 * BusinessContext — Links a logged-in user to their business
 *
 * After login, looks up `businesses` table by the user's phone number.
 * Stores the business in context so all pages see their own data.
 * All pages use the useBusiness() hook instead of a hardcoded BUSINESS_ID.
 */

import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';
import type { Business } from '../types';
import type { User } from '@supabase/supabase-js';

interface BusinessContextValue {
  business: Business | null;
  businessId: string;
  loading: boolean;
  refreshBusiness: () => Promise<void>;
}

const BusinessContext = createContext<BusinessContextValue>({
  business: null,
  businessId: import.meta.env.VITE_BUSINESS_ID || 'mock-business-001',
  loading: true,
  refreshBusiness: async () => {},
});

const FALLBACK_BUSINESS_ID = import.meta.env.VITE_BUSINESS_ID || 'mock-business-001';
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface BusinessProviderProps {
  user: User | null;
  children: ReactNode;
}

export function BusinessProvider({ user, children }: BusinessProviderProps) {
  const [business, setBusiness] = useState<Business | null>(null);
  const [loading, setLoading] = useState(true);

  // ── Get the user's phone from Supabase auth ──
  const phone = user?.phone ?? user?.email ?? '';

  async function fetchBusiness() {
    if (!user) {
      setBusiness(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      // First try backend API lookup by phone
      const res = await fetch(`${API_BASE}/api/businesses/by-phone?phone=${encodeURIComponent(phone)}`);
      if (res.ok) {
        const data = await res.json();
        setBusiness(data.business);
        return;
      }
    } catch {
      // API not available — fall through to mock mode
    }

    // ── Fallback: use mock/env business ──
    try {
      const res = await fetch(`${API_BASE}/api/businesses/${FALLBACK_BUSINESS_ID}`);
      if (res.ok) {
        const data = await res.json();
        setBusiness(data.business);
        return;
      }
    } catch {
      // Backend not running — use null
    }

    setLoading(false);
  }

  useEffect(() => {
    fetchBusiness().finally(() => setLoading(false));
  }, [user]);

  const businessId = business?.id ?? FALLBACK_BUSINESS_ID;

  return (
    <BusinessContext.Provider value={{ business, businessId, loading, refreshBusiness: fetchBusiness }}>
      {children}
    </BusinessContext.Provider>
  );
}

/** Hook to access the logged-in business data from any page */
export function useBusiness(): BusinessContextValue {
  return useContext(BusinessContext);
}
