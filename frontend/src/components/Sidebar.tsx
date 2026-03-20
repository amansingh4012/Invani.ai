/**
 * Sidebar — Dark navy sidebar matching Stitch design
 *
 * Shows: logo/brand, 4 nav links, active state highlight,
 * user avatar + plan badge + logout button at the bottom.
 */

import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Phone,
  CalendarDays,
  Settings,
  Bot,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../hooks/useAuth';

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/calls', label: 'Call Logs', icon: Phone },
  { to: '/appointments', label: 'Appointments', icon: CalendarDays },
  { to: '/settings', label: 'Settings', icon: Settings },
];

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({ isOpen, onClose }: SidebarProps) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    onClose();
    await logout();
    navigate('/login', { replace: true });
  }

  // Derive display info from user
  const phone = user?.phone || '';
  const initials = phone ? phone.slice(-4, -2) : 'RK';
  const displayPhone = phone
    ? `${phone.slice(0, 3)} ${phone.slice(3, 8)} ${phone.slice(8)}`
    : 'Rajesh Kumar';

  return (
    <>
      {/* ── Mobile overlay ── */}
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* ── Sidebar ── */}
      <aside
        className={`
          fixed top-0 left-0 z-50 h-screen w-[220px]
          flex flex-col
          bg-[#1a1f37] text-white
          transition-transform duration-300 ease-in-out
          lg:translate-x-0 lg:static lg:z-auto
          ${isOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        {/* ── Brand ── */}
        <div className="flex items-center gap-3 px-5 py-6 border-b border-white/10">
          <div className="flex items-center justify-center w-9 h-9 rounded-lg bg-primary-600">
            <Bot className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="text-sm font-semibold leading-tight">VaaniAI</div>
            <div className="text-[11px] text-white/50">AI Voice Agent</div>
          </div>
        </div>

        {/* ── Navigation ── */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={onClose}
              end={item.to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-primary-600 text-white'
                    : 'text-white/60 hover:bg-white/8 hover:text-white'
                }`
              }
            >
              <item.icon className="w-[18px] h-[18px]" />
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* ── User + Logout ── */}
        <div className="px-4 py-4 border-t border-white/10 space-y-3">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center text-xs font-bold shrink-0">
              {initials.toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{displayPhone}</div>
              <div className="text-[11px] text-emerald-400">Active</div>
            </div>
          </div>

          {/* Logout button */}
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 w-full px-3 py-2 rounded-lg text-xs font-medium text-white/50 hover:bg-white/8 hover:text-red-300 transition-colors group"
          >
            <LogOut className="w-4 h-4 group-hover:text-red-400 transition-colors" />
            Logout
          </button>
        </div>
      </aside>
    </>
  );
}
