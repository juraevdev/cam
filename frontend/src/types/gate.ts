export type GateAction = 'entry' | 'exit'
export type GateStatus = 'allowed' | 'require_payment' | 'exited'

export interface GateLog {
  id: number
  licensePlate: string
  action: GateAction
  status: GateStatus
  isPaid: boolean
  timeIn: string
  timeOut: string | null
  time: string
}

/** Raw payload from Django EntryLogSerializer / WebSocket */
export interface GateLogApi {
  id: number
  license_plate: string
  time_in: string
  time_out: string | null
  is_paid: boolean
  action: GateAction
  status: GateStatus
  created_at?: string
}

export interface GateSocketMessage {
  type: 'connection' | 'gate_log_update'
  event?: 'created' | 'updated'
  message?: string
  data?: GateLogApi
}

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export const GATE_WS_URL =
  import.meta.env.VITE_GATE_WS_URL ?? 'ws://localhost:8000/ws/logs/'

/** MJPEG stream published by cv_module/scanner.py (default :8081) */
export const CAMERA_STREAM_URL =
  import.meta.env.VITE_CAMERA_STREAM_URL ?? 'http://127.0.0.1:8081/stream'

export function mapApiLog(data: GateLogApi): GateLog {
  return {
    id: data.id,
    licensePlate: data.license_plate,
    action: data.action,
    status: data.status,
    isPaid: data.is_paid,
    timeIn: data.time_in,
    timeOut: data.time_out,
    time: data.time_out ?? data.time_in,
  }
}
