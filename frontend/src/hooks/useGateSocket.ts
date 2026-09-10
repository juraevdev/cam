import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchRecentLogs } from '../api/gateApi'
import {
  GATE_WS_URL,
  mapApiLog,
  type GateLog,
  type GateSocketMessage,
} from '../types/gate'

export interface UseGateSocketResult {
  logs: GateLog[]
  connected: boolean
  paymentAlert: GateLog | null
  dismissAlert: () => void
  upsertLog: (log: GateLog) => void
  error: string | null
}

export function useGateSocket(url: string = GATE_WS_URL): UseGateSocketResult {
  const [logs, setLogs] = useState<GateLog[]>([])
  const [connected, setConnected] = useState(false)
  const [paymentAlert, setPaymentAlert] = useState<GateLog | null>(null)
  const [error, setError] = useState<string | null>(null)
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<number | null>(null)

  const upsertLog = useCallback((log: GateLog) => {
    setLogs((prev) => {
      const without = prev.filter((item) => item.id !== log.id)
      return [log, ...without].slice(0, 100)
    })
    if (log.status === 'require_payment') {
      setPaymentAlert(log)
    } else if (log.isPaid) {
      setPaymentAlert((current) => (current?.id === log.id ? null : current))
    }
  }, [])

  const dismissAlert = useCallback(() => {
    setPaymentAlert(null)
  }, [])

  useEffect(() => {
    let cancelled = false

    fetchRecentLogs()
      .then((initial) => {
        if (!cancelled) setLogs(initial)
      })
      .catch(() => {
        // Soft-fail bootstrap; live socket will still populate the table.
      })

    const connect = () => {
      if (cancelled) return

      const ws = new WebSocket(url)
      socketRef.current = ws

      ws.onopen = () => {
        if (cancelled) return
        setConnected(true)
        setError(null)
      }

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as GateSocketMessage
          if (payload.type !== 'gate_log_update' || !payload.data) return
          upsertLog(mapApiLog(payload.data))
        } catch {
          setError('Failed to parse WebSocket message')
        }
      }

      ws.onerror = () => {
        if (!cancelled) setError('WebSocket connection error')
      }

      ws.onclose = () => {
        if (cancelled) return
        setConnected(false)
        reconnectTimer.current = window.setTimeout(connect, 2500)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (reconnectTimer.current) window.clearTimeout(reconnectTimer.current)
      socketRef.current?.close()
    }
  }, [url, upsertLog])

  return {
    logs,
    connected,
    paymentAlert,
    dismissAlert,
    upsertLog,
    error,
  }
}
