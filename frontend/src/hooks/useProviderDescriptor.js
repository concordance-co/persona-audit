import { getScoreSpaces } from '../api'
import { useEffect, useState } from 'react'

// Descriptor cache keyed by provider: descriptors are static per backend
// process, so one fetch per provider per page load is enough.
const cache = new Map()

export function useProviderDescriptor(provider) {
  const [descriptor, setDescriptor] = useState(() => cache.get(provider) || null)

  useEffect(() => {
    if (cache.has(provider)) {
      setDescriptor(cache.get(provider))
      return undefined
    }
    let active = true
    setDescriptor(null)
    getScoreSpaces(provider)
      .then(payload => {
        const next = payload?.descriptor || {}
        cache.set(provider, next)
        if (active) setDescriptor(next)
      })
      .catch(() => {
        if (active) setDescriptor({})
      })
    return () => {
      active = false
    }
  }, [provider])

  return {
    descriptor: descriptor || {},
    features: descriptor?.features || {},
    copy: descriptor?.copy || {},
    loading: descriptor === null,
  }
}
