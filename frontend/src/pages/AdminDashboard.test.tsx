import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import AdminDashboard from './AdminDashboard'

// Mock useSession hook with main admin
vi.mock('../auth/SessionProvider', () => ({
  useSession: () => ({
    user: {
      id: 1,
      username: 'admin',
      email: 'esan3125@gmail.com',
      is_staff: true,
      is_superuser: true,
      is_main_admin: true,
      profile: {
        display_name: 'Lead Admin',
        bio: 'Cinema curator',
        is_film_student: true,
        favorite_genres: [],
      },
    },
    signOut: vi.fn(),
  }),
}))

// Mock api client
vi.mock('../api/client', () => ({
  api: (url: string) => {
    if (url.includes('/stats/')) {
      return Promise.resolve({
        total_users: 42,
        total_admins: 3,
        total_movies: 1500,
        total_ratings: 8900,
      })
    }
    if (url.includes('/users/')) {
      return Promise.resolve({
        count: 2,
        next: null,
        previous: null,
        results: [
          {
            id: 1,
            username: 'admin',
            email: 'esan3125@gmail.com',
            is_staff: true,
            is_superuser: true,
            is_main_admin: true,
            display_name: 'Lead Admin',
            is_film_student: false,
            date_joined: '2026-01-01T00:00:00Z',
            last_login: null,
          },
          {
            id: 2,
            username: 'editor_sarah',
            email: 'sarah@example.com',
            is_staff: true,
            is_superuser: false,
            is_main_admin: false,
            display_name: 'Sarah Editor',
            is_film_student: true,
            date_joined: '2026-02-01T00:00:00Z',
            last_login: null,
          },
        ],
      })
    }
    return Promise.resolve({})
  },
  errorMessage: (err: unknown) => String(err),
}))

describe('AdminDashboard Component', () => {
  it('renders dashboard heading, stats, user list, and add admin button', async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AdminDashboard />
        </BrowserRouter>
      </QueryClientProvider>
    )

    // Heading & identity
    expect(screen.getByRole('heading', { level: 1 })).toBeDefined()
    expect(screen.getByText('Administration & Control')).toBeDefined()

    // Main admin pill
    expect(screen.getByText(/Main Administrator \(Owner\)/)).toBeDefined()

    // Add New Admin button (visible to main admin)
    expect(screen.getByText(/Add New Admin/)).toBeDefined()

    // Stats
    expect(await screen.findByText('Total Users')).toBeDefined()
    expect(await screen.findByText('42')).toBeDefined()
    expect(await screen.findByText('Administrators')).toBeDefined()
    expect(await screen.findByText('3')).toBeDefined()

    // Table rows
    expect(await screen.findByText('editor_sarah')).toBeDefined()

    // Main admin row has Protected tag
    expect(screen.getByText('Protected')).toBeDefined()

    // Other staff admin row has Demote button
    expect(screen.getByText('Demote')).toBeDefined()
  })
})
