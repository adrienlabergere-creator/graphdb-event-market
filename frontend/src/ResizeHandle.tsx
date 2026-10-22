// The draggable border of a resizable panel.
export function ResizeHandle({ onPointerDown, onDoubleClick, side }: {
  onPointerDown: (e: React.PointerEvent) => void
  onDoubleClick: () => void
  side: 'left' | 'right'
}) {
  return (
    <div
      role="separator"
      aria-orientation="vertical"
      title="Drag to resize, double-click to reset"
      onPointerDown={onPointerDown}
      onDoubleClick={onDoubleClick}
      className={`group absolute top-0 z-10 h-full w-2 cursor-col-resize ${side === 'left' ? '-right-1' : '-left-1'}`}
    >
      <div className="mx-auto h-full w-px bg-transparent transition-colors group-hover:bg-accent group-active:bg-accent" />
    </div>
  )
}
