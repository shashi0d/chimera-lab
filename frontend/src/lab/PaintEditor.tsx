import { useRef, useState, type PointerEvent } from "react";
import { absoluteUrl } from "../api/client";
import { Button } from "../ui/Button";

type Point = { x: number; y: number };
type Stroke = { points: Point[]; width: number; erase: boolean; color: string };
const CHECK_SIZE = 256;
const MASK_COLOR = "#ff3f6d";
const SKETCH_COLORS = ["#e5484d", "#f5a524", "#30a46c", "#0090ff", "#8e4ec6", "#1c2024", "#ffffff"];

/**
 * Two uses. "mask": paint the area an edit may change (pixels outside the paint stay exactly as they are).
 * "sketch": draw what you want on the creature, in colour; the model turns the drawing into the creature.
 */
export function PaintEditor({ imageUrl, disabled, onSave, mode = "mask" }: { imageUrl: string; disabled: boolean; onSave: (mask: Blob) => void; mode?: "mask" | "sketch" }) {
  const sketch = mode === "sketch";
  const [color, setColor] = useState(sketch ? SKETCH_COLORS[0]! : MASK_COLOR);
  const canvas = useRef<HTMLCanvasElement>(null);
  const active = useRef<Stroke | null>(null);
  const strokes = useRef<Stroke[]>([]);
  const undone = useRef<Stroke[]>([]);
  const [painted, setPainted] = useState(false);
  const [history, setHistory] = useState({ undo: 0, redo: 0 });
  const [erase, setErase] = useState(false);
  const [size, setSize] = useState(sketch ? 14 : 60);

  function point(event: PointerEvent<HTMLCanvasElement>) {
    const el = event.currentTarget, bounds = el.getBoundingClientRect();
    return { x: (event.clientX - bounds.left) * el.width / bounds.width, y: (event.clientY - bounds.top) * el.height / bounds.height };
  }
  function configure(ctx: CanvasRenderingContext2D, stroke: Stroke) {
    ctx.globalCompositeOperation = stroke.erase ? "destination-out" : "source-over";
    ctx.strokeStyle = stroke.color; ctx.fillStyle = stroke.color; ctx.lineCap = "round"; ctx.lineJoin = "round"; ctx.lineWidth = stroke.width;
  }
  function draw(ctx: CanvasRenderingContext2D, stroke: Stroke) {
    const first = stroke.points[0];
    if (!first) return;
    configure(ctx, stroke);
    ctx.beginPath(); ctx.arc(first.x, first.y, stroke.width / 2, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(first.x, first.y);
    for (const p of stroke.points.slice(1)) ctx.lineTo(p.x, p.y);
    ctx.stroke(); ctx.globalCompositeOperation = "source-over";
  }
  function updateState() {
    const el = canvas.current, ctx = el?.getContext("2d");
    if (!el || !ctx) return;
    // Check a downscaled copy: the scan stays small on large images, and any brush stroke survives the scaling.
    const scale = Math.min(1, CHECK_SIZE / Math.max(el.width, el.height));
    const probe = document.createElement("canvas");
    probe.width = Math.max(1, Math.round(el.width * scale)); probe.height = Math.max(1, Math.round(el.height * scale));
    const probeCtx = probe.getContext("2d");
    let hasPaint = strokes.current.length > 0;
    if (probeCtx) {
      probeCtx.drawImage(el, 0, 0, probe.width, probe.height);
      const pixels = probeCtx.getImageData(0, 0, probe.width, probe.height).data;
      hasPaint = false;
      for (let i = 3; i < pixels.length; i += 4) if (pixels[i]) { hasPaint = true; break; }
    }
    setPainted(hasPaint); setHistory({ undo: strokes.current.length, redo: undone.current.length });
  }
  function redraw() {
    const el = canvas.current, ctx = el?.getContext("2d");
    if (!el || !ctx) return;
    ctx.clearRect(0, 0, el.width, el.height);
    for (const stroke of strokes.current) draw(ctx, stroke);
    updateState();
  }
  function down(event: PointerEvent<HTMLCanvasElement>) {
    if (disabled) return;
    const el = event.currentTarget, ctx = el.getContext("2d");
    if (!ctx) return;
    event.preventDefault(); el.setPointerCapture(event.pointerId);
    const p = point(event);
    const stroke: Stroke = { points: [p], width: size * el.width / el.getBoundingClientRect().width, erase, color };
    active.current = stroke; configure(ctx, stroke);
    ctx.beginPath(); ctx.arc(p.x, p.y, stroke.width / 2, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.moveTo(p.x, p.y);
  }
  function move(event: PointerEvent<HTMLCanvasElement>) {
    if (!active.current) return;
    const ctx = event.currentTarget.getContext("2d");
    if (!ctx) return;
    const p = point(event); active.current.points.push(p); ctx.lineTo(p.x, p.y); ctx.stroke();
  }
  function finish() {
    if (!active.current) return;
    strokes.current.push(active.current); active.current = null; undone.current = [];
    const ctx = canvas.current?.getContext("2d"); if (ctx) ctx.globalCompositeOperation = "source-over";
    updateState();
  }
  function undo() { const stroke = strokes.current.pop(); if (stroke) { undone.current.push(stroke); redraw(); } }
  function redo() { const stroke = undone.current.pop(); if (stroke) { strokes.current.push(stroke); redraw(); } }
  function clear() { active.current = null; strokes.current = []; undone.current = []; redraw(); }
  return <div className={`region-editor${sketch ? " region-editor--sketch" : ""}`}>
    <p>{sketch
      ? "Draw what you want on the creature: a horn, wings, a new pattern or colour. The model turns your drawing into the creature, in its art style, and removes the lines."
      : "Paint the area to change. The edit is blended into your paint; everything outside it stays exactly as it is. Edges may be visible."}</p>
    <div className="region-editor__image"><img src={absoluteUrl(imageUrl)} alt="Image to paint a region on" onLoad={(event) => {
      const el = canvas.current; if (el) { el.width = event.currentTarget.naturalWidth; el.height = event.currentTarget.naturalHeight; clear(); }
    }} />
      <canvas ref={canvas} tabIndex={0} aria-label={sketch ? "Draw on the creature" : "Paint the area to change"} onPointerDown={down} onPointerMove={move} onPointerUp={finish} onPointerCancel={finish} onLostPointerCapture={finish}
        onKeyDown={(event) => { if (!disabled && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") { event.preventDefault(); if (event.shiftKey) redo(); else undo(); } }} />
    </div>
    {sketch ? <div className="region-editor__colors" role="radiogroup" aria-label="Pen colour">
      {SKETCH_COLORS.map((c) => <button key={c} type="button" role="radio" aria-checked={color === c && !erase} aria-label={`Colour ${c}`} className={`swatch swatch--${c.slice(1)}${color === c && !erase ? " is-on" : ""}`} disabled={disabled} onClick={() => { setColor(c); setErase(false); }} />)}
    </div> : null}
    <label htmlFor="region-size">{sketch ? "Pen size" : "Brush size"}: {size}px</label><input id="region-size" type="range" min={sketch ? 3 : 10} max={sketch ? 60 : 140} value={size} disabled={disabled} onChange={(event) => setSize(Number(event.target.value))} />
    <div className="region-editor__tools" aria-label="Paint tools">
      <Button size="sm" disabled={disabled} aria-pressed={!erase} onClick={() => setErase(false)}>{sketch ? "Pen" : "Brush"}</Button>
      <Button size="sm" disabled={disabled} aria-pressed={erase} onClick={() => setErase(true)}>Eraser</Button>
      <Button size="sm" disabled={disabled || !history.undo} onClick={undo}>Undo stroke</Button>
      <Button size="sm" disabled={disabled || !history.redo} onClick={redo}>Redo stroke</Button>
      <Button size="sm" disabled={disabled || !history.undo} onClick={clear}>{sketch ? "Clear drawing" : "Clear paint"}</Button>
    </div>
    <Button variant="primary" icon="check" disabled={disabled || !painted} onClick={() => canvas.current?.toBlob((blob) => { if (blob) onSave(blob); }, "image/png")}>
      {sketch ? "Use this drawing" : "Use this area"}
    </Button>
  </div>;
}
