import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'

export default function EChart({ option, height = 320, style }) {
  const ref = useRef(null)
  const inst = useRef(null)

  useEffect(() => {
    inst.current = echarts.init(ref.current, null, { renderer: 'canvas' })
    const ro = new ResizeObserver(() => inst.current && inst.current.resize())
    ro.observe(ref.current)
    return () => {
      ro.disconnect()
      if (inst.current) inst.current.dispose()
      inst.current = null
    }
  }, [])

  useEffect(() => {
    if (inst.current && option) inst.current.setOption(option, true)
  }, [option])

  return <div ref={ref} style={{ width: '100%', height, ...style }} />
}
