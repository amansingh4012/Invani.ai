/**
 * Sidebar — Dark navy sidebar matching Stitch design
 *
 * Shows: logo/brand, 4 nav links, active state highlight,
 * user avatar + plan badge at the bottom.
 */

import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Phone,
  CalendarDays,
  Settings,
  Bot,
} from 'lucide-react';

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
            <div className="text-sm font-semibold leading-tight">AIVoice.in</div>
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

        {/* ── User section ── */}
        <div className="px-4 py-4 border-t border-white/10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-primary-500 flex items-center justify-center text-xs font-bold">
              RK
            </div>
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">Rajesh Kumar</div>
              <div className="text-[11px] text-emerald-400">Premium Plan</div>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
}
