import { useEffect, useState } from 'react'

export function useAsyncResource(factory, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true })

  useEffect(() => {
    let active = true
    setState({ data: null, error: null, loading: true })
    Promise.resolve()
      .then(factory)
      .then(data => {
        if (active) setState({ data, error: null, loading: false })
      })
      .catch(error => {
        if (active) setState({ data: null, error: String(error), loading: false })
      })
    return () => {
      active = false
    }
  }, deps)

  return state
}
