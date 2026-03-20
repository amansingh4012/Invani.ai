/**
 * Call Logs Page — matching Stitch "Call Logs" design
 *
 * Shows: search bar, timeline tabs, filters, data table
 * with expandable rows showing call detail + transcript.
 */

import { useState, useEffect } from 'react';
import {
  Search,
  ChevronDown,
  ChevronRight,
  Phone,
  X,
  Bot,
  User,
  Download,
} from 'lucide-react';
import { fetchCallLogs, fetchCallDetail } from '../lib/api';
import type { CallLog, CallDetail, CallFilters } from '../types';

const BUSINESS_ID = import.meta.env.VITE_BUSINESS_ID || 'mock-business-001';

/* ── Default mock data when API is not available ── */
const mockCalls: CallLog[] = [
  {
    id: 'call-001',
    caller_phone: '+919876543210',
    duration_sec: 135,
    outcome: 'appointment_booked',
    language: 'hi-IN',
    summary: 'Patient called to inquire about root canal pricing. Booked appointment for tomorrow at 4 PM.',
    timestamp: '2026-03-18T10:45:00',
  },
  {
    id: 'call-002',
    caller_phone: '+919876543211',
    duration_sec: 45,
    outcome: 'info_provided',
    language: 'en-IN',
    summary: 'Caller asked about clinic timings and fee structure.',
    timestamp: '2026-03-18T11:20:00',
  },
  {
    id: 'call-003',
    caller_phone: '+919876543212',
    duration_sec: 180,
    outcome: 'missed',
    language: 'hi-IN',
    summary: null,
    timestamp: '2026-03-18T12:05:00',
  },
  {
    id: 'call-004',
    caller_phone: '+919876543213',
    duration_sec: 195,
    outcome: 'appointment_booked',
    language: 'en-IN',
    summary: 'Booked general consultation for March 20 at 11 AM.',
    timestamp: '2026-03-18T14:30:00',
  },
  {
    id: 'call-005',
    caller_phone: '+919876543214',
    duration_sec: 243,
    outcome: 'escalated_to_human',
    language: 'hi-IN',
    summary: 'Caller was upset about billing. Escalated to owner.',
    timestamp: '2026-03-18T02:30:00',
  },
];

const mockTranscript = [
  { role: 'assistant' as const, text: 'Hello, thank you for calling HealthSync Dental. How can I assist you today?' },
  { role: 'user' as const, text: 'Hi, I have a severe pain in my tooth. How much does a root canal cost?' },
  { role: 'assistant' as const, text: 'Root canal treatment typically starts from ₹4,500 depending on the complexity. Would you like to schedule an examination with Dr. Rajesh tomorrow?' },
  { role: 'user' as const, text: 'Yes, please. Do you have anything around 4 PM?' },
  { role: 'assistant' as const, text: "Perfect. I've booked your appointment for tomorrow, Oct 13th, at 4:00 PM. You'll receive a confirmation SMS shortly." },
];

const timelineTabs = ['Today', '7 Days', '30 Days', 'Custom'];
const outcomeOptions = ['All Outcomes', 'appointment_booked', 'info_provided', 'missed', 'escalated_to_human'];
const languageOptions = ['All Languages', 'hi-IN', 'en-IN'];

export default function Calls() {
  const [calls, setCalls] = useState<CallLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTimeline, setActiveTimeline] = useState('7 Days');
  const [outcomeFilter, setOutcomeFilter] = useState('All Outcomes');
  const [languageFilter, setLanguageFilter] = useState('All Languages');
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCallId, setExpandedCallId] = useState<string | null>(null);
  const [selectedCallDetail, setSelectedCallDetail] = useState<CallDetail | null>(null);
  const [page, setPage] = useState(0);
  const pageSize = 20;

  useEffect(() => {
    loadCalls();
  }, [activeTimeline, outcomeFilter, languageFilter, page]);

  async function loadCalls() {
    setLoading(true);
    try {
      const filters: CallFilters = {
        limit: pageSize,
        offset: page * pageSize,
      };
      if (outcomeFilter !== 'All Outcomes') filters.outcome = outcomeFilter;
      if (languageFilter !== 'All Languages') filters.language = languageFilter;

      const data = await fetchCallLogs(BUSINESS_ID, filters);
      setCalls(data.calls);
    } catch {
      setCalls(mockCalls);
    } finally {
      setLoading(false);
    }
  }

  async function handleExpandCall(callId: string) {
    if (expandedCallId === callId) {
      setExpandedCallId(null);
      setSelectedCallDetail(null);
      return;
    }

    setExpandedCallId(callId);
    try {
      const detail = await fetchCallDetail(BUSINESS_ID, callId);
      setSelectedCallDetail(detail.call);
    } catch {
      const call = calls.find((c) => c.id === callId);
      setSelectedCallDetail({
        ...(call as CallLog),
        business_id: BUSINESS_ID,
        call_sid: `exo-${callId.slice(0, 8)}`,
        transcript: mockTranscript,
      });
    }
  }

  const filteredCalls = searchQuery
    ? calls.filter(
        (c) =>
          c.caller_phone.includes(searchQuery) ||
          (c.summary && c.summary.toLowerCase().includes(searchQuery.toLowerCase()))
      )
    : calls;

  const callerNames: Record<string, string> = {
    '+919876543210': 'Amit Sharma',
    '+919876543211': 'Priya Gupta',
    '+919876543212': 'Rahul Verma',
    '+919876543213': 'Sneha Reddy',
    '+919876543214': 'Vikram Malhotra',
  };

  return (
    <div className="space-y-5">
      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Call Logs</h1>
        <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 text-xs font-medium text-white hover:bg-primary-700 transition-colors">
          <Download className="w-3.5 h-3.5" />
          Export CSV
        </button>
      </div>

      {/* ── Search + Filters Bar ── */}
      <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm space-y-3">
        {/* Search */}
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-gray-50 border border-gray-200">
          <Search className="w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search callers, phone numbers..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="flex-1 bg-transparent text-sm text-gray-700 placeholder-gray-400 outline-none"
          />
          {searchQuery && (
            <button onClick={() => setSearchQuery('')}>
              <X className="w-4 h-4 text-gray-400" />
            </button>
          )}
        </div>

        {/* Timeline tabs + Filters */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-1">
            <span className="text-xs text-gray-400 mr-1">TIMELINE:</span>
            {timelineTabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTimeline(tab)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                  activeTimeline === tab
                    ? 'bg-primary-600 text-white'
                    : 'text-gray-500 hover:bg-gray-100'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">STATUS:</span>
            <select
              value={outcomeFilter}
              onChange={(e) => setOutcomeFilter(e.target.value)}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600 bg-white"
            >
              {outcomeOptions.map((o) => (
                <option key={o} value={o}>
                  {o === 'All Outcomes' ? 'All Outcomes' : formatOutcome(o)}
                </option>
              ))}
            </select>

            <select
              value={languageFilter}
              onChange={(e) => setLanguageFilter(e.target.value)}
              className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600 bg-white"
            >
              {languageOptions.map((l) => (
                <option key={l} value={l}>
                  {l === 'All Languages' ? 'All Languages' : l === 'hi-IN' ? 'Hindi' : 'English'}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* ── Table ── */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-6 space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4">
                <div className="skeleton w-24 h-4" />
                <div className="skeleton w-28 h-4" />
                <div className="skeleton w-16 h-4" />
                <div className="skeleton w-16 h-4" />
                <div className="skeleton w-20 h-6 rounded-full" />
              </div>
            ))}
          </div>
        ) : filteredCalls.length === 0 ? (
          <div className="p-12 text-center">
            <Phone className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <div className="text-sm font-medium text-gray-500">No call logs found</div>
            <div className="text-xs text-gray-400 mt-1">
              Calls will appear here once your AI agent starts handling them.
            </div>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100">
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Date & Time</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Caller</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Duration</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Language</th>
                <th className="text-left text-xs font-medium text-gray-400 uppercase px-4 py-3">Outcome</th>
                <th className="w-8" />
              </tr>
            </thead>
            <tbody>
              {filteredCalls.map((call) => (
                <CallRow
                  key={call.id}
                  call={call}
                  callerName={callerNames[call.caller_phone]}
                  isExpanded={expandedCallId === call.id}
                  onToggle={() => handleExpandCall(call.id)}
                  detail={expandedCallId === call.id ? selectedCallDetail : null}
                />
              ))}
            </tbody>
          </table>
        )}

        {/* ── Pagination ── */}
        {filteredCalls.length > 0 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100">
            <div className="text-xs text-gray-400">
              Showing {page * pageSize + 1} to {Math.min((page + 1) * pageSize, filteredCalls.length)} of {filteredCalls.length} logs
            </div>
            <div className="flex gap-1">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-2 py-1 text-xs rounded border border-gray-200 disabled:opacity-40"
              >
                ‹
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={filteredCalls.length < pageSize}
                className="px-2 py-1 text-xs rounded border border-gray-200 disabled:opacity-40"
              >
                ›
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   CallRow — Table row with expandable detail
   ═══════════════════════════════════════════ */

interface CallRowProps {
  call: CallLog;
  callerName?: string;
  isExpanded: boolean;
  onToggle: () => void;
  detail: CallDetail | null;
}

function CallRow({ call, callerName, isExpanded, onToggle, detail }: CallRowProps) {
  const ts = call.timestamp ? new Date(call.timestamp) : null;

  return (
    <>
      <tr
        onClick={onToggle}
        className="border-b border-gray-50 hover:bg-gray-50 cursor-pointer transition-colors"
      >
        <td className="px-4 py-3">
          <div className="text-sm text-gray-900">
            {ts ? ts.toLocaleDateString('en-IN', { month: 'short', day: 'numeric' }) : '—'}
          </div>
          <div className="text-xs text-gray-400">
            {ts ? ts.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit' }) : '—'}
          </div>
        </td>
        <td className="px-4 py-3">
          <div className="text-sm font-medium text-gray-900">{callerName || 'Unknown'}</div>
          <div className="text-xs text-gray-400">{formatPhone(call.caller_phone)}</div>
        </td>
        <td className="px-4 py-3 text-sm text-gray-600">
          {Math.floor(call.duration_sec / 60)}m {String(call.duration_sec % 60).padStart(2, '0')}s
        </td>
        <td className="px-4 py-3">
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            call.language === 'hi-IN' ? 'badge-hindi' : 'badge-english'
          }`}>
            {call.language === 'hi-IN' ? 'HINDI' : 'ENGLISH'}
          </span>
        </td>
        <td className="px-4 py-3">
          <OutcomeBadge outcome={call.outcome} />
        </td>
        <td className="px-4 py-2">
          {isExpanded ? (
            <ChevronDown className="w-4 h-4 text-gray-400" />
          ) : (
            <ChevronRight className="w-4 h-4 text-gray-400" />
          )}
        </td>
      </tr>

      {/* ── Expanded Detail Panel ── */}
      {isExpanded && (
        <tr>
          <td colSpan={6} className="bg-gray-50 px-6 py-5">
            <CallDetailPanel call={call} detail={detail} />
          </td>
        </tr>
      )}
    </>
  );
}

/* ═══════════════════════════════════════════
   CallDetailPanel — Transcript + AI Summary
   ═══════════════════════════════════════════ */

function CallDetailPanel({ call, detail }: { call: CallLog; detail: CallDetail | null }) {
  const transcript = detail?.transcript || [];

  return (
    <div className="max-w-2xl space-y-4">
      {/* AI Summary */}
      <div className="bg-white rounded-lg border border-gray-200 p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-5 h-5 rounded-full bg-green-100 flex items-center justify-center">
            <Bot className="w-3 h-3 text-green-600" />
          </div>
          <span className="text-xs font-semibold text-gray-500 uppercase">AI Summary</span>
        </div>
        <p className="text-sm text-gray-700 leading-relaxed">
          {call.summary || 'No summary available for this call.'}
        </p>
      </div>

      {/* Transcript */}
      {transcript.length > 0 && (
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="text-xs font-semibold text-gray-400 uppercase mb-3">
            Full Transcript
          </div>
          <div className="space-y-3">
            {transcript.map((msg, i) => (
              <div key={i} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                {msg.role === 'assistant' && (
                  <div className="w-7 h-7 rounded-full bg-primary-100 flex items-center justify-center shrink-0">
                    <Bot className="w-3.5 h-3.5 text-primary-600" />
                  </div>
                )}
                <div
                  className={`max-w-[80%] rounded-xl px-3 py-2 text-sm ${
                    msg.role === 'user'
                      ? 'bg-primary-600 text-white rounded-br-sm'
                      : 'bg-gray-100 text-gray-700 rounded-bl-sm'
                  }`}
                >
                  {msg.text}
                </div>
                {msg.role === 'user' && (
                  <div className="w-7 h-7 rounded-full bg-gray-200 flex items-center justify-center shrink-0">
                    <User className="w-3.5 h-3.5 text-gray-600" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2">
        <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-700 hover:bg-gray-50">
          <Download className="w-3.5 h-3.5" />
          Download Audio
        </button>
        <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 text-xs font-medium text-white hover:bg-primary-700">
          ✏️ Add Clinical Notes
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════
   Helper Components
   ═══════════════════════════════════════════ */

function OutcomeBadge({ outcome }: { outcome: string }) {
  const config: Record<string, { label: string; className: string }> = {
    appointment_booked: { label: '+ Book', className: 'badge-booked' },
    info_provided: { label: '★ FAQ', className: 'badge-faq' },
    missed: { label: '✕ Miss', className: 'badge-missed' },
    escalated_to_human: { label: '⚡ Escalated', className: 'badge-escalated' },
  };

  const badge = config[outcome] || { label: outcome, className: 'badge-faq' };

  return (
    <span className={`text-xs font-medium px-2.5 py-1 rounded-full ${badge.className}`}>
      {badge.label}
    </span>
  );
}

function formatOutcome(outcome: string): string {
  return outcome
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

function formatPhone(phone: string): string {
  if (phone.startsWith('+91') && phone.length >= 13) {
    return `+91 ${phone.slice(3, 8)} ${phone.slice(8)}`;
  }
  return phone;
}
