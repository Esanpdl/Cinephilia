import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, Navigate } from 'react-router-dom'
import {
  Film,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Star,
  Trash2,
  UserCheck,
  UserMinus,
  UserPlus,
  Users,
  X,
} from 'lucide-react'
import { useSession } from '../auth/SessionProvider'
import { api, errorMessage } from '../api/client'
import type { AdminStats, AdminUser, Page } from '../api/types'
import { Button, Pagination } from '../components/ui'

export default function AdminDashboard() {
  const { user } = useSession()
  const cache = useQueryClient()

  // Must be staff to view this page
  if (!user?.is_staff) {
    return <Navigate to="/" replace />
  }

  const isMainAdmin = Boolean(user.is_main_admin)

  // Filters & Pagination
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState<'all' | 'admin' | 'user'>('all')
  const [page, setPage] = useState(1)
  const [showAddModal, setShowAddModal] = useState(false)

  // Status feedback
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Stats query
  const statsQuery = useQuery({
    queryKey: ['admin-stats'],
    queryFn: () => api<AdminStats>('/api/v1/admin-panel/stats/'),
  })

  // Users list query
  const usersQuery = useQuery({
    queryKey: ['admin-users', search, roleFilter, page],
    queryFn: () => {
      const params = new URLSearchParams()
      if (search.trim()) params.set('search', search.trim())
      if (roleFilter !== 'all') params.set('role', roleFilter)
      if (page > 1) params.set('page', String(page))
      return api<Page<AdminUser>>(`/api/v1/admin-panel/users/?${params.toString()}`)
    },
  })

  // Promote user mutation
  const promoteMutation = useMutation({
    mutationFn: (userId: number) =>
      api<AdminUser>(`/api/v1/admin-panel/users/${userId}/promote/`, { method: 'POST' }),
    onSuccess: target => {
      setActionMessage({ type: 'success', text: `Successfully promoted ${target.username} to Admin.` })
      void cache.invalidateQueries({ queryKey: ['admin-users'] })
      void cache.invalidateQueries({ queryKey: ['admin-stats'] })
    },
    onError: err => {
      setActionMessage({ type: 'error', text: errorMessage(err) })
    },
  })

  // Demote user mutation
  const demoteMutation = useMutation({
    mutationFn: (userId: number) =>
      api<AdminUser>(`/api/v1/admin-panel/users/${userId}/demote/`, { method: 'POST' }),
    onSuccess: target => {
      setActionMessage({ type: 'success', text: `Successfully demoted ${target.username} from Admin.` })
      void cache.invalidateQueries({ queryKey: ['admin-users'] })
      void cache.invalidateQueries({ queryKey: ['admin-stats'] })
    },
    onError: err => {
      setActionMessage({ type: 'error', text: errorMessage(err) })
    },
  })

  // Delete user mutation
  const deleteMutation = useMutation({
    mutationFn: (userId: number) =>
      api<void>(`/api/v1/admin-panel/users/${userId}/delete/`, { method: 'DELETE' }),
    onSuccess: () => {
      setActionMessage({ type: 'success', text: 'User removed successfully.' })
      void cache.invalidateQueries({ queryKey: ['admin-users'] })
      void cache.invalidateQueries({ queryKey: ['admin-stats'] })
    },
    onError: err => {
      setActionMessage({ type: 'error', text: errorMessage(err) })
    },
  })

  // Add new admin mutation
  const [addError, setAddError] = useState<string | null>(null)
  const addAdminMutation = useMutation({
    mutationFn: (data: { username: string; email: string; password: string; display_name?: string }) =>
      api<AdminUser>('/api/v1/admin-panel/users/create-admin/', { method: 'POST', body: data }),
    onSuccess: newAdmin => {
      setActionMessage({ type: 'success', text: `Admin account '${newAdmin.username}' created successfully!` })
      setShowAddModal(false)
      setAddError(null)
      void cache.invalidateQueries({ queryKey: ['admin-users'] })
      void cache.invalidateQueries({ queryKey: ['admin-stats'] })
    },
    onError: err => {
      setAddError(errorMessage(err))
    },
  })

  return (
    <div className="section-wrap admin-page">
      {/* Header */}
      <div className="admin-header-row">
        <div>
          <p className="eyebrow">Administration & Control</p>
          <h1>Admin <em>Dashboard.</em></h1>
          <div className="admin-status-identity">
            <span className="admin-user-pill">
              {isMainAdmin ? (
                <>
                  <ShieldCheck size={16} className="gold-icon" /> Main Administrator (Owner)
                </>
              ) : (
                <>
                  <Shield size={16} className="blue-icon" /> Staff Administrator
                </>
              )}
            </span>
            <span className="admin-user-name">Signed in as <strong>{user.username}</strong></span>
          </div>
        </div>

        <div className="admin-header-actions">
          <Link to="/account" className="button button-outline">
            My Account Settings
          </Link>
          {isMainAdmin && (
            <Button
              className="button-light"
              onClick={() => {
                setAddError(null)
                setShowAddModal(true)
              }}
            >
              <UserPlus size={16} /> Add New Admin
            </Button>
          )}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="admin-metrics-grid">
        <div className="metric-card">
          <div className="metric-icon-wrap">
            <Users size={22} className="gold-icon" />
          </div>
          <div>
            <span className="metric-label">Total Users</span>
            <strong className="metric-value">
              {statsQuery.isPending ? '—' : statsQuery.data?.total_users ?? 0}
            </strong>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-wrap">
            <ShieldCheck size={22} className="gold-icon" />
          </div>
          <div>
            <span className="metric-label">Administrators</span>
            <strong className="metric-value">
              {statsQuery.isPending ? '—' : statsQuery.data?.total_admins ?? 0}
            </strong>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-wrap">
            <Film size={22} className="gold-icon" />
          </div>
          <div>
            <span className="metric-label">Catalog Movies</span>
            <strong className="metric-value">
              {statsQuery.isPending ? '—' : statsQuery.data?.total_movies ?? 0}
            </strong>
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-icon-wrap">
            <Star size={22} className="gold-icon" />
          </div>
          <div>
            <span className="metric-label">Community Ratings</span>
            <strong className="metric-value">
              {statsQuery.isPending ? '—' : statsQuery.data?.total_ratings ?? 0}
            </strong>
          </div>
        </div>
      </div>

      {/* Action Notice */}
      {actionMessage && (
        <div
          className={`admin-feedback-banner ${actionMessage.type === 'success' ? 'success' : 'error'}`}
          role="alert"
        >
          <span>{actionMessage.text}</span>
          <button
            type="button"
            className="dismiss-btn"
            onClick={() => setActionMessage(null)}
            aria-label="Dismiss message"
          >
            <X size={16} />
          </button>
        </div>
      )}

      {/* Add New Admin Modal / Panel */}
      {showAddModal && isMainAdmin && (
        <div className="admin-modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="admin-modal-dialog" onClick={e => e.stopPropagation()}>
            <div className="admin-modal-header">
              <h2>Add New Administrator</h2>
              <button
                type="button"
                className="icon-button"
                onClick={() => setShowAddModal(false)}
                aria-label="Close modal"
              >
                <X size={20} />
              </button>
            </div>
            <p className="admin-modal-desc">
              Create a new administrator account with staff privileges. Only the main administrator can create new admins.
            </p>

            <form
              onSubmit={e => {
                e.preventDefault()
                setAddError(null)
                const form = new FormData(e.currentTarget)
                const username = String(form.get('username') || '').trim()
                const email = String(form.get('email') || '').trim()
                const password = String(form.get('password') || '')
                const displayName = String(form.get('display_name') || '').trim()

                if (!username || !/^[a-zA-Z0-9_-]{3,30}$/.test(username)) {
                  setAddError('Username must be 3–30 characters (letters, numbers, hyphens, underscores).')
                  return
                }
                if (!email) {
                  setAddError('Valid email address is required.')
                  return
                }
                if (/@gmail\./i.test(email) && !email.toLowerCase().endsWith('@gmail.com')) {
                  setAddError('Gmail addresses must end with @gmail.com.')
                  return
                }
                if (password.length < 8) {
                  setAddError('Password must be at least 8 characters long.')
                  return
                }
                if (!/[a-zA-Z]/.test(password) || !/[0-9!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?~`]/.test(password)) {
                  setAddError('Password must contain at least one letter and at least one number or special character.')
                  return
                }

                addAdminMutation.mutate({
                  username,
                  email,
                  password,
                  display_name: displayName,
                })
              }}
            >
              <label className="field">
                Username
                <input name="username" required maxLength={30} placeholder="e.g. curator_eva" />
              </label>

              <label className="field">
                Email address
                <input type="email" name="email" required placeholder="admin@example.com" />
              </label>

              <label className="field">
                Temporary password
                <input type="password" name="password" required minLength={8} placeholder="At least 8 characters" />
              </label>

              <label className="field">
                Display name (optional)
                <input name="display_name" maxLength={100} placeholder="e.g. Eva Miller" />
              </label>

              {addError && <p className="inline-error" role="alert">{addError}</p>}

              <div className="admin-modal-actions">
                <Button
                  type="button"
                  className="button-outline"
                  onClick={() => setShowAddModal(false)}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  className="button-light"
                  disabled={addAdminMutation.isPending}
                >
                  {addAdminMutation.isPending ? 'Creating…' : 'Create Admin Account'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* User Management Section */}
      <section className="admin-management-section">
        <div className="admin-section-header">
          <div>
            <h2>User & Admin Management</h2>
            <p>View all accounts, manage staff administrator privileges, and oversee membership.</p>
          </div>

          <div className="admin-filter-bar">
            {/* Search Input */}
            <div className="admin-search-wrap">
              <Search size={16} className="search-icon" />
              <input
                type="text"
                placeholder="Search username, email, name…"
                value={search}
                onChange={e => {
                  setSearch(e.target.value)
                  setPage(1)
                }}
              />
            </div>

            {/* Role Filter Tabs */}
            <div className="admin-role-tabs">
              <button
                type="button"
                className={`tab-btn ${roleFilter === 'all' ? 'active' : ''}`}
                onClick={() => {
                  setRoleFilter('all')
                  setPage(1)
                }}
              >
                All Users
              </button>
              <button
                type="button"
                className={`tab-btn ${roleFilter === 'admin' ? 'active' : ''}`}
                onClick={() => {
                  setRoleFilter('admin')
                  setPage(1)
                }}
              >
                Admins Only
              </button>
              <button
                type="button"
                className={`tab-btn ${roleFilter === 'user' ? 'active' : ''}`}
                onClick={() => {
                  setRoleFilter('user')
                  setPage(1)
                }}
              >
                Members
              </button>
            </div>
          </div>
        </div>

        {/* User Table */}
        {usersQuery.isPending ? (
          <div className="route-loading" role="status">Loading accounts…</div>
        ) : usersQuery.isError ? (
          <p className="inline-error" role="alert">{errorMessage(usersQuery.error)}</p>
        ) : usersQuery.data.results.length === 0 ? (
          <div className="admin-empty-state">
            <p>No accounts match your query.</p>
          </div>
        ) : (
          <div className="admin-table-container">
            <table className="admin-users-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Joined</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {usersQuery.data.results.map(account => {
                  const isAccountMainAdmin = Boolean(account.is_main_admin)
                  const isAccountStaff = Boolean(account.is_staff)

                  return (
                    <tr key={account.id} className={isAccountMainAdmin ? 'row-main-admin' : ''}>
                      <td>
                        <div className="user-cell">
                          <span className="avatar">
                            {(account.display_name || account.username).slice(0, 1).toUpperCase()}
                          </span>
                          <div>
                            <strong>{account.username}</strong>
                            {account.display_name && (
                              <span className="user-display-sub">{account.display_name}</span>
                            )}
                          </div>
                        </div>
                      </td>

                      <td>
                        <span className="email-text">{account.email || '—'}</span>
                      </td>

                      <td>
                        {isAccountMainAdmin ? (
                          <span className="badge badge-gold">
                            <ShieldCheck size={13} /> Main Admin
                          </span>
                        ) : isAccountStaff ? (
                          <span className="badge badge-blue">
                            <Shield size={13} /> Staff Admin
                          </span>
                        ) : (
                          <span className="badge badge-gray">Member</span>
                        )}
                      </td>

                      <td>
                        <span className="date-text">
                          {new Date(account.date_joined).toLocaleDateString(undefined, {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                          })}
                        </span>
                      </td>

                      <td>
                        <div className="action-button-group">
                          {isAccountMainAdmin ? (
                            <span className="protected-tag" title="The main administrator cannot be demoted or deleted.">
                              <ShieldAlert size={14} /> Protected
                            </span>
                          ) : isMainAdmin ? (
                            <>
                              {isAccountStaff ? (
                                <button
                                  type="button"
                                  className="admin-action-btn demote-btn"
                                  title="Demote from Admin"
                                  disabled={demoteMutation.isPending}
                                  onClick={() => {
                                    if (window.confirm(`Are you sure you want to remove admin privileges from ${account.username}?`)) {
                                      demoteMutation.mutate(account.id)
                                    }
                                  }}
                                >
                                  <UserMinus size={15} /> Demote
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  className="admin-action-btn promote-btn"
                                  title="Promote to Admin"
                                  disabled={promoteMutation.isPending}
                                  onClick={() => {
                                    if (window.confirm(`Promote ${account.username} to Staff Administrator?`)) {
                                      promoteMutation.mutate(account.id)
                                    }
                                  }}
                                >
                                  <UserCheck size={15} /> Promote
                                </button>
                              )}

                              <button
                                type="button"
                                className="admin-action-btn delete-btn"
                                title="Remove User"
                                aria-label={`Permanently delete user ${account.username}`}
                                disabled={deleteMutation.isPending}
                                onClick={() => {
                                  if (window.confirm(`Are you sure you want to permanently delete user ${account.username}?`)) {
                                    deleteMutation.mutate(account.id)
                                  }
                                }}
                              >
                                <Trash2 size={15} />
                              </button>
                            </>
                          ) : (
                            <span className="readonly-tag">Managed by Main Admin</span>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            <Pagination
              page={page}
              count={usersQuery.data.count}
              onPage={newPage => {
                setPage(newPage)
                window.scrollTo({ top: 300, behavior: 'smooth' })
              }}
            />
          </div>
        )}
      </section>
    </div>
  )
}
