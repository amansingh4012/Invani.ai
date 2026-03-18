/* ── Data Models matching backend Pydantic schemas ── */

export interface CallLog {
  id: string;
  caller_phone: string;
  duration_sec: number;
  outcome: CallOutcome;
  language: string;
  summary: string | null;
  timestamp: string | null;
}

export interface CallDetail extends CallLog {
  business_id: string;
  call_sid: string;
  transcript: TranscriptMessage[];
}

export interface TranscriptMessage {
  role: 'assistant' | 'user';
  text: string;
}

export interface CallStats {
  total_calls: number;
  appointments_booked: number;
  missed_calls: number;
  escalated: number;
  avg_duration_sec: number;
  conversion_rate: number;
  period_days: number;
  business_id: string;
}

export interface Appointment {
  id: string;
  business_id: string;
  patient_name: string;
  phone: string;
  date: string;
  time: string;
  service: string;
  status: AppointmentStatus;
  created_by?: string;
  notes?: string;
}

export interface Business {
  id: string;
  name: string;
  type: string;
  phone_number: string;
  config_json: BusinessConfig;
  plan: string;
  is_active: boolean;
}

export interface BusinessConfig {
  greeting?: string;
  services?: string[];
  timings?: {
    open: string;
    close: string;
    days: string;
  };
  consultation_fee?: number;
  followup_fee?: number;
  languages?: string[];
  escalation_number?: string;
  location?: string;
}

export interface WhatsAppMessage {
  id: string;
  business_id: string;
  phone: string;
  message: string;
  direction: 'inbound' | 'outbound';
  status: string;
  message_type?: string;
  timestamp: string | null;
}

export interface ActiveCall {
  call_sid: string;
  business: string;
  caller: string;
  duration_sec: number;
}

/* ── Enum types ── */

export type CallOutcome =
  | 'appointment_booked'
  | 'info_provided'
  | 'missed'
  | 'escalated_to_human'
  | string;

export type AppointmentStatus =
  | 'confirmed'
  | 'scheduled'
  | 'completed'
  | 'cancelled'
  | 'no_show';

/* ── API Response Wrappers ── */

export interface PaginatedCallsResponse {
  calls: CallLog[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export interface AppointmentsResponse {
  appointments: Appointment[];
  total: number;
  business_id: string;
  filters: {
    date: string | null;
    status: string | null;
  };
}

export interface CallDetailResponse {
  call: CallDetail;
}

export interface BusinessResponse {
  business: Business;
}

export interface ActiveCallsResponse {
  active_calls: ActiveCall[];
  total: number;
}

/* ── Filter types for call logs ── */
export interface CallFilters {
  outcome?: string;
  language?: string;
  dateFrom?: string;
  dateTo?: string;
  limit?: number;
  offset?: number;
}
