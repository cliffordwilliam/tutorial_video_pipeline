import { useEffect, useState } from 'react'

function CodePreview({ slide }) {
  const [preview, setPreview] = useState({ url: null, error: null })

  // Revokes the previous blob URL whenever it's replaced, and on unmount -
  // covers both "preview the same slide again" and "switch away from this
  // slide" (this component is remounted via key={slide._key} in SlideEditor).
  useEffect(() => {
    return () => {
      if (preview.url) URL.revokeObjectURL(preview.url)
    }
  }, [preview.url])

  async function handlePreview() {
    const { _key, ...slideData } = slide
    try {
      const res = await fetch('/api/preview/frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(slideData),
      })
      if (!res.ok) {
        const data = await res.json()
        setPreview({ url: null, error: data.detail || 'Preview failed' })
        return
      }
      const blob = await res.blob()
      setPreview({ url: URL.createObjectURL(blob), error: null })
    } catch (err) {
      setPreview({ url: null, error: `Preview failed: ${err.message}` })
    }
  }

  return (
    <div className="preview-section">
      <button type="button" onClick={handlePreview}>
        Preview
      </button>
      {preview.error && <div className="preview-error">{preview.error}</div>}
      {preview.url && <img className="preview-image" src={preview.url} alt="Rendered frame preview" />}
    </div>
  )
}

export default CodePreview
