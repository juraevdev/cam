import { API_BASE_URL, mapApiLog, type GateLog, type GateLogApi } from '../types/gate'

async function parseError(response: Response): Promise<string> {
  try {
    const body = await response.json()
    return body.detail ?? body.status ?? `Request failed (${response.status})`
  } catch {
    return `Request failed (${response.status})`
  }
}

export async function fetchRecentLogs(): Promise<GateLog[]> {
  const response = await fetch(`${API_BASE_URL}/api/logs/`)
  if (!response.ok) {
    throw new Error(await parseError(response))
  }
  const data = (await response.json()) as GateLogApi[]
  return data.map(mapApiLog)
}

export async function openBarrier(params: {
  entryLogId?: number
  licensePlate?: string
}): Promise<GateLog> {
  const body: Record<string, string | number> = {}
  if (params.entryLogId != null) body.entry_log_id = params.entryLogId
  if (params.licensePlate) body.license_plate = params.licensePlate

  const response = await fetch(`${API_BASE_URL}/api/open-barrier/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(await parseError(response))
  }

  const payload = await response.json()
  return mapApiLog(payload.entry_log as GateLogApi)
}
