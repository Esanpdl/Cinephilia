const API_ORIGIN = (import.meta.env.VITE_API_ORIGIN || '').replace(/\/$/, '')
let csrfToken: string | undefined
let csrfRequest: Promise<string> | undefined

export class ApiError extends Error {
  status: number
  fields: Record<string, unknown>
  constructor(status: number, fields: Record<string, unknown>) {
    const messages = Object.entries(fields).flatMap(([field, value]) => {
      const message = Array.isArray(value) ? value.join(' ') : typeof value === 'string' ? value : ''
      return message ? [field === 'detail' || field === 'non_field_errors' ? message : field.replaceAll('_', ' ') + ': ' + message] : []
    })
    super(messages.join(' ') || 'The request could not be completed.')
    this.status = status
    this.fields = fields
  }
}

export function resetCsrf() { csrfToken = undefined; csrfRequest = undefined }

async function readResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const contentType = response.headers.get('content-type') || ''
  if (!contentType.includes('json')) {
    throw new ApiError(response.status || 502, { detail: 'The film service is unavailable. Please try again.' })
  }
  return response.json()
}

async function csrf(): Promise<string> {
  if (csrfToken) return csrfToken
  if (!csrfRequest) csrfRequest = (async () => {
    const response = await fetch(API_ORIGIN + '/api/v1/users/csrf/', { credentials: 'include', cache: 'no-store' })
    const data = await readResponse(response) as { csrf_token?: string }
    if (!response.ok || !data.csrf_token) throw new ApiError(response.status, { detail: 'Could not establish a secure session. Please try again.' })
    csrfToken = data.csrf_token
    return csrfToken
  })().finally(() => { csrfRequest = undefined })
  return csrfRequest
}

export async function api<T>(path: string, options: { method?: string; body?: unknown; signal?: AbortSignal } = {}, retried = false): Promise<T> {
  if (!path.startsWith('/api/')) throw new Error('Expected a Cinephilia API path.')
  const method = options.method || 'GET'
  const unsafe = !['GET', 'HEAD', 'OPTIONS'].includes(method)
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (unsafe) headers['X-CSRFToken'] = await csrf()
  const response = await fetch(API_ORIGIN + path, {
    method, headers, credentials: 'include', cache: 'no-store', signal: options.signal,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
  const data = await readResponse(response)
  if (!response.ok) {
    const fields = data && typeof data === 'object' ? data as Record<string, unknown> : {}
    if (unsafe && response.status === 403 && !retried && String(fields.detail).startsWith('CSRF Failed:')) {
      resetCsrf()
      return api<T>(path, options, true)
    }
    if (response.status === 403 && String(fields.detail).includes('Authentication credentials were not provided')) {
      window.dispatchEvent(new Event('cinephilia:session-expired'))
    }
    throw new ApiError(response.status, fields)
  }
  if (data && typeof data === 'object' && 'csrf_token' in data) csrfToken = String(data.csrf_token)
  return data as T
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'We could not connect to Cinephilia. Check your connection and try again.'
}

export function queryString(params: Record<string, string | number | undefined>) {
  return new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== '').map(([key, value]) => [key, String(value)])).toString()
}
