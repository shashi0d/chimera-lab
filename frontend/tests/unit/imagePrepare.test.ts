import { afterEach, describe, expect, it } from "vitest";
import { browserCodec, prepareImage, setImageCodec, type ImageCodec } from "../../src/nodes/image-input/codec";
import { sniffKind, targetSize } from "../../src/nodes/image-input/validate";

const JPEG = [0xff, 0xd8, 0xff, 0xe0];
const PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
const bytes = (head: number[], size = 64) => new Blob([new Uint8Array([...head, ...new Array(Math.max(0, size - head.length)).fill(0)])]);
const ascii = (s: string) => Array.from(s, (c) => c.charCodeAt(0));

function fakeCodec(width: number, height: number, opts: { fail?: boolean } = {}): ImageCodec & { encoded: Array<[number, number, string]> } {
  const encoded: Array<[number, number, string]> = [];
  return {
    encoded,
    async decode() {
      if (opts.fail) throw new Error("undecodable");
      return { width, height, source: {} as CanvasImageSource, close: () => undefined };
    },
    async encode(_s, w, h, type) {
      encoded.push([w, h, type]);
      return new Blob(["x"], { type });
    },
  };
}

afterEach(() => setImageCodec(browserCodec));

describe("client image checks (TASKSHEET 7.1)", () => {
  it("sniffs real formats from magic bytes", () => {
    expect(sniffKind(new Uint8Array(JPEG))).toBe("jpeg");
    expect(sniffKind(new Uint8Array(PNG))).toBe("png");
    expect(sniffKind(new Uint8Array([...ascii("RIFF"), 0, 0, 0, 0, ...ascii("WEBP")]))).toBe("webp");
    expect(sniffKind(new Uint8Array([0, 0, 0, 24, ...ascii("ftypheic")]))).toBe("heif");
    expect(sniffKind(new Uint8Array(ascii("GIF89a")))).toBeNull();
    expect(sniffKind(new Uint8Array(ascii("%PDF-1.4")))).toBeNull();
    expect(sniffKind(new Uint8Array(ascii("<svg xmlns")))).toBeNull();
  });

  it("rejects unsupported types without creating anything", async () => {
    const r = await prepareImage(bytes(ascii("GIF89a")));
    expect(r).toMatchObject({ ok: false, error: { code: "UNSUPPORTED_FILE" } });
  });

  it("rejects files over 20 MB before reading them", async () => {
    const big = new Blob([new Uint8Array(20 * 1024 * 1024 + 1)]);
    expect(await prepareImage(big)).toMatchObject({ ok: false, error: { code: "FILE_TOO_LARGE" } });
  });

  it("rejects undecodable images as IMAGE_CORRUPT", async () => {
    setImageCodec(fakeCodec(800, 600, { fail: true }));
    expect(await prepareImage(bytes(JPEG))).toMatchObject({ ok: false, error: { code: "IMAGE_CORRUPT" } });
  });

  it("rejects images under 256px on the short side", async () => {
    setImageCodec(fakeCodec(1200, 200));
    expect(await prepareImage(bytes(JPEG))).toMatchObject({ ok: false, error: { code: "IMAGE_TOO_SMALL" } });
  });

  it("downscales to 2048px on the long edge and re-encodes (strips EXIF)", async () => {
    const codec = fakeCodec(4096, 3072);
    setImageCodec(codec);
    const r = await prepareImage(bytes(JPEG));
    expect(r.ok).toBe(true);
    expect(codec.encoded).toEqual([[2048, 1536, "image/jpeg"]]);
  });

  it("keeps PNG as PNG (alpha) and leaves normal sizes alone", async () => {
    const codec = fakeCodec(900, 700);
    setImageCodec(codec);
    await prepareImage(bytes(PNG));
    expect(codec.encoded).toEqual([[900, 700, "image/png"]]);
  });

  it("passes HEIC through untouched for server-side conversion", async () => {
    const heic = bytes([0, 0, 0, 24, ...ascii("ftypheic")]);
    const r = await prepareImage(heic);
    expect(r).toMatchObject({ ok: true, image: { blob: heic, width: null } });
  });

  it("computes target sizes", () => {
    expect(targetSize(1000, 500)).toEqual({ width: 1000, height: 500, scaled: false });
    expect(targetSize(3000, 6000)).toEqual({ width: 1024, height: 2048, scaled: true });
  });
});
