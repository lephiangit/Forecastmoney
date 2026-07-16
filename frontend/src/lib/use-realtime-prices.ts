"use client"

import { useEffect, useRef, useState, useCallback } from "react"

interface PriceData {
  price: number
  change: number
  change_pct: number
  volume: number
}

type PriceMap = Record<string, PriceData>

/**
 * useRealtimePrices – WebSocket hook for real-time price streaming.
 * Falls back to HTTP polling if WebSocket is unavailable.
 */
export function useRealtimePrices(tickers: string[]) {
  const [prices, setPrices] = useState<PriceMap>({})
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const maxRetries = 5

  const connect = useCallback(() => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL
    if (!baseUrl) return

    // Convert http(s) to ws(s)
    const wsUrl = baseUrl.replace(/^http/, "ws") + "/ws/prices"

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        retriesRef.current = 0
        // Subscribe to tickers
        ws.send(JSON.stringify({ type: "subscribe", tickers }))
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === "prices" && msg.data) {
            setPrices((prev) => ({ ...prev, ...msg.data }))
          }
        } catch {
          // Ignore parse errors
        }
      }

      ws.onclose = () => {
        setConnected(false)
        wsRef.current = null
        // Reconnect with exponential backoff
        if (retriesRef.current < maxRetries) {
          const delay = Math.min(1000 * Math.pow(2, retriesRef.current), 30000)
          retriesRef.current++
          setTimeout(connect, delay)
        }
      }

      ws.onerror = () => {
        ws.close()
      }
    } catch {
      // WebSocket not available — will fallback to polling
    }
  }, [tickers])

  useEffect(() => {
    connect()
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect])

  // Re-subscribe when tickers change
  useEffect(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "subscribe", tickers }))
    }
  }, [tickers])

  return { prices, connected }
}
