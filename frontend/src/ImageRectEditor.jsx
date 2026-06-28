import { useCallback, useEffect, useRef, useState } from 'react'

const RECT_COLOR = '#ff0000' // matches render.py's COLOR_RECT_BORDER
const MIN_DRAG_PIXELS = 3 // ignores accidental clicks that aren't real drags

function resolveImagePath(scriptPath, src) {
  const dir = scriptPath.slice(0, scriptPath.lastIndexOf('/'))
  return `${dir}/${src}`
}

function ImageRectEditor({ scriptPath, src, rect, onChange }) {
  const canvasRef = useRef(null)
  const imageRef = useRef(null)
  const rectRef = useRef(rect)
  const [error, setError] = useState(null)

  useEffect(() => {
    rectRef.current = rect
  }, [rect])

  // Reads rect via a ref, not the prop directly, so this stays referentially stable across
  // renders - per react.dev's "avoid function dependencies" guidance, listing an unstable
  // function in an Effect's deps re-runs that Effect whenever the function's identity changes.
  // Without this, the image-fetch Effect below would re-fetch the image on every rect change.
  const drawFrame = useCallback((liveRect) => {
    const canvas = canvasRef.current
    const img = imageRef.current
    if (!canvas || !img) return
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0)
    const r = liveRect || rectRef.current
    if (r) {
      ctx.strokeStyle = RECT_COLOR
      ctx.lineWidth = 2
      ctx.strokeRect(r.x, r.y, r.w, r.h)
    }
  }, [])

  useEffect(() => {
    setError(null)
    let url = null
    let cancelled = false

    fetch(`/api/image?path=${encodeURIComponent(resolveImagePath(scriptPath, src))}`)
      .then(async (res) => {
        if (!res.ok) {
          const data = await res.json().catch(() => ({}))
          throw new Error(data.detail || 'Failed to load image')
        }
        return res.blob()
      })
      .then((blob) => {
        if (cancelled) return
        url = URL.createObjectURL(blob)
        const img = new Image()
        img.onload = () => {
          if (cancelled) return
          imageRef.current = img
          const canvas = canvasRef.current
          canvas.width = img.naturalWidth
          canvas.height = img.naturalHeight
          drawFrame()
        }
        img.onerror = () => setError('Failed to decode image')
        img.src = url
      })
      .catch((err) => setError(err.message))

    return () => {
      cancelled = true
      if (url) URL.revokeObjectURL(url)
    }
  }, [scriptPath, src, drawFrame])

  useEffect(() => {
    drawFrame()
  }, [rect, drawFrame])

  function toCanvasPoint(e) {
    const canvas = canvasRef.current
    const bounds = canvas.getBoundingClientRect()
    const scaleX = canvas.width / bounds.width
    const scaleY = canvas.height / bounds.height
    return {
      x: (e.clientX - bounds.left) * scaleX,
      y: (e.clientY - bounds.top) * scaleY,
    }
  }

  function rectFromDrag(start, end) {
    const canvas = canvasRef.current
    const x = Math.max(0, Math.min(start.x, end.x))
    const y = Math.max(0, Math.min(start.y, end.y))
    const w = Math.min(Math.abs(end.x - start.x), canvas.width - x)
    const h = Math.min(Math.abs(end.y - start.y), canvas.height - y)
    return { x: Math.round(x), y: Math.round(y), w: Math.round(w), h: Math.round(h) }
  }

  function handleMouseDown(e) {
    const start = toCanvasPoint(e)

    function onMove(ev) {
      drawFrame(rectFromDrag(start, toCanvasPoint(ev)))
    }
    function onUp(ev) {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
      const end = toCanvasPoint(ev)
      if (Math.abs(end.x - start.x) < MIN_DRAG_PIXELS || Math.abs(end.y - start.y) < MIN_DRAG_PIXELS) {
        drawFrame() // too small to count as a real drag - snap back to the committed rect
        return
      }
      onChange(rectFromDrag(start, end))
    }

    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp)
  }

  return (
    <div className="image-rect-editor">
      <div className="image-rect-actions">
        <span>Drag on the image to set the annotation rect</span>
        <button type="button" onClick={() => onChange(null)} disabled={!rect}>
          Clear rect
        </button>
      </div>
      {error && <div className="image-rect-error">{error}</div>}
      <canvas ref={canvasRef} className="image-rect-canvas" onMouseDown={handleMouseDown} />
    </div>
  )
}

export default ImageRectEditor
