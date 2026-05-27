import { useEffect, useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'
import { CheckCircle, AlertTriangle, XCircle, Clock, ChevronDown, ChevronUp } from 'lucide-react'

const STATUS_ICON: Record<string, any> = {
  completed: { icon: CheckCircle, color: 'text-green-400' },
  partial: { icon: AlertTriangle, color: 'text-amber-400' },
  failed: { icon: XCircle, color: 'text-red-400' },
  processing: { icon: Clock, color: 'text-blue-400' },
  pending: { icon: Clock, color: 'text-slate-400' },
}

const SOURCE_LABELS: Record<string, string> = {
  sap_flat_file: 'SAP Flat File',
  utility_csv: 'Utility CSV',
  travel_csv: 'Travel CSV',
}

export default function BatchesPage() {
  const { activeTenant } = useAuth()
  const [batches, setBatches] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)

  useEffect(() => {
    if (!activeTenant) return
    setLoading(true)
    api.get(`/emissions/batches/?tenant=${activeTenant.id}`)
      .then(r => setBatches(r.data.results || r.data))
      .finally(() => setLoading(false))
  }, [activeTenant])

  return (
    <div className="p-8 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Batch History</h1>
        <p className="text-slate-400 text-sm mt-1">All ingestion runs for {activeTenant?.name}</p>
      </div>

      <div className="space-y-3">
        {loading && <p className="text-slate-400">Loading…</p>}
        {!loading && batches.length === 0 && (
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-10 text-center">
            <p className="text-slate-400">No batches yet. Upload data via the Ingest Data page.</p>
          </div>
        )}
        {batches.map(batch => {
          const { icon: Icon, color } = STATUS_ICON[batch.status] || STATUS_ICON.pending
          const isExpanded = expanded === batch.id
          return (
            <div key={batch.id} className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
              <div
                className="flex items-center gap-4 px-5 py-4 cursor-pointer hover:bg-slate-800/30 transition-colors"
                onClick={() => setExpanded(isExpanded ? null : batch.id)}
              >
                <Icon size={16} className={color} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-white">
                      {SOURCE_LABELS[batch.source_type] || batch.source_type}
                    </span>
                    <span className="text-xs text-slate-500 truncate">{batch.source_file_name}</span>
                  </div>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {new Date(batch.uploaded_at).toLocaleString()} · by {batch.uploaded_by_name || 'unknown'}
                  </p>
                </div>
                <div className="flex items-center gap-6 text-sm text-right">
                  <div>
                    <p className="text-slate-500 text-xs">Ingested</p>
                    <p className="text-green-400 font-medium">{batch.row_count_ok}</p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-xs">Failed</p>
                    <p className={`font-medium ${batch.row_count_failed > 0 ? 'text-red-400' : 'text-slate-400'}`}>
                      {batch.row_count_failed}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-500 text-xs">Suspicious</p>
                    <p className={`font-medium ${batch.row_count_suspicious > 0 ? 'text-amber-400' : 'text-slate-400'}`}>
                      {batch.row_count_suspicious}
                    </p>
                  </div>
                  {isExpanded ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
                </div>
              </div>

              {isExpanded && (
                <div className="border-t border-slate-800 px-5 py-4 space-y-3">
                  <div className="flex gap-6 text-sm">
                    <div>
                      <p className="text-slate-500 text-xs">Batch ID</p>
                      <p className="text-slate-300 font-mono text-xs mt-0.5">{batch.id}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs">Status</p>
                      <p className={`mt-0.5 text-xs font-medium ${color}`}>{batch.status}</p>
                    </div>
                    <div>
                      <p className="text-slate-500 text-xs">Total rows</p>
                      <p className="text-slate-300 mt-0.5 text-xs">{batch.row_count_total}</p>
                    </div>
                  </div>

                  {batch.processing_notes && (
                    <div>
                      <p className="text-slate-500 text-xs mb-1">Processing notes</p>
                      <p className="text-sm text-slate-400">{batch.processing_notes}</p>
                    </div>
                  )}

                  {batch.error_log?.length > 0 && (
                    <div>
                      <p className="text-slate-500 text-xs mb-2">Error log ({batch.error_log.length} errors, capped at 100)</p>
                      <div className="max-h-48 overflow-y-auto space-y-1">
                        {batch.error_log.map((e: any, i: number) => (
                          <div key={i} className="bg-slate-800 rounded-lg px-3 py-2 text-xs text-slate-400">
                            <span className="text-red-400">Row {e.row}: </span>{e.error}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
