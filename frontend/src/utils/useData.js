import { useCallback, useEffect, useState } from 'react'

export function useData(fetcher, ...args) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetcher(...args)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [fetcher, ...args])

  useEffect(() => {
    load()
  }, [load])

  return { data, loading, error, refetch: load }
}
