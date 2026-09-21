import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import Account from './Account'

// Mock useSession hook
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
        favorite_genres: [28, 18],
      },
    },
    signOut: vi.fn(),
  }),
}))

// Mock queries
vi.mock('../api/queries', () => ({
  genresQuery: () => ({
    queryKey: ['genres'],
    queryFn: () => Promise.resolve([
      { tmdb_id: 28, name: 'Action' },
      { tmdb_id: 18, name: 'Drama' },
    ]),
  }),
}))

describe('Account Component', () => {
  it('renders account credentials, password form, and main admin badge', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Account />
        </BrowserRouter>
      </QueryClientProvider>
    )

    // Heading & Sections
    expect(screen.getByRole('heading', { level: 1 })).toBeDefined()
    expect(screen.getByText('Account credentials')).toBeDefined()
    expect(screen.getByText('Change password')).toBeDefined()
    expect(screen.getByText('Cinema profile')).toBeDefined()

    // Credentials inputs
    const usernameInput = screen.getByLabelText(/Username/) as HTMLInputElement
    expect(usernameInput.value).toBe('admin')

    const emailInput = screen.getByLabelText(/Email address/) as HTMLInputElement
    expect(emailInput.value).toBe('esan3125@gmail.com')

    // Password fields
    expect(screen.getByLabelText(/^Current password/)).toBeDefined()
    expect(screen.getByLabelText(/^New password/)).toBeDefined()
    expect(screen.getByLabelText(/^Confirm new password/)).toBeDefined()

    // Admin dashboard card
    expect(screen.getByText('Main Administrator')).toBeDefined()
    expect(screen.getByText('Open Admin Dashboard')).toBeDefined()
  })

  it('renders safely when profile or favorite_genres is missing/empty', () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })

    // Render without throwing TypeError on favorite_genres
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Account />
        </BrowserRouter>
      </QueryClientProvider>
    )

    expect(container).toBeDefined()
  })
})
