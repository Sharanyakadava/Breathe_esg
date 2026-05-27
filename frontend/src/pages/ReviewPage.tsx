import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'
import {
  CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronUp,
  Filter, Search, RefreshCw
} from 'lucide-react'

const STATUS_STYLES: Record<string, string> = {
  pending_review: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
  approved: 'bg-green-500/10 text-green-400 border border-green-500/20',
  rejected: 'bg-red-500/10 text-red-400 border border-red-500/20',
  locked: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
  flagged: 'bg-rose-500/10 text-rose-400 border border-rose-500/20',
}

const SCOPE_LABELS: Record<string, string> = {
  scope1: 'S1', scope2_lb: 'S2-LB', scope2_mb: 'S2-MB', scope3: 'S3',
}
const SCOPE_COLORS: Record<string, string> = {
  scope1: 'text-green-400', scope2_lb: 'text-blue-400', scope2_mb: 'text-blue-300', scope3: 'text-amber-400',
}

function RecordRow({ record, onReview, selected, onSelect }: any) {
  const [expanded, setExpanded] = useState(false)
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleAction = async (action: 'approved' | 'rejected' | 'flagged') => {
    setSubmitting(true)
    try {
      await onReview(record.id, { status: action, review_notes: note, reason: note })
    } finally {
      setSubmitting(false)
    }
  }

  const co2e = Number(record.quantity_kg_co2e)
  const tonnes = co2e >= 1000 ? `${(co2e / 1000).toFixed(2)} t` : `${co2e.toFixed(1)} kg`

  return (
    <>
      <tr className={`border-b border-slate-800 hover:bg-slate-800/30 transition-colors ${selected ? 'bg-slate-800/50' : ''}`}>
        <td className="px-4 py-3">
          <input type="checkbox" checked={selected} onChange={() => onSelect(record.id)}
            className="rounded border-slate-600 bg-slate-700 text-green-500"
          />
        </td>
        <td className="px-4 py-3">
          <span className={`text-xs font-mono font-bold ${SCOPE_COLORS[record.scope] || 'text-slate-400'}`}>
            {SCOPE_LABELS[record.scope] || record.scope}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-slate-300 max-w-xs truncate">{record.description}</td>
        <td className="px-4 py-3 text-sm font-medium text-white tabular-nums">{tonnes}CO₂e</td>
        <td className="px-4 py-3 text-xs text-slate-400">{record.period_start}</td>
        <td className="px-4 py-3 text-xs text-slate-400">{record.source_unit}</td>
        <td className="px-4 py-3">
          {record.is_suspicious && (
            <span className="flex items-center gap-1 text-xs text-orange-400">
              <AlertTriangle size={12} />
              {record.suspicion_reasons?.[0]?.replace(/_/g, ' ')}
            </span>
          )}
        </td>
        <td className="px-4 py-3">
          <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_STYLES[record.status] || ''}`}>
            {record.status.replace('_', ' ')}
          </span>
        </td>
        <td className="px-4 py-3">
          <div className="flex items-center gap-2">
            {record.status === 'pending_review' && (
              <>
                <button onClick={() => handleAction('approved')} disabled={submitting}
                  className="p-1 text-green-400 hover:text-green-300 hover:bg-green-500/10 rounded transition-colors"
                  title="Approve">
                  <CheckCircle size={16} />
                </button>
                <button onClick={() => handleAction('rejected')} disabled={submitting}
                  className="p-1 text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded transition-colors"
                  title="Reject">
                  <XCircle size={16} />
                </button>
                <button onClick={() => handleAction('flagged')} disabled={submitting}
                  className="p-1 text-orange-400 hover:text-orange-300 hover:bg-orange-500/10 rounded transition-colors"
                  title="Flag">
                  <AlertTriangle size={16} />
                </button>
              </>
            )}
            <button onClick={() => setExpanded(e => !e)}
              className="p-1 text-slate-400 hover:text-slate-200 rounded transition-colors">
              {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
          </div>
        </td>
      </tr>
      {expanded && (
        <tr className="bg-slate-900/50 border-b border-slate-800">
          <td colSpan={9} className="px-6 py-4">
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-slate-500 text-xs mb-1">Raw source</p>
                <p className="text-slate-300">{record.source_quantity} {record.source_unit_original || record.source_unit}</p>
                <p className="text-slate-500 text-xs mt-1">{record.source_date_raw}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Emission factor</p>
                <p className="text-slate-300">{record.emission_factor_value} {record.emission_factor_unit}</p>
                <p className="text-slate-500 text-xs mt-1">{record.emission_factor_source}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs mb-1">Source row ID</p>
                <p className="text-slate-300 font-mono text-xs">{record.source_row_id}</p>
              </div>
              {record.source_extra && Object.keys(record.source_extra).length > 0 && (
                <div className="col-span-2 lg:col-span-3">
                  <p className="text-slate-500 text-xs mb-1">Extra source fields</p>
                  <pre className="text-xs text-slate-400 bg-slate-800 rounded-lg p-2 overflow-x-auto">
                    {JSON.stringify(record.source_extra, null, 2)}
                  </pre>
                </div>
              )}
              {record.suspicion_reasons?.length > 0 && (
                <div>
                  <p className="text-slate-500 text-xs mb-1">Suspicion flags</p>
                  <ul className="space-y-0.5">
                    {record.suspicion_reasons.map((r: string) => (
                      <li key={r} className="text-orange-400 text-xs">• {r.replace(/_/g, ' ')}</li>
                    ))}
                  </ul>
                </div>
              )}
              {record.edits?.length > 0 && (
                <div className="col-span-2 lg:col-span-3">
                  <p className="text-slate-500 text-xs mb-1">Edit history</p>
                  {record.edits.map((e: any) => (
                    <div key={e.id} className="text-xs text-slate-400 mb-1">
                      <span className="text-slate-300">{e.edited_by_name}</span> changed <span className="text-slate-300">{e.field_name}</span>: {e.old_value} → {e.new_value}
                      {e.reason && <span className="text-slate-500"> ({e.reason})</span>}
                    </div>
                  ))}
                </div>
              )}
            </div>
            {record.status === 'pending_review' && (
              <div className="mt-3 flex items-center gap-3">
                <input
                  value={note} onChange={e => setNote(e.target.value)}
                  placeholder="Add a review note (optional)…"
                  className="flex-1 bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-green-500 placeholder-slate-600"
                />
              </div>
            )}
          </td>
        </tr>
      )}
    </>
  )
}

export default function ReviewPage() {
  const { activeTenant } = useAuth()
  const [records, setRecords] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ status: 'pending_review', scope: '', suspicious: '' })
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [page, setPage] = useState(1)
  const [count, setCount] = useState(0)
  const PAGE_SIZE = 50

  const fetchRecords = useCallback(() => {
    if (!activeTenant) return
    setLoading(true)
    const params: any = { tenant: activeTenant.id, page }
    if (filters.status) params.status = filters.status
    if (filters.scope) params.scope = filters.scope
    if (filters.suspicious) params.is_suspicious = filters.suspicious
    if (search) params.search = search
    api.get('/emissions/records/', { params })
      .then(r => { setRecords(r.data.results || r.data); setCount(r.data.count || 0) })
      .finally(() => setLoading(false))
  }, [activeTenant, filters, search, page])

  useEffect(() => { fetchRecords() }, [fetchRecords])

  const handleReview = async (id: string, data: any) => {
    await api.post(`/emissions/records/${id}/review/`, data)
    fetchRecords()
  }

  const handleBulkApprove = async () => {
    if (!activeTenant || selected.size === 0) return
    await api.post('/emissions/records/bulk_approve/', {
      ids: Array.from(selected),
      tenant: activeTenant.id,
    })
    setSelected(new Set())
    fetchRecords()
  }

  const toggleSelect = (id: string) => {
    setSelected(s => {
      const n = new Set(s)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  const totalPages = Math.ceil(count / PAGE_SIZE)

  return (
    <div className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Review Queue</h1>
          <p className="text-slate-400 text-sm mt-0.5">{count} records • {selected.size} selected</p>
        </div>
        <div className="flex items-center gap-3">
          {selected.size > 0 && (
            <button onClick={handleBulkApprove}
              className="flex items-center gap-2 bg-green-500 hover:bg-green-400 text-white text-sm px-4 py-2 rounded-lg transition-colors">
              <CheckCircle size={15} />
              Approve {selected.size} selected
            </button>
          )}
          <button onClick={fetchRecords} className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors">
            <RefreshCw size={15} />
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="flex items-center gap-2 bg-slate-800 rounded-lg px-3 py-2">
          <Search size={14} className="text-slate-400" />
          <input
            value={search} onChange={e => { setSearch(e.target.value); setPage(1) }}
            placeholder="Search description, row ID…"
            className="bg-transparent text-sm text-white focus:outline-none w-48 placeholder-slate-500"
          />
        </div>
        <select
          value={filters.status}
          onChange={e => { setFilters(f => ({ ...f, status: e.target.value })); setPage(1) }}
          className="bg-slate-800 border border-slate-700 text-sm text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-green-500"
        >
          <option value="">All statuses</option>
          <option value="pending_review">Pending review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
          <option value="flagged">Flagged</option>
          <option value="locked">Locked</option>
        </select>
        <select
          value={filters.scope}
          onChange={e => { setFilters(f => ({ ...f, scope: e.target.value })); setPage(1) }}
          className="bg-slate-800 border border-slate-700 text-sm text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-green-500"
        >
          <option value="">All scopes</option>
          <option value="scope1">Scope 1</option>
          <option value="scope2_lb">Scope 2 (Location)</option>
          <option value="scope2_mb">Scope 2 (Market)</option>
          <option value="scope3">Scope 3</option>
        </select>
        <select
          value={filters.suspicious}
          onChange={e => { setFilters(f => ({ ...f, suspicious: e.target.value })); setPage(1) }}
          className="bg-slate-800 border border-slate-700 text-sm text-slate-300 rounded-lg px-3 py-2 focus:outline-none focus:border-green-500"
        >
          <option value="">All records</option>
          <option value="true">Suspicious only</option>
          <option value="false">Clean only</option>
        </select>
      </div>

      {/* Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-slate-800 bg-slate-800/50">
              <th className="px-4 py-3 w-8">
                <input type="checkbox"
                  onChange={e => setSelected(e.target.checked ? new Set(records.map(r => r.id)) : new Set())}
                  className="rounded border-slate-600 bg-slate-700"
                />
              </th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">Scope</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">Description</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">CO₂e</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">Period</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">Unit</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">Flags</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">Status</th>
              <th className="px-4 py-3 text-xs font-medium text-slate-400 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={9} className="px-4 py-12 text-center text-slate-400">Loading…</td></tr>
            ) : records.length === 0 ? (
              <tr><td colSpan={9} className="px-4 py-12 text-center text-slate-400">
                No records found. Upload data via the Ingest Data page.
              </td></tr>
            ) : (
              records.map(r => (
                <RecordRow
                  key={r.id} record={r}
                  onReview={handleReview}
                  selected={selected.has(r.id)}
                  onSelect={toggleSelect}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-4">
          <p className="text-slate-400 text-sm">Page {page} of {totalPages}</p>
          <div className="flex gap-2">
            <button disabled={page === 1} onClick={() => setPage(p => p - 1)}
              className="px-3 py-1.5 text-sm bg-slate-800 text-slate-300 rounded-lg disabled:opacity-40 hover:bg-slate-700 transition-colors">
              Previous
            </button>
            <button disabled={page === totalPages} onClick={() => setPage(p => p + 1)}
              className="px-3 py-1.5 text-sm bg-slate-800 text-slate-300 rounded-lg disabled:opacity-40 hover:bg-slate-700 transition-colors">
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
