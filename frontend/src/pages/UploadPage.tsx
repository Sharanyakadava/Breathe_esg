import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import api from '../api/client'
import { Upload, CheckCircle, AlertTriangle, FileText, Info } from 'lucide-react'

const SOURCE_TYPES = [
  {
    id: 'sap_flat_file',
    label: 'SAP Flat File',
    description: 'Tab or semicolon-delimited export from SAP (IDoc/flat file). Handles fuel consumption and procurement data. Expects columns: BWART, WERKS, BUDAT, MENGE, MEINS, MAKTX, MATKL.',
    scope: 'Scope 1 + Scope 3',
    accept: '.txt,.csv,.tsv,.dat',
    extras: ['facility_lookup'],
  },
  {
    id: 'utility_csv',
    label: 'Utility Portal CSV',
    description: 'CSV export from a utility portal (e.g. National Grid, PG&E, EDF). Auto-detects column headers. Handles non-calendar billing periods and estimated reads.',
    scope: 'Scope 2',
    accept: '.csv',
    extras: ['grid_region', 'market_based'],
  },
  {
    id: 'travel_csv',
    label: 'Corporate Travel CSV',
    description: 'CSV export from Concur, Navan, or similar. Handles flights (computes distance from IATA codes), hotels (room-nights), and ground transport.',
    scope: 'Scope 3',
    accept: '.csv',
    extras: [],
  },
]

const GRID_REGIONS = [
  { value: 'UK', label: 'UK (DEFRA 2023 — 0.205 kgCO₂e/kWh)' },
  { value: 'US-ERCT', label: 'US ERCOT/Texas (EPA eGRID — 0.423)' },
  { value: 'US-WECC', label: 'US Western (EPA eGRID — 0.271)' },
  { value: 'US-RFC', label: 'US Mid-Atlantic (EPA eGRID — 0.382)' },
  { value: 'US-SERC', label: 'US Southeast (EPA eGRID — 0.400)' },
  { value: 'US', label: 'US Average (0.386)' },
  { value: 'EU', label: 'EU Average (IEA 2022 — 0.276)' },
  { value: 'IN', label: 'India (IEA 2022 — 0.708)' },
  { value: 'DEFAULT', label: 'Conservative default (0.400)' },
]

interface UploadResult {
  status: 'success' | 'partial' | 'error'
  batch_id?: string
  rows_ingested?: number
  rows_failed?: number
  rows_suspicious?: number
  error?: string
}

export default function UploadPage() {
  const { activeTenant } = useAuth()
  const [sourceType, setSourceType] = useState('sap_flat_file')
  const [file, setFile] = useState<File | null>(null)
  const [gridRegion, setGridRegion] = useState('DEFAULT')
  const [marketBased, setMarketBased] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [result, setResult] = useState<UploadResult | null>(null)
  const [dragOver, setDragOver] = useState(false)

  const selected = SOURCE_TYPES.find(s => s.id === sourceType)!

  const handleFile = (f: File) => {
    setFile(f)
    setResult(null)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragOver(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file || !activeTenant) return
    setUploading(true)
    setResult(null)

    const formData = new FormData()
    formData.append('file', file)
    formData.append('source_type', sourceType)
    formData.append('tenant', activeTenant.id)
    if (sourceType === 'utility_csv') {
      formData.append('grid_region', gridRegion)
      formData.append('market_based', String(marketBased))
    }

    try {
      const res = await api.post('/ingestion/upload/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      setResult({
        status: res.data.rows_failed > 0 ? 'partial' : 'success',
        ...res.data,
      })
      setFile(null)
    } catch (err: any) {
      setResult({
        status: 'error',
        error: err.response?.data?.error || 'Upload failed. Check file format.',
      })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-white">Ingest Data</h1>
        <p className="text-slate-400 text-sm mt-1">Upload emissions source files for processing and review.</p>
      </div>

      {/* Source type selector */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {SOURCE_TYPES.map(s => (
          <button
            key={s.id}
            onClick={() => { setSourceType(s.id); setFile(null); setResult(null) }}
            className={`text-left p-4 rounded-xl border transition-all ${
              sourceType === s.id
                ? 'border-green-500 bg-green-500/5'
                : 'border-slate-700 bg-slate-800/50 hover:border-slate-600'
            }`}
          >
            <p className={`font-medium text-sm ${sourceType === s.id ? 'text-green-400' : 'text-white'}`}>
              {s.label}
            </p>
            <p className="text-xs text-slate-500 mt-1">{s.scope}</p>
          </button>
        ))}
      </div>

      {/* Source description */}
      <div className="flex items-start gap-3 bg-slate-800/50 border border-slate-700 rounded-xl p-4 mb-6">
        <Info size={15} className="text-slate-400 mt-0.5 shrink-0" />
        <p className="text-sm text-slate-400">{selected.description}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Extra options for utility */}
        {sourceType === 'utility_csv' && (
          <div className="space-y-4 p-4 bg-slate-800/50 border border-slate-700 rounded-xl">
            <h3 className="text-sm font-medium text-white">Electricity options</h3>
            <div>
              <label className="block text-xs text-slate-400 mb-1.5">Grid region / emission factor</label>
              <select
                value={gridRegion}
                onChange={e => setGridRegion(e.target.value)}
                className="w-full bg-slate-800 border border-slate-700 text-sm text-slate-300 rounded-lg px-3 py-2.5 focus:outline-none focus:border-green-500"
              >
                {GRID_REGIONS.map(r => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={marketBased}
                onChange={e => setMarketBased(e.target.checked)}
                className="rounded border-slate-600 bg-slate-700 text-green-500 focus:ring-0"
              />
              <div>
                <p className="text-sm text-slate-300">Use market-based accounting (Scope 2 MB)</p>
                <p className="text-xs text-slate-500">Applies renewable percentage from file if present; falls back to location-based.</p>
              </div>
            </label>
          </div>
        )}

        {/* Drop zone */}
        <div
          onDragOver={e => { e.preventDefault(); setDragOver(true) }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input')?.click()}
          className={`relative border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-all ${
            dragOver
              ? 'border-green-500 bg-green-500/5'
              : file
              ? 'border-green-500/50 bg-green-500/5'
              : 'border-slate-700 hover:border-slate-500 bg-slate-800/30'
          }`}
        >
          <input
            id="file-input"
            type="file"
            accept={selected.accept}
            className="hidden"
            onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
          />
          {file ? (
            <div className="flex items-center justify-center gap-3">
              <FileText size={20} className="text-green-400" />
              <div className="text-left">
                <p className="text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-slate-400">{(file.size / 1024).toFixed(1)} KB</p>
              </div>
            </div>
          ) : (
            <>
              <Upload size={24} className="text-slate-500 mx-auto mb-3" />
              <p className="text-sm text-slate-400">
                Drop file here or <span className="text-green-400">browse</span>
              </p>
              <p className="text-xs text-slate-600 mt-1">Accepts {selected.accept}</p>
            </>
          )}
        </div>

        {/* Sample data notice */}
        <p className="text-xs text-slate-500">
          Sample files available in <code className="text-slate-400">backend/sample_data/</code> for testing.
        </p>

        <button
          type="submit"
          disabled={!file || uploading}
          className="w-full bg-green-500 hover:bg-green-400 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium py-3 rounded-xl text-sm transition-colors"
        >
          {uploading ? 'Processing…' : 'Upload and process'}
        </button>
      </form>

      {/* Result */}
      {result && (
        <div className={`mt-6 rounded-xl border p-5 ${
          result.status === 'error'
            ? 'bg-red-500/5 border-red-500/20'
            : result.status === 'partial'
            ? 'bg-amber-500/5 border-amber-500/20'
            : 'bg-green-500/5 border-green-500/20'
        }`}>
          <div className="flex items-center gap-2 mb-3">
            {result.status === 'error' ? (
              <AlertTriangle size={16} className="text-red-400" />
            ) : result.status === 'partial' ? (
              <AlertTriangle size={16} className="text-amber-400" />
            ) : (
              <CheckCircle size={16} className="text-green-400" />
            )}
            <span className={`font-medium text-sm ${
              result.status === 'error' ? 'text-red-400' :
              result.status === 'partial' ? 'text-amber-400' : 'text-green-400'
            }`}>
              {result.status === 'error' ? 'Upload failed' :
               result.status === 'partial' ? 'Partial success' : 'Upload complete'}
            </span>
          </div>

          {result.status !== 'error' ? (
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <p className="text-slate-500 text-xs">Rows ingested</p>
                <p className="text-white font-medium mt-0.5">{result.rows_ingested}</p>
              </div>
              <div>
                <p className="text-slate-500 text-xs">Rows failed</p>
                <p className={`font-medium mt-0.5 ${result.rows_failed ? 'text-red-400' : 'text-white'}`}>
                  {result.rows_failed}
                </p>
              </div>
              <div>
                <p className="text-slate-500 text-xs">Suspicious</p>
                <p className={`font-medium mt-0.5 ${result.rows_suspicious ? 'text-amber-400' : 'text-white'}`}>
                  {result.rows_suspicious}
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-red-300">{result.error}</p>
          )}

          {result.batch_id && (
            <p className="text-xs text-slate-500 mt-3">
              Batch ID: <code className="text-slate-400">{result.batch_id}</code>
              {' — '}Records are now in the <a href="/review" className="text-green-400 hover:underline">Review Queue</a>.
            </p>
          )}
        </div>
      )}
    </div>
  )
}
