import { absoluteUrl } from "../../api/client";
import type { FieldCard } from "../../types/api";

// Draws the field card onto a canvas using the current theme tokens and the
// self-hosted fonts, so the PNG matches the on-canvas card. Works offline once
// the plate image is cached. Token names are checked against theme.css by
// tests/unit/renderPngTokens.test.ts (U1 renamed every token once already).

/** Theme tokens the PNG is painted with (ZD names; see docs/DESIGN_U1.md). */
export const PNG_TOKENS = ["--surface-card", "--text-strong", "--text-muted", "--line-input-strong", "--success-text-aa", "--accent-text"] as const;
export const PNG_FONTS = ["600 56px 'Space Grotesk'", "italic 400 36px 'Hanken Grotesk'", "400 24px 'Hanken Grotesk'", "500 18px 'JetBrains Mono'", "600 22px 'Hanken Grotesk'", "500 20px 'Hanken Grotesk'"] as const;

const W = 1600;
const H = 1000;

function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "currentColor";
}

function wrap(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, maxWidth: number, lineHeight: number, maxLines = 6): number {
  const words = text.split(/\s+/);
  let line = "";
  let lines = 0;
  for (const w of words) {
    const test = line ? `${line} ${w}` : w;
    if (ctx.measureText(test).width > maxWidth && line) {
      ctx.fillText(line, x, y);
      y += lineHeight;
      line = w;
      if (++lines >= maxLines - 1) break;
    } else line = test;
  }
  if (line) {
    ctx.fillText(line, x, y);
    y += lineHeight;
  }
  return y;
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("plate image failed to load"));
    img.src = absoluteUrl(src);
  });
}

export async function renderCardPng(card: FieldCard, imageUrl: string): Promise<Blob> {
  await Promise.all(PNG_FONTS.map((f) => document.fonts?.load(f)));
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("no canvas");
  const [paper, ink, muted, rule, moss, lapis] = PNG_TOKENS.map(token) as unknown as [string, string, string, string, string, string];

  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, W, H);
  ctx.strokeStyle = ink;
  ctx.lineWidth = 3;
  ctx.strokeRect(24, 24, W - 48, H - 48);

  const plate = await loadImage(imageUrl);
  ctx.drawImage(plate, 64, 64, 820, 820);
  ctx.lineWidth = 2;
  ctx.strokeRect(64, 64, 820, 820);
  ctx.fillStyle = moss;
  ctx.font = "600 22px 'Hanken Grotesk'";
  ctx.fillText("Generated fusion · not a real animal", 64, 924);

  const x = 940;
  const w = W - x - 72;
  ctx.fillStyle = muted;
  ctx.font = "500 18px 'JetBrains Mono'";
  ctx.fillText("CHIMERA LAB · FIELD CARD", x, 100);
  ctx.fillStyle = ink;
  ctx.font = "600 56px 'Space Grotesk'";
  let y = wrap(ctx, card.commonName, x, 170, w, 62, 2);
  ctx.font = "italic 400 36px 'Hanken Grotesk'";
  ctx.fillText(card.binomial, x, y + 4);
  const bw = ctx.measureText(card.binomial).width;
  ctx.fillStyle = lapis;
  ctx.font = "500 18px 'JetBrains Mono'";
  ctx.fillText("(invented name)", x + bw + 16, y + 2);
  y += 56;

  const rows: Array<[string, string]> = [
    ["Habitat", card.habitat],
    ["Diet", card.diet],
    ["Size", card.size],
    ["Behaviour", card.behaviour],
  ];
  for (const [label, text] of rows) {
    ctx.strokeStyle = rule;
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(x, y - 30);
    ctx.lineTo(x + w, y - 30);
    ctx.stroke();
    ctx.fillStyle = muted;
    ctx.font = "500 18px 'JetBrains Mono'";
    ctx.fillText(label.toUpperCase(), x, y);
    ctx.fillStyle = ink;
    ctx.font = "400 24px 'Hanken Grotesk'";
    y = wrap(ctx, text, x, y + 34, w, 32, 4) + 28;
  }
  ctx.fillStyle = moss;
  ctx.font = "500 20px 'Hanken Grotesk'";
  wrap(ctx, card.provenance, x, Math.max(y, H - 120), w, 28, 3);

  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("encode failed"))), "image/png"));
}

export function downloadBlob(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
