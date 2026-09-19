export function safeNext(value: string | null): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\') || value.startsWith('/login') || value.startsWith('/register')) return '/for-you'
  return value
}
