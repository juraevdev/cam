import { useState } from 'react'
import { Shield } from 'lucide-react'

import { openBarrier } from '../api/gateApi'
import { useGateSocket } from '../hooks/useGateSocket'
import type { GateLog } from '../types/gate'
import { CameraFeed } from './CameraFeed'
import { GateLogTable } from './GateLogTable'
import { PaymentAlert } from './PaymentAlert'

export function Dashboard() {
  const { logs, connected, paymentAlert, dismissAlert, upsertLog, error } = useGateSocket()
  const [openingAlert, setOpeningAlert] = useState(false)
  const [manualPlate, setManualPlate] = useState('')
  const [manualBusy, setManualBusy] = useState(false)
  const [manualError, setManualError] = useState<string | null>(null)

  const handleOpenFromAlert = async (log: GateLog) => {
    setOpeningAlert(true)
    try {
      const updated = await openBarrier({ entryLogId: log.id })
      upsertLog(updated)
      dismissAlert()
    } catch {
      // Keep alert visible so the operator can retry.
    } finally {
      setOpeningAlert(false)
    }
  }

  const handleManualOpenByPlate = async () => {
    const plate = manualPlate.trim()
    if (!plate) return
    setManualBusy(true)
    setManualError(null)
    try {
      const updated = await openBarrier({ licensePlate: plate })
      upsertLog(updated)
      setManualPlate('')
    } catch (err) {
      setManualError(err instanceof Error ? err.message : 'Failed to open barrier')
    } finally {
      setManualBusy(false)
    }
  }

  return (
    <div className="mx-auto flex min-h-svh w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
            Smart Gate
          </p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight text-ink sm:text-4xl">
            Operator Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted">
            Live detections via WebSocket <span className="font-mono">/ws/logs/</span>
          </p>
        </div>

        <div className="flex items-center gap-2 self-start rounded-full border border-line bg-panel px-3 py-1.5 text-xs font-medium shadow-sm">
          <span className={`h-2 w-2 rounded-full ${connected ? 'bg-ok' : 'bg-danger'}`} />
          {connected ? 'WebSocket connected' : 'Reconnecting…'}
        </div>
      </header>

      {error && (
        <p className="rounded-xl border border-danger/20 bg-danger-soft px-4 py-3 text-sm text-danger">
          {error}
        </p>
      )}

      {paymentAlert && (
        <PaymentAlert
          log={paymentAlert}
          onDismiss={dismissAlert}
          onOpenBarrier={handleOpenFromAlert}
          opening={openingAlert}
        />
      )}

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <CameraFeed />

        <section className="flex flex-col gap-4 rounded-2xl border border-line bg-panel p-4 shadow-sm">
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-accent" />
            <h2 className="text-sm font-semibold text-ink">Manual Controls</h2>
          </div>
          <p className="text-sm text-muted">
            Override the barrier for a plate when cash/QR payment is taken at the booth.
          </p>

          <label className="text-xs font-semibold uppercase tracking-wide text-muted">
            License plate
            <input
              value={manualPlate}
              onChange={(e) => setManualPlate(e.target.value.toUpperCase())}
              placeholder="01A123AA"
              className="mt-1 w-full rounded-lg border border-line bg-white px-3 py-2 font-mono text-sm text-ink outline-none focus:border-accent"
            />
          </label>

          <button
            type="button"
            onClick={handleManualOpenByPlate}
            disabled={manualBusy || !manualPlate.trim()}
            className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:opacity-50"
          >
            {manualBusy ? 'Opening…' : 'Open Barrier Manually'}
          </button>

          {manualError && <p className="text-sm text-danger">{manualError}</p>}

          <ul className="mt-auto space-y-2 border-t border-line pt-4 text-sm text-muted">
            <li>• Paid pass → auto open on scan</li>
            <li>• Unpaid → alert + require payment</li>
            <li>• Manual open marks entry as paid</li>
          </ul>
        </section>
      </div>

      <GateLogTable logs={logs} onLogUpdated={upsertLog} />
    </div>
  )
}
