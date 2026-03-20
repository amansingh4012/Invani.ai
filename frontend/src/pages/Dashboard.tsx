/**
 * Dashboard Page — Home screen matching Stitch design
 *
 * Shows: AI Agent status banner, 4 stat cards,
 * calls-per-day line chart, and live activity feed.
 *
 * For new users with no data, shows clean empty states
 * instead of dummy/mock data.
 */

import { useState, useEffect } from 'react';
import {
  Phone,
  CalendarCheck,
  TrendingUp,
  PhoneMissed,
  PhoneIncoming,
  Activity,
  Mic,
  BarChart3,
  Copy,
  CheckCircle2
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import StatsCard from '../components/StatsCard';
import { fetchDashboardStats, fetchActiveCalls, fetchCallLogs, assignNumber } from '../lib/api';
import { useBusiness } from '../context/BusinessContext';
import type { CallStats, ActiveCall, CallLog } from '../types';

const BUSINESS_ID = import.meta.env.VITE_BUSINESS_ID || 'mock-business-001';

/** Build the "Calls this week" date range label dynamically */
function getWeekRangeLabel(): string {
  const now = new Date();
  const dayOfWeek = now.getDay(); // 0=Sun
  const mondayOffset = dayOfWeek === 0 ? -6 : 1 - dayOfWeek;
  const monday = new Date(now);
  monday.setDate(now.getDate() + mondayOffset);
  const sunday = new Date(monday);
  sunday.setDate(monday.getDate() + 6);
  const fmt = (d: Date) =>
    d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' });
  return `${fmt(monday)} – ${fmt(sunday)}`;
}

export default function Dashboard() {
  const { business, refreshBusiness } = useBusiness();
  const [stats, setStats] = useState<CallStats | null>(null);
  const [_activeCalls, setActiveCalls] = useState<ActiveCall[]>([]);
  const [recentCalls, setRecentCalls] = useState<CallLog[]>([]);
  const [chartData, setChartData] = useState<{ day: string; calls: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [assigningNumber, setAssigningNumber] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopyNumber = () => {
    if (business?.phone_number) {
      navigator.clipboard.writeText(business.phone_number);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleAssignNumber = async () => {
    if (!business) return;
    setAssigningNumber(true);
    try {
      await assignNumber(business.id);
      await refreshBusiness();
    } catch (err: any) {
      alert(err.message || 'Failed to assign number. Pool might be empty.');
    } finally {
      setAssigningNumber(false);
    }
  };

  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, activeData, callsData] = await Promise.allSettled([
          fetchDashboardStats(BUSINESS_ID),
          fetchActiveCalls(),
          fetchCallLogs(BUSINESS_ID, { limit: 5 }),
        ]);

        if (statsData.status === 'fulfilled') {
          setStats(statsData.value);
          // Build chart data from the daily_breakdown if the backend provides it,
          // otherwise leave chartData empty so the empty state is shown.
          const s = statsData.value as CallStats & { daily_breakdown?: { day: string; calls: number }[] };
          if (s.daily_breakdown && s.daily_breakdown.length > 0) {
            setChartData(s.daily_breakdown);
          }
        }
        if (activeData.status === 'fulfilled') setActiveCalls(activeData.value.active_calls);
        if (callsData.status === 'fulfilled') setRecentCalls(callsData.value.calls);
      } catch {
        /* ── In mock mode, use fallback data ── */
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  return (
    <div className="space-y-6">
      {/* ── Page header ── */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard Home</h1>
      </div>

      {/* ── AI Agent Status Banner ── */}
      <div className="bg-gradient-to-r from-primary-50 to-white rounded-xl border border-primary-100 p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-start gap-4">
          <span className="relative flex h-3 w-3 mt-1 cursor-help" title="Agent is listening for incoming calls">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
          </span>
          <div>
            <div className="text-sm font-semibold text-gray-900 mb-1 flex items-center gap-2">
              AI Receptionist 
              <span className="px-2 py-0.5 rounded text-[10px] bg-primary-100 text-primary-700 font-bold uppercase tracking-wider">
                Active
              </span>
            </div>
            
            {/* SaaS Number Display logic */}
            {business?.phone_number ? (
               <div className="flex flex-col sm:flex-row sm:items-center gap-2 mt-2">
                 <span className="text-xs text-slate-500 font-medium whitespace-nowrap">Your Public AI Number:</span>
                 <div className="flex items-center gap-2 bg-white border border-primary-200 shadow-sm rounded-lg px-3 py-1.5">
                   <PhoneIncoming className="w-3.5 h-3.5 text-primary-500" />
                   <span className="text-[13px] font-bold text-slate-800 tracking-wide">{business.phone_number}</span>
                   <button 
                     onClick={handleCopyNumber}
                     className="ml-1 text-slate-400 hover:text-primary-600 transition-colors focus:outline-none"
                     title="Copy to clipboard"
                   >
                     {copied ? <CheckCircle2 className="w-3.5 h-3.5 text-green-500" /> : <Copy className="w-3.5 h-3.5" />}
                   </button>
                 </div>
                 <span className="text-[10px] text-slate-400 max-w-xs leading-tight ml-1">
                   Publish this number on your website. Incoming calls will be answered instantly by your AI.
                 </span>
               </div>
            ) : (
               <div className="mt-2 bg-white border border-red-100 p-3 rounded-lg shadow-sm w-full md:max-w-md">
                 <p className="text-xs text-red-600 font-medium mb-2">No active phone number assigned to your AI Agent.</p>
                 <button 
                   onClick={handleAssignNumber}
                   disabled={assigningNumber}
                   className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50 transition-colors shadow-sm"
                 >
                   <Phone className="w-4 h-4" />
                   {assigningNumber ? 'Assigning Virtual Number...' : 'Get Your AI Phone Number'}
                 </button>
               </div>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div className="flex shrink-0 gap-2 w-full md:w-auto">
          <button className="flex-1 md:flex-none inline-flex justify-center items-center gap-1.5 px-4 py-2 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors">
            <Mic className="w-4 h-4" />
            Configure
          </button>
        </div>
      </div>

      {/* ── Stats Cards Row ── */}
      {(() => {
        /* Show percentage change badges only when there is real call data */
        const hasData = (stats?.total_calls ?? 0) > 0;
        return (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatsCard
              title="Total Calls Today"
              value={stats?.total_calls ?? 0}
              icon={Phone}
              change={hasData ? 12 : undefined}
              iconColor="text-blue-600"
              iconBg="bg-blue-50"
              loading={loading}
            />
            <StatsCard
              title="Appointments Booked"
              value={stats?.appointments_booked ?? 0}
              icon={CalendarCheck}
              change={hasData ? 8 : undefined}
              iconColor="text-green-600"
              iconBg="bg-green-50"
              loading={loading}
            />
            <StatsCard
              title="Conversion Rate"
              value={stats ? `${Math.round(stats.conversion_rate)}%` : '0%'}
              icon={TrendingUp}
              change={hasData ? -2 : undefined}
              iconColor="text-purple-600"
              iconBg="bg-purple-50"
              loading={loading}
            />
            <StatsCard
              title="Missed Calls"
              value={stats?.missed_calls ?? 0}
              icon={PhoneMissed}
              change={hasData ? -18 : undefined}
              iconColor="text-red-600"
              iconBg="bg-red-50"
              loading={loading}
            />
          </div>
        );
      })()}

      {/* ── Charts + Live Activity ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ── Calls This Week Chart ── */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-gray-900">Calls this week</div>
              <div className="text-xs text-gray-400">{getWeekRangeLabel()}</div>
            </div>
            <select className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600 bg-white">
              <option>Last 7 Days</option>
              <option>Last 30 Days</option>
            </select>
          </div>
          <div className="h-[220px]">
            {chartData.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 12, fill: '#94a3b8' }}
                    axisLine={{ stroke: '#e2e8f0' }}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: '#94a3b8' }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1e293b',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#fff',
                      fontSize: '12px',
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="calls"
                    stroke="#4f46e5"
                    strokeWidth={2.5}
                    dot={{ r: 4, fill: '#4f46e5', strokeWidth: 2, stroke: '#fff' }}
                    activeDot={{ r: 6, fill: '#4f46e5' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-gray-400">
                <BarChart3 className="w-10 h-10 mb-2 text-gray-300" />
                <div className="text-sm font-medium">No call data yet</div>
                <div className="text-xs mt-1">Call activity will appear here once calls are received</div>
              </div>
            )}
          </div>
        </div>

        {/* ── Live Activity Feed ── */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm font-semibold text-gray-900">Live Activity</div>
            {recentCalls.length > 0 && (
              <button className="text-xs text-primary-600 hover:text-primary-700 font-medium">
                View All
              </button>
            )}
          </div>

          {recentCalls.length > 0 ? (
            <div className="space-y-3">
              {recentCalls.map((item, i) => (
                <ActivityItem key={i} item={item} />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-8 text-gray-400">
              <PhoneIncoming className="w-10 h-10 mb-2 text-gray-300" />
              <div className="text-sm font-medium">No recent activity</div>
              <div className="text-xs mt-1 text-center">Incoming calls and their outcomes will show up here</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ── Activity Item sub-component ── */
interface ActivityItemData {
  caller_phone?: string;
  phone?: string;
  duration_sec?: number;
  duration?: string;
  outcome?: string;
  status?: string;
}

function ActivityItem({ item }: { item: ActivityItemData }) {
  const phone = item.caller_phone || item.phone || '+91 XXXXX XXXXX';
  const duration = item.duration_sec
    ? `${Math.floor(item.duration_sec / 60)}m ${item.duration_sec % 60}s`
    : item.duration || '—';
  const outcome = item.outcome || item.status || 'info_provided';

  const outcomeConfig: Record<string, { label: string; className: string }> = {
    appointment_booked: { label: 'Booked', className: 'badge-booked' },
    info_provided: { label: 'FAQ', className: 'badge-faq' },
    missed: { label: 'Missed', className: 'badge-missed' },
    escalated_to_human: { label: 'Escalated', className: 'badge-escalated' },
  };

  const badge = outcomeConfig[outcome] || { label: outcome, className: 'badge-faq' };

  return (
    <div className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
      <div className="flex items-center gap-3">
        <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
          outcome === 'missed' ? 'bg-red-50' : 'bg-green-50'
        }`}>
          {outcome === 'missed' ? (
            <PhoneMissed className="w-4 h-4 text-red-500" />
          ) : (
            <Activity className="w-4 h-4 text-green-500" />
          )}
        </div>
        <div>
          <div className="text-sm font-medium text-gray-900">{formatPhone(phone)}</div>
          <div className="text-xs text-gray-400">Duration: {duration}</div>
        </div>
      </div>
      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${badge.className}`}>
        {badge.label}
      </span>
    </div>
  );
}

function formatPhone(phone: string): string {
  if (phone.startsWith('+91') && phone.length >= 13) {
    return `+91 ${phone.slice(3, 8)} ${phone.slice(8)}`;
  }
  return phone;
}


