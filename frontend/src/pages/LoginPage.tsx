import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { Leaf, AlertCircle } from 'lucide-react'

export default function LoginPage() {
  const [isRegister, setIsRegister] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [email, setEmail] = useState('')
  const [fullName, setFullName] = useState('')
  const [companyName, setCompanyName] = useState('')
  
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  
  const { login, register } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (isRegister) {
        await register(username, password, email, fullName, companyName)
      } else {
        await login(username, password)
      }
      navigate('/dashboard')
    } catch (err: any) {
      const serverError = err.response?.data?.error
      setError(serverError || (isRegister ? 'Registration failed.' : 'Invalid username or password.'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0B0B0C] flex items-center justify-center p-4 antialiased text-zinc-200 font-sans">
      <div className="w-full max-w-[380px]">
        {/* Brand Logo Header */}
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="w-6 h-6 rounded bg-emerald-500 flex items-center justify-center">
            <Leaf size={13} className="text-[#0B0B0C] stroke-[2.5]" />
          </div>
          <span className="font-semibold text-zinc-100 text-[15px] tracking-tight">Breathe ESG</span>
        </div>

        {/* Auth form container */}
        <div className="bg-[#121214] border border-zinc-800/80 rounded-xl p-8 shadow-xl">
          <div className="mb-6">
            <h1 className="text-zinc-100 font-semibold text-lg leading-snug">
              {isRegister ? 'Create Workspace' : 'Sign in'}
            </h1>
            <p className="text-zinc-500 text-xs mt-1">
              {isRegister ? 'Register your user account and tenant environment.' : 'Access the emissions analyst dashboard.'}
            </p>
          </div>

          {error && (
            <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg px-3 py-2.5 mb-4 text-xs">
              <AlertCircle size={13} /> {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {isRegister && (
              <>
                <div>
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5">Full Name</label>
                  <input
                    value={fullName}
                    onChange={e => setFullName(e.target.value)}
                    placeholder="Jane Doe"
                    className="w-full bg-zinc-900 border border-zinc-800/80 rounded px-3 py-2 text-zinc-200 text-xs focus:outline-none focus:border-zinc-600 transition-colors placeholder:text-zinc-650"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5">Email Address</label>
                  <input
                    type="email"
                    value={email}
                    onChange={e => setEmail(e.target.value)}
                    placeholder="jane@company.com"
                    className="w-full bg-zinc-900 border border-zinc-800/80 rounded px-3 py-2 text-zinc-200 text-xs focus:outline-none focus:border-zinc-600 transition-colors placeholder:text-zinc-650"
                    required
                  />
                </div>
                <div>
                  <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5">Company Name</label>
                  <input
                    value={companyName}
                    onChange={e => setCompanyName(e.target.value)}
                    placeholder="Acme Corp"
                    className="w-full bg-zinc-900 border border-zinc-800/80 rounded px-3 py-2 text-zinc-200 text-xs focus:outline-none focus:border-zinc-600 transition-colors placeholder:text-zinc-650"
                    required
                  />
                </div>
              </>
            )}

            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5">Username</label>
              <input
                value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="username"
                className="w-full bg-zinc-900 border border-zinc-800/80 rounded px-3 py-2 text-zinc-200 text-xs focus:outline-none focus:border-zinc-600 transition-colors placeholder:text-zinc-650"
                required
              />
            </div>
            <div>
              <label className="block text-[11px] font-mono uppercase tracking-wider text-zinc-500 mb-1.5">Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full bg-zinc-900 border border-zinc-800/80 rounded px-3 py-2 text-zinc-200 text-xs focus:outline-none focus:border-zinc-600 transition-colors placeholder:text-zinc-650"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full mt-3 bg-zinc-100 hover:bg-zinc-200 text-zinc-950 font-semibold py-2 rounded text-xs transition-colors disabled:opacity-60"
            >
              {loading ? (isRegister ? 'Creating Account…' : 'Signing in…') : (isRegister ? 'Create Account' : 'Sign in')}
            </button>
          </form>

          {/* Clean Switch tab action in footer of card */}
          <div className="mt-5 border-t border-zinc-800/60 pt-4 text-center">
            <button
              type="button"
              onClick={() => {
                setIsRegister(!isRegister)
                setError('')
              }}
              className="text-xs text-zinc-450 hover:text-zinc-200 transition-colors focus:outline-none"
            >
              {isRegister ? 'Already have an account? Sign in' : 'Don\'t have an account? Sign up'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
