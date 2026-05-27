import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts'
import { TrendingUp, CheckCircle, AlertTriangle, Clock, Leaf } from 'lucide-react'

const SCOPE_COLORS: Record<string, string> = {
  scope1: '#22c55e',
  scope2_lb: '#3b82f6',
  scope2_mb: '#60a5fa',
  scope3: '#f59e0b',
}
const SCOPE_LABELS: Record<string, string> = {
  scope1: 'Scope 1',
  scope2_lb: 'Scope 2 (LB)',
  scope2_mb: 'Scope 2 (MB)',
  scope3: 'Scope 3',
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: any; color: string }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-400 text-sm">{label}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
        </div>
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${color}`}>
          <Icon size={16} className="text-white" />
        </div>
      </div>
    </div>
  )
}

export default function DashboardPage() {
  const { activeTenant } = useAuth()
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeTenant) return
    setLoading(true)
    api.get(`/emissions/records/summary/?tenant=${activeTenant.id}`)
      .then(r => setSummary(r.data))
      .finally(() => setLoading(false))
  }, [activeTenant])

  if (loading) return (
    <div className="p-8 text-slate-400">Loading dashboard…</div>
  )

  const totalTonnes = summary?.total?.total_kg
    ? (Number(summary.total.total_kg) / 1000).toFixed(1)
    : '—'

  const byScope = (summary?.by_scope || []).map((s: any) => ({
    name: SCOPE_LABELS[s.scope] || s.scope,
    value: Math.round(Number(s.total_kg) / 1000),
    color: SCOPE_COLORS[s.scope] || '#6b7280',
  }))

  const byStatus = summary?.by_status || []
  const pending = byStatus.find((s: any) => s.status === 'pending_review')?.count || 0
  const approved = byStatus.find((s: any) => s.status === 'approved')?.count || 0
  const flagged = byStatus.find((s: any) => s.status === 'flagged')?.count || 0
  const total = summary?.total?.count || 0

  const byCategory = (summary?.by_category || [])
    .sort((a: any, b: any) => Number(b.total_kg) - Number(a.total_kg))
    .slice(0, 8)
    .map((c: any) => ({
      name: c.category.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()),
      value: Math.round(Number(c.total_kg) / 1000),
    }))

  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-slate-400 text-sm mt-1">{activeTenant?.name} — Emissions overview</p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Emissions" value={`${totalTonnes} tCO₂e`} icon={Leaf} color="bg-green-600" />
        <StatCard label="Total Records" value={total} icon={TrendingUp} color="bg-blue-600" />
        <StatCard label="Pending Review" value={pending} icon={Clock} color="bg-amber-600" />
        <StatCard label="Approved" value={approved} icon={CheckCircle} color="bg-emerald-600" />
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* By Scope */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h2 className="text-white font-medium mb-4">Emissions by Scope (tCO₂e)</h2>
          {byScope.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={byScope} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={({ name, value }) => `${value}t`}>
                  {byScope.map((entry: any, i: number) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: any) => [`${v} tCO₂e`, '']} contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                <Legend formatter={(v) => <span className="text-slate-300 text-sm">{v}</span>} />
              </PieChart>
            </ResponsiveContainer>
          ) : <p className="text-slate-500 text-sm py-8 text-center">No data yet. Upload some files to get started.</p>}
        </div>

        {/* By Category */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h2 className="text-white font-medium mb-4">Top Categories (tCO₂e)</h2>
          {byCategory.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={byCategory} layout="vertical" margin={{ left: 0 }}>
                <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="name" width={130} tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip formatter={(v: any) => [`${v} tCO₂e`, '']} contentStyle={{ background: '#1e293b', border: '1px solid #334155', borderRadius: 8 }} />
                <Bar dataKey="value" fill="#22c55e" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : <p className="text-slate-500 text-sm py-8 text-center">No data yet.</p>}
        </div>
      </div>

      {/* Status breakdown */}
      <div className="mt-6 bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h2 className="text-white font-medium mb-4">Review Status</h2>
        <div className="flex flex-wrap gap-3">
          {byStatus.map((s: any) => (
            <div key={s.status} className="flex items-center gap-2 bg-slate-800 rounded-lg px-3 py-2">
              <span className={`w-2 h-2 rounded-full ${
                s.status === 'approved' ? 'bg-green-400' :
                s.status === 'pending_review' ? 'bg-amber-400' :
                s.status === 'flagged' ? 'bg-red-400' :
                s.status === 'locked' ? 'bg-blue-400' : 'bg-slate-400'
              }`} />
              <span className="text-slate-300 text-sm capitalize">{s.status.replace('_', ' ')}</span>
              <span className="text-slate-500 text-sm font-medium">{s.count}</span>
            </div>
          ))}
          {byStatus.length === 0 && <p className="text-slate-500 text-sm">No records yet.</p>}
        </div>
      </div>
    </div>
  )
}
