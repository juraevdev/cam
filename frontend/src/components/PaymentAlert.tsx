import { AlertTriangle, X } from 'lucide-react'

import type { GateLog } from '../types/gate'

interface PaymentAlertProps {
  log: GateLog
  onDismiss: () => void
  onOpenBarrier: (log: GateLog) => void
  opening?: boolean
}

export function PaymentAlert({
  log,
  onDismiss,
  onOpenBarrier,
  opening = false,
}: PaymentAlertProps) {
  return (
    <div
      role="alert"
      className="mb-4 flex flex-col gap-3 rounded-2xl border border-amber-300 bg-warn-soft px-4 py-4 text-warn shadow-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 rounded-lg bg-amber-200/70 p-2">
          <AlertTriangle className="h-5 w-5" />
        </div>
        <div>
          <p className="text-sm font-bold uppercase tracking-wide">Payment required</p>
          <p className="mt-1 text-sm text-amber-950/80">
            Vehicle{' '}
            <span className="font-mono font-semibold text-ink">{log.licensePlate}</span> (
            {log.action}) needs payment before the barrier can open.
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2 self-end sm:self-center">
        <button
          type="button"
          onClick={() => onOpenBarrier(log)}
          disabled={opening}
          className="rounded-lg bg-warn px-3 py-2 text-sm font-semibold text-white transition hover:bg-amber-800 disabled:opacity-60"
        >
          {opening ? 'Opening…' : 'Open Barrier Manually'}
        </button>
        <button
          type="button"
          aria-label="Dismiss alert"
          onClick={onDismiss}
          className="rounded-lg p-2 text-amber-900/70 hover:bg-amber-200/60"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}
