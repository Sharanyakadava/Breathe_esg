import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import {
  LayoutDashboard, ClipboardCheck, Upload, History,
  LogOut, Leaf, ChevronDown, X
} from 'lucide-react'
import { useState } from 'react'

const navItems = [
  { to: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/review',    icon: ClipboardCheck,  label: 'Review Queue' },
  { to: '/upload',    icon: Upload,           label: 'Ingest Data' },
  { to: '/batches',   icon: History,          label: 'Batch History' },
]

export default function Layout() {
  const { user, logout, tenants, activeTenant, setActiveTenant } = useAuth()
  const navigate = useNavigate()
  const [tenantOpen,  setTenantOpen]  = useState(false)
  const [profileOpen, setProfileOpen] = useState(false)

  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="flex h-screen bg-[#0B0B0C] font-sans antialiased text-zinc-200 relative">

      {/* ── Sidebar ── */}
      <aside className="w-60 flex flex-col bg-[#121214] border-r border-zinc-800/80">

        {/* Brand */}
        <div className="flex items-center gap-2.5 px-6 py-5 border-b border-zinc-800/60">
          <div className="w-6 h-6 rounded bg-emerald-500 flex items-center justify-center">
            <Leaf size={13} className="text-[#121214] stroke-[2.5]" />
          </div>
          <span className="font-semibold text-zinc-100 text-[15px] tracking-tight">Breathe ESG</span>
        </div>

        {/* Tenant switcher */}
        {tenants.length > 1 && (
          <div className="px-4 py-3 border-b border-zinc-800/60">
            <button
              onClick={() => setTenantOpen(o => !o)}
              className="w-full flex items-center justify-between px-3 py-2 rounded bg-zinc-900 border border-zinc-800/50 hover:bg-zinc-800/50 text-xs text-zinc-300 transition-colors"
            >
              <span className="truncate">{activeTenant?.name}</span>
              <ChevronDown size={12} className="text-zinc-500 shrink-0" />
            </button>
            {tenantOpen && (
              <div className="mt-1 rounded border border-zinc-800 bg-zinc-900 overflow-hidden shadow-xl">
                {tenants.map(t => (
                  <button
                    key={t.id}
                    onClick={() => { setActiveTenant(t); setTenantOpen(false) }}
                    className={`w-full text-left px-3 py-2 text-xs hover:bg-zinc-800/50 transition-colors ${
                      activeTenant?.id === t.id ? 'text-emerald-400 font-medium' : 'text-zinc-400'
                    }`}
                  >
                    {t.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded text-[13px] tracking-wide transition-all ${
                  isActive
                    ? 'bg-zinc-800 text-zinc-100 font-medium'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900/50'
                }`
              }
            >
              <Icon size={14} className="stroke-[2]" />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* User footer */}
        <div className="px-4 py-4 border-t border-zinc-800/60">
          <div className="flex items-center justify-between gap-3 bg-zinc-900/40 p-2.5 rounded-lg border border-zinc-800/50">
            <button
              onClick={() => setProfileOpen(true)}
              className="flex items-center gap-2.5 flex-1 min-w-0 text-left focus:outline-none group"
            >
              <div className="w-7 h-7 rounded-full bg-zinc-800 group-hover:bg-zinc-700 flex items-center justify-center text-xs font-semibold text-zinc-300 transition-colors">
                {user?.full_name?.[0] || user?.username?.[0]}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xs font-semibold text-zinc-200 truncate group-hover:text-zinc-100 transition-colors">
                  {user?.full_name || user?.username}
                </p>
                <p className="text-[10px] font-mono text-zinc-500 truncate mt-0.5 uppercase tracking-wider">
                  {activeTenant?.role}
                </p>
              </div>
            </button>
            <button
              onClick={handleLogout}
              title="Sign Out"
              className="text-zinc-500 hover:text-red-400 p-1 rounded hover:bg-zinc-800/50 transition-colors"
            >
              <LogOut size={13} />
            </button>
          </div>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="flex-1 overflow-auto bg-[#0B0B0C]">
        <Outlet />
      </main>

      {/* ── Profile Modal ── */}
      {profileOpen && (
        <div className="fixed inset-0 bg-[#060608]/90 backdrop-blur-[2px] z-50 flex items-center justify-center p-4">
          <div className="bg-[#121214] border border-zinc-800/80 rounded-xl w-full max-w-sm p-6 relative shadow-2xl">

            <button
              onClick={() => setProfileOpen(false)}
              className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-200 transition-colors"
            >
              <X size={15} />
            </button>

            {/* Avatar + name */}
            <div className="flex items-center gap-4 mb-6 pb-4 border-b border-zinc-800/60">
              <div className="w-12 h-12 rounded-full bg-zinc-800 border border-zinc-700 flex items-center justify-center text-zinc-200 text-[17px] font-semibold">
                {user?.full_name?.[0] || user?.username?.[0]}
              </div>
              <div>
                <h2 className="text-zinc-100 font-semibold text-sm leading-snug">
                  {user?.full_name || user?.username}
                </h2>
                <span className="inline-block text-[9px] font-mono text-zinc-500 uppercase tracking-widest bg-zinc-900 border border-zinc-800 px-2 py-0.5 rounded-full mt-1.5">
                  {activeTenant?.role || 'Member'}
                </span>
              </div>
            </div>

            {/* User details */}
            <div className="space-y-5">
              <div>
                <h3 className="text-zinc-500 text-[10px] font-mono uppercase tracking-widest mb-2.5">
                  User Information
                </h3>
                <div className="divide-y divide-zinc-800/60">
                  <div className="flex justify-between py-2.5 text-xs">
                    <span className="text-zinc-500">Username</span>
                    <span className="text-zinc-200 font-medium">{user?.username}</span>
                  </div>
                  <div className="flex justify-between py-2.5 text-xs">
                    <span className="text-zinc-500">Email Address</span>
                    <span className="text-zinc-200 font-medium truncate max-w-[180px]">{user?.email || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between py-2.5 text-xs">
                    <span className="text-zinc-500">User ID</span>
                    <span className="text-zinc-400 font-mono text-[10px]">#{user?.id}</span>
                  </div>
                </div>
              </div>

              {/* Org details */}
              <div>
                <h3 className="text-zinc-500 text-[10px] font-mono uppercase tracking-widest mb-2.5">
                  Organization Details
                </h3>
                <div className="divide-y divide-zinc-800/60">
                  <div className="flex justify-between py-2.5 text-xs">
                    <span className="text-zinc-500">Active Tenant</span>
                    <span className="text-zinc-200 font-medium">{activeTenant?.name}</span>
                  </div>
                  <div className="flex justify-between py-2.5 text-xs">
                    <span className="text-zinc-500">Workspace Slug</span>
                    <span className="text-zinc-400 font-mono text-[10px]">/{activeTenant?.slug}</span>
                  </div>
                </div>
              </div>
            </div>

            <button
              onClick={() => setProfileOpen(false)}
              className="w-full mt-7 bg-zinc-100 hover:bg-zinc-200 text-zinc-950 font-semibold py-2 rounded text-xs transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  )
}