export interface PlaybackSource { source_url: string; title: string; start: number; end: number }

export function playbackAt(sources: PlaybackSource[], timestamp: number) {
  const time = Math.max(0, timestamp)
  const source = sources.find(part => time >= part.start && time < part.end)
  if (!source) return null
  let embed = ''
  let watchUrl = source.source_url
  try {
    const url = new URL(source.source_url)
    const key = url.hostname === 'youtu.be' ? url.pathname.slice(1) : url.searchParams.get('v')
    if (['youtube.com', 'www.youtube.com', 'youtu.be'].includes(url.hostname) && key && /^[\w-]{11}$/.test(key)) {
      embed = `https://www.youtube-nocookie.com/embed/${key}?start=${Math.floor(time - source.start)}`
      watchUrl = `https://www.youtube.com/watch?v=${key}&t=${Math.floor(time - source.start)}s`
    }
  } catch { /* A source link may still be pending. */ }
  return { ...source, embed, watchUrl, timestamp: time - source.start }
}
