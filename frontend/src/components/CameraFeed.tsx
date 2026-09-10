import { useEffect, useMemo, useState } from 'react'
import { Camera, Radio, RefreshCw } from 'lucide-react'

import { CAMERA_STREAM_URL } from '../types/gate'

interface CameraFeedProps {
  label?: string
  streamUrl?: string
}

export function CameraFeed({
  label = 'Entry Camera · Lane A',
  streamUrl = CAMERA_STREAM_URL,
}: CameraFeedProps) {
  const [live, setLive] = useState(false)
  const [failed, setFailed] = useState(false)
  const [clock, setClock] = useState(() => new Date().toLocaleTimeString())
  const [reloadKey, setReloadKey] = useState(0)

  const src = useMemo(
    () => `${streamUrl}${streamUrl.includes('?') ? '&' : '?'}t=${reloadKey}`,
    [streamUrl, reloadKey],
  )

  useEffect(() => {
    const id = window.setInterval(() => {
      setClock(new Date().toLocaleTimeString())
    }, 1000)
    return () => window.clearInterval(id)
  }, [])

  const retry = () => {
    setFailed(false)
    setLive(false)
    setReloadKey((k) => k + 1)
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Camera className="h-4 w-4 text-accent" />
          Live Camera Feed
        </div>
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={retry}
            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted hover:bg-slate-100"
            title="Reconnect stream"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Retry
          </button>
          <div
            className={`flex items-center gap-2 text-xs font-medium ${live ? 'text-ok' : 'text-muted'}`}
          >
            <span className="relative flex h-2 w-2">
              {live && (
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
              )}
              <span
                className={`relative inline-flex h-2 w-2 rounded-full ${live ? 'bg-ok' : 'bg-slate-400'}`}
              />
            </span>
            {live ? 'LIVE' : 'OFFLINE'}
          </div>
        </div>
      </header>

      <div className="relative aspect-video bg-slate-900">
        {!failed && (
          <img
            key={reloadKey}
            src={src}
            alt="Live camera stream"
            className="absolute inset-0 h-full w-full object-cover"
            onLoad={() => {
              setLive(true)
              setFailed(false)
            }}
            onError={() => {
              setLive(false)
              setFailed(true)
            }}
          />
        )}

        {failed && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 px-6 text-center text-slate-300">
            <Radio className="h-10 w-10 text-slate-500" />
            <p className="text-sm font-medium">Camera stream offline</p>
            <p className="max-w-sm text-xs text-slate-400">
              Start the CV scanner to publish MJPEG:
              <br />
              <span className="font-mono text-teal-200/90">
                python scanner.py --type auto --api http://127.0.0.1:8000
              </span>
            </p>
            <p className="font-mono text-[11px] text-slate-500">{streamUrl}</p>
            <button
              type="button"
              onClick={retry}
              className="mt-2 rounded-lg bg-accent px-3 py-1.5 text-xs font-semibold text-white"
            >
              Retry connection
            </button>
          </div>
        )}

        <div className="pointer-events-none absolute left-4 top-4 rounded bg-black/55 px-2 py-1 font-mono text-xs text-teal-100">
          CAM-01 · {label}
        </div>
        <div className="pointer-events-none absolute right-4 top-4 rounded bg-black/55 px-2 py-1 font-mono text-xs text-slate-200">
          {clock}
        </div>
      </div>
    </section>
  )
}
