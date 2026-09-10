import { useState } from 'react'

import { openBarrier } from '../api/gateApi'
import type { GateLog, GateStatus } from '../types/gate'

interface GateLogTableProps {
  logs: GateLog[]
  onLogUpdated: (log: GateLog) => void
}

function statusLabel(status: GateStatus): string {
  switch (status) {
    case 'allowed':
      return 'Allowed'
    case 'require_payment':
      return 'Payment Required'
    case 'exited':
      return 'Exited'
  }
}

function statusClass(status: GateStatus): string {
  switch (status) {
    case 'allowed':
      return 'bg-ok-soft text-ok'
    case 'require_payment':
      return 'bg-warn-soft text-warn'
    case 'exited':
      return 'bg-slate-100 text-slate-600'
  }
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export function GateLogTable({ logs, onLogUpdated }: GateLogTableProps) {
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleOpen = async (log: GateLog) => {
    setBusyId(log.id)
    setError(null)
    try {
      const updated = await openBarrier({ entryLogId: log.id })
      onLogUpdated(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to open barrier')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <section className="overflow-hidden rounded-2xl border border-line bg-panel shadow-sm">
      <header className="flex items-center justify-between border-b border-line px-4 py-3">
        <h2 className="text-sm font-semibold text-ink">Live Camera Detections</h2>
        <span className="text-xs text-muted">{logs.length} events</span>
      </header>

      {error && (
        <p className="border-b border-danger/20 bg-danger-soft px-4 py-2 text-sm text-danger">
          {error}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-muted">
            <tr>
              <th className="px-4 py-3 font-semibold">License Plate</th>
              <th className="px-4 py-3 font-semibold">Action</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Paid</th>
              <th className="px-4 py-3 font-semibold">Time</th>
              <th className="px-4 py-3 font-semibold">Manual Control</th>
            </tr>
          </thead>
          <tbody>
            {logs.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-muted">
                  Waiting for CV detections on <span className="font-mono">/api/scan/</span>…
                </td>
              </tr>
            ) : (
              logs.map((log) => (
                <tr key={`${log.id}-${log.time}`} className="border-t border-line">
                  <td className="px-4 py-3 font-mono text-base font-semibold tracking-wide">
                    {log.licensePlate}
                  </td>
                  <td className="px-4 py-3 capitalize text-ink">{log.action}</td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex rounded-md px-2 py-1 text-xs font-semibold ${statusClass(log.status)}`}
                    >
                      {statusLabel(log.status)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted">{log.isPaid ? 'Yes' : 'No'}</td>
                  <td className="px-4 py-3 text-muted">{formatTime(log.time)}</td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => handleOpen(log)}
                      disabled={busyId === log.id || log.isPaid}
                      className="rounded-lg border border-accent/30 bg-accent-soft px-3 py-1.5 text-xs font-semibold text-accent transition hover:bg-teal-200/70 disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      {busyId === log.id
                        ? 'Opening…'
                        : log.isPaid
                          ? 'Barrier OK'
                          : 'Open Barrier Manually'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  )
}
