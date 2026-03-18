/**
 * API Client — connects to the FastAPI backend
 *
 * All functions mirror the backend route structure exactly.
 * Uses VITE_API_BASE_URL from .env for the base URL.
 */

import type {
  PaginatedCallsResponse,
  CallDetailResponse,
  CallStats,
  AppointmentsResponse,
  BusinessResponse,
  ActiveCallsResponse,
  CallFilters,
} from '../types';

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

/**
 * Generic fetch wrapper with error handling.
 * All API calls go through this to ensure consistent error handling.
 */
async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;

  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(
        (errorBody as { detail?: string }).detail || `API Error: ${response.status} ${response.statusText}`
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new Error('Cannot connect to backend. Is the server running?');
    }
    throw error;
  }
}

/* ═══════════════════════════════════════════
   CALLS API
   ═══════════════════════════════════════════ */

/** Get paginated call logs with optional filters */
export function fetchCallLogs(
  businessId: string,
  filters: CallFilters = {}
): Promise<PaginatedCallsResponse> {
  const params = new URLSearchParams();
  if (filters.limit) params.set('limit', String(filters.limit));
  if (filters.offset) params.set('offset', String(filters.offset));
  if (filters.outcome) params.set('outcome', filters.outcome);
  if (filters.language) params.set('language', filters.language);
  if (filters.dateFrom) params.set('date_from', filters.dateFrom);
  if (filters.dateTo) params.set('date_to', filters.dateTo);

  const query = params.toString();
  return apiFetch<PaginatedCallsResponse>(
    `/api/calls/${businessId}${query ? `?${query}` : ''}`
  );
}

/** Get aggregate call statistics for dashboard */
export function fetchDashboardStats(
  businessId: string,
  days = 7
): Promise<CallStats> {
  return apiFetch<CallStats>(
    `/api/calls/${businessId}/stats?days=${days}`
  );
}

/** Get single call detail with full transcript */
export function fetchCallDetail(
  businessId: string,
  callId: string
): Promise<CallDetailResponse> {
  return apiFetch<CallDetailResponse>(
    `/api/calls/${businessId}/${callId}`
  );
}

/** Get currently active calls */
export function fetchActiveCalls(): Promise<ActiveCallsResponse> {
  return apiFetch<ActiveCallsResponse>('/api/active-calls');
}

/* ═══════════════════════════════════════════
   APPOINTMENTS API
   ═══════════════════════════════════════════ */

/** Get appointments with optional date and status filters */
export function fetchAppointments(
  businessId: string,
  date?: string,
  status?: string
): Promise<AppointmentsResponse> {
  const params = new URLSearchParams();
  if (date) params.set('date', date);
  if (status) params.set('status', status);

  const query = params.toString();
  return apiFetch<AppointmentsResponse>(
    `/api/appointments/${businessId}${query ? `?${query}` : ''}`
  );
}

/** Get available time slots for a date */
export function fetchAvailableSlots(
  businessId: string,
  date: string
): Promise<{ available_slots: string[]; morning_slots: string[]; afternoon_slots: string[] }> {
  return apiFetch(`/api/appointments/${businessId}/slots/${date}`);
}

/** Create a new appointment manually */
export function createAppointment(
  businessId: string,
  data: {
    patient_name: string;
    phone: string;
    date: string;
    time: string;
    service: string;
    notes?: string;
  }
): Promise<{ success: boolean; appointment: Record<string, unknown>; message: string }> {
  return apiFetch(`/api/appointments/${businessId}`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/** Update appointment status (cancel, complete, etc.) */
export function updateAppointmentStatus(
  businessId: string,
  appointmentId: string,
  status: string,
  notes?: string
): Promise<{ success: boolean; appointment_id: string; status: string; message: string }> {
  return apiFetch(`/api/appointments/${businessId}/${appointmentId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status, notes }),
  });
}

/* ═══════════════════════════════════════════
   BUSINESSES API
   ═══════════════════════════════════════════ */

/** Get business profile and config */
export function fetchBusiness(
  businessId: string
): Promise<BusinessResponse> {
  return apiFetch<BusinessResponse>(`/api/businesses/${businessId}`);
}

/** Update business settings (partial update) */
export function updateBusiness(
  businessId: string,
  data: {
    name?: string;
    config_json?: Record<string, unknown>;
    plan?: string;
    is_active?: boolean;
  }
): Promise<{ success: boolean; business: Record<string, unknown>; message: string }> {
  return apiFetch(`/api/businesses/${businessId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/** Get WhatsApp message history */
export function fetchWhatsAppHistory(
  businessId: string,
  phone?: string
): Promise<{ messages: Record<string, unknown>[]; total: number }> {
  const params = phone ? `?phone=${encodeURIComponent(phone)}` : '';
  return apiFetch(`/api/businesses/${businessId}/whatsapp${params}`);
}

/* ═══════════════════════════════════════════
   TEST / SIMULATE
   ═══════════════════════════════════════════ */

/** Simulate an AI call for testing */
export function simulateCall(
  message: string,
  businessPhone = '+911234567890',
  language = 'hi-IN'
): Promise<{ ai_response: string; conversation_turns: number }> {
  return apiFetch('/test/simulate-call', {
    method: 'POST',
    body: JSON.stringify({ message, business_phone: businessPhone, language }),
  });
}
