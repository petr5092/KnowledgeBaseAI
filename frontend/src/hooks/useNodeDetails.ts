import { useState, useEffect } from 'react'
import { getNodeDetails, type NodeDetails, HttpError } from '../api'

/**
 * Хук для получения детальной информации об узле
 */
export function useNodeDetails(uid: string | null) {
  const [data, setData] = useState<NodeDetails | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!uid) {
      setData(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)

    getNodeDetails(uid)
      .then((res) => {
        if (!cancelled) setData(res)
      })
      .catch((err) => {
        if (cancelled) return
        if (err instanceof HttpError) {
          setError(err.message)
        } else {
          setError(err instanceof Error ? err.message : 'Unknown error')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [uid])

  return { data, loading, error }
}

