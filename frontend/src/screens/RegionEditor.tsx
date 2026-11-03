import { useRef, useState, type PointerEvent } from "react";
import { absoluteUrl } from "../api/client";
import { Button } from "../ui/Button";

export function RegionEditor({ imageUrl, disabled, onSubmit }: { imageUrl: string; disabled: boolean; onSubmit: (mask: Blob, instruction: string) => void }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const drawing = useRef(false);
  const [painted, setPainted] = useState(false);
  const [size, setSize] = useState(60);
  const [instruction, setInstruction] = useState("");

  function point(event: PointerEvent<HTMLCanvasElement>) {
    const el = event.currentTarget, bounds = el.getBoundingClientRect();
    return { x: (event.clientX - bounds.left) * el.width / bounds.width, y: (event.clientY - bounds.top) * el.height / bounds.height };
  }
  function down(event: PointerEvent<HTMLCanvasElement>) {
    if (disabled) return;
    const el = event.currentTarget, ctx = el.getContext("2d");
    if (!ctx) return;
    event.preventDefault(); el.setPointerCapture(event.pointerId); drawing.current = true;
    const p = point(event);
    ctx.strokeStyle = "#ff3f6d"; ctx.fillStyle = "#ff3f6d"; ctx.lineCap = "round"; ctx.lineJoin = "round";
    ctx.lineWidth = size * el.width / el.getBoundingClientRect().width;
    ctx.beginPath(); ctx.arc(p.x, p.y, ctx.lineWidth / 2, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(p.x, p.y); setPainted(true);
  }
  function move(event: PointerEvent<HTMLCanvasElement>) {
    if (!drawing.current) return;
    const ctx = event.currentTarget.getContext("2d");
    if (!ctx) return;
    const p = point(event); ctx.lineTo(p.x, p.y); ctx.stroke();
  }
  function clear() { const el = canvas.current; if (el) el.getContext("2d")?.clearRect(0, 0, el.width, el.height); setPainted(false); }
  return <div className="region-editor">
    <p>Paint the area to change. A full-image edit is blended into your selection; everything outside the paint stays unchanged. Edges may be visible.</p>
    <div className="region-editor__image"><img src={absoluteUrl(imageUrl)} alt="Image to paint a region on" onLoad={(event) => {
      const el = canvas.current; if (el) { el.width = event.currentTarget.naturalWidth; el.height = event.currentTarget.naturalHeight; setPainted(false); }
    }} />
      <canvas ref={canvas} aria-label="Paint the area to change" onPointerDown={down} onPointerMove={move} onPointerUp={() => { drawing.current = false; }} onPointerCancel={() => { drawing.current = false; }} />
    </div>
    <label htmlFor="region-size">Brush size: {size}px</label><input id="region-size" type="range" min="10" max="140" value={size} disabled={disabled} onChange={(event) => setSize(Number(event.target.value))} />
    <Button size="sm" disabled={disabled || !painted} onClick={clear}>Clear paint</Button>
    <label htmlFor="region-instruction">Change in painted area</label>
    <textarea id="region-instruction" className="text-input studio__textarea" rows={3} value={instruction} maxLength={2000} disabled={disabled}
      placeholder="Remove the spider face and blend the waist into the abdomen" onChange={(event) => setInstruction(event.target.value)} />
    <Button variant="primary" disabled={disabled || !painted || !instruction.trim()} onClick={() => canvas.current?.toBlob((blob) => { if (blob) onSubmit(blob, instruction.trim()); }, "image/png")}>
      Generate painted edit
    </Button>
  </div>;
}
