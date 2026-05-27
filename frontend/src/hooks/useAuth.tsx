import React, { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/client'

interface User { id: number; username: string; full_name: string; email: string }
interface Tenant { id: string; name: string; slug: string; role: string }
interface AuthCtx {
  user: User | null
  tenants: Tenant[]
  activeTenant: Tenant | null
  setActiveTenant: (t: Tenant) => void
  login: (username: string, password: string) => Promise<void>
  register: (username: string, password: string, email: string, fullName: string, companyName: string) => Promise<void>
  logout: () => void
  loading: boolean
}

const AuthContext = createContext<AuthCtx>(null!)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [tenants, setTenants] = useState<Tenant[]>([])
  const [activeTenant, setActiveTenant] = useState<Tenant | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) { setLoading(false); return }
    api.get('/auth/me/').then(res => {
      setUser(res.data.user)
      setTenants(res.data.tenants)
      if (res.data.tenants.length > 0) {
        const stored = localStorage.getItem('activeTenant')
        const found = stored ? res.data.tenants.find((t: Tenant) => t.id === stored) : null
        setActiveTenant(found || res.data.tenants[0])
      }
    }).catch(() => localStorage.removeItem('token')).finally(() => setLoading(false))
  }, [])

  const login = async (username: string, password: string) => {
    const res = await api.post('/auth/login/', { username, password })
    localStorage.setItem('token', res.data.token)
    setUser(res.data.user)
    setTenants(res.data.tenants)
    if (res.data.tenants.length > 0) {
      setActiveTenant(res.data.tenants[0])
      localStorage.setItem('activeTenant', res.data.tenants[0].id)
    }
  }

  const register = async (username: string, password: string, email: string, fullName: string, companyName: string) => {
    const res = await api.post('/auth/register/', {
      username,
      password,
      email,
      full_name: fullName,
      company_name: companyName
    })
    localStorage.setItem('token', res.data.token)
    setUser(res.data.user)
    setTenants(res.data.tenants)
    if (res.data.tenants.length > 0) {
      setActiveTenant(res.data.tenants[0])
      localStorage.setItem('activeTenant', res.data.tenants[0].id)
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('activeTenant')
    setUser(null); setTenants([]); setActiveTenant(null)
  }

  const handleSetTenant = (t: Tenant) => {
    setActiveTenant(t)
    localStorage.setItem('activeTenant', t.id)
  }

  return (
    <AuthContext.Provider value={{ user, tenants, activeTenant, setActiveTenant: handleSetTenant, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
