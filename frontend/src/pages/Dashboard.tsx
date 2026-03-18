/**
 * Dashboard Page — Home screen matching Stitch design
 *
 * Shows: AI Agent status banner, 4 stat cards,
 * calls-per-day line chart, and live activity feed.
 */

import { useState, useEffect } from 'react';
import {
  Phone,
  CalendarCheck,
  TrendingUp,
  PhoneMissed,
  Activity,
  Mic,
  Settings,
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
import { fetchDashboardStats, fetchActiveCalls, fetchCallLogs } from '../lib/api';
import type { CallStats, ActiveCall, CallLog } from '../types';

/* ── Mock chart data (replaced by real data when backend is connected) ── */
const mockChartData = [
  { day: 'Mon', calls: 32 },
  { day: 'Tue', calls: 45 },
  { day: 'Wed', calls: 28 },
  { day: 'Thu', calls: 56 },
  { day: 'Fri', calls: 42 },
  { day: 'Sat', calls: 38 },
  { day: 'Sun', calls: 48 },
];

const BUSINESS_ID = import.meta.env.VITE_BUSINESS_ID || 'mock-business-001';

export default function Dashboard() {
  const [stats, setStats] = useState<CallStats | null>(null);
  const [activeCalls, setActiveCalls] = useState<ActiveCall[]>([]);
  const [recentCalls, setRecentCalls] = useState<CallLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsData, activeData, callsData] = await Promise.allSettled([
          fetchDashboardStats(BUSINESS_ID),
          fetchActiveCalls(),
          fetchCallLogs(BUSINESS_ID, { limit: 5 }),
        ]);

        if (statsData.status === 'fulfilled') setStats(statsData.value);
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
      <div className="bg-gradient-to-r from-primary-50 to-white rounded-xl border border-primary-100 p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="relative flex h-3 w-3">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500" />
          </span>
          <div>
            <div className="text-sm font-semibold text-gray-900">AI Agent is Active</div>
            <div className="text-xs text-gray-500">
              Your virtual receptionist is currently handling inbound queries and scheduling appointments.
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 bg-white text-xs font-medium text-gray-700 hover:bg-gray-50 transition-colors">
            <Mic className="w-3.5 h-3.5" />
            Configure Voice
          </button>
          <button className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary-600 text-xs font-medium text-white hover:bg-primary-700 transition-colors">
            <Settings className="w-3.5 h-3.5" />
            Test Agent
          </button>
        </div>
      </div>

      {/* ── Stats Cards Row ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total Calls Today"
          value={stats?.total_calls ?? 48}
          icon={Phone}
          change={12}
          iconColor="text-blue-600"
          iconBg="bg-blue-50"
          loading={loading}
        />
        <StatsCard
          title="Appointments Booked"
          value={stats?.appointments_booked ?? 12}
          icon={CalendarCheck}
          change={8}
          iconColor="text-green-600"
          iconBg="bg-green-50"
          loading={loading}
        />
        <StatsCard
          title="Conversion Rate"
          value={stats ? `${Math.round(stats.conversion_rate)}%` : '25%'}
          icon={TrendingUp}
          change={-2}
          iconColor="text-purple-600"
          iconBg="bg-purple-50"
          loading={loading}
        />
        <StatsCard
          title="Missed Calls"
          value={stats?.missed_calls ?? 4}
          icon={PhoneMissed}
          change={-18}
          iconColor="text-red-600"
          iconBg="bg-red-50"
          loading={loading}
        />
      </div>

      {/* ── Charts + Live Activity ── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* ── Calls This Week Chart ── */}
        <div className="lg:col-span-3 bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-semibold text-gray-900">Calls this week</div>
              <div className="text-xs text-gray-400">Mon 20 May - Sun 26 May</div>
            </div>
            <select className="text-xs border border-gray-200 rounded-lg px-2 py-1 text-gray-600 bg-white">
              <option>Last 7 Days</option>
              <option>Last 30 Days</option>
            </select>
          </div>
          <div className="h-[220px]">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={mockChartData}>
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
          </div>
        </div>

        {/* ── Live Activity Feed ── */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-100 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm font-semibold text-gray-900">Live Activity</div>
            <button className="text-xs text-primary-600 hover:text-primary-700 font-medium">
              View All
            </button>
          </div>

          <div className="space-y-3">
            {(recentCalls.length > 0 ? recentCalls : defaultActivity).map((item, i) => (
              <ActivityItem key={i} item={item} />
            ))}
          </div>
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

/* ── Default activity data when API is not connected ── */
const defaultActivity: ActivityItemData[] = [
  { phone: '+919876543210', duration: '1m 30s', status: 'appointment_booked' },
  { phone: '+919123456789', duration: '0m 45s', status: 'info_provided' },
  { phone: '+918887766554', duration: '—', status: 'missed' },
  { phone: '+919990011122', duration: '2m 15s', status: 'appointment_booked' },
  { phone: '+917000000001', duration: '1m 05s', status: 'info_provided' },
];
