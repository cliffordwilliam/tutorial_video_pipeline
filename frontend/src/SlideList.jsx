function SlideList({ slides, selectedIndex, onSelect, onAddCode, onAddImage, onDelete }) {
  return (
    <div className="slide-list">
      <div className="slide-list-actions">
        <button type="button" onClick={onAddCode}>
          + Code slide
        </button>
        <button type="button" onClick={onAddImage}>
          + Image slide
        </button>
      </div>
      <ul>
        {slides.map((slide, i) => (
          <li key={slide._key} className={i === selectedIndex ? 'selected' : ''}>
            <button type="button" className="slide-row" onClick={() => onSelect(i)}>
              <span className="slide-type">{slide.type}</span>
              <span className="slide-voice">{slide.voice || '(no voice line)'}</span>
            </button>
            <button
              type="button"
              className="slide-delete"
              onClick={() => onDelete(i)}
              aria-label="Delete slide"
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

export default SlideList
