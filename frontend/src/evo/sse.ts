// Incremental text/event-stream parser (WHATWG rules, the parts the contract uses):
// "id:", "event:", "data:" (multi-line joined by \n), ":" comments (the 15 s keep-alive), blank line dispatches.

export interface SseMessage {
  id: string | null;
  event: string;
  data: string;
}

export class SseParser {
  private buffer = "";
  private id: string | null = null;
  private event = "";
  private data: string[] = [];

  /** Feed a chunk; returns the messages it completed. */
  push(chunk: string): SseMessage[] {
    this.buffer += chunk;
    const out: SseMessage[] = [];
    let nl: number;
    while ((nl = this.buffer.search(/\r\n|\r|\n/)) >= 0) {
      const line = this.buffer.slice(0, nl);
      const sep = this.buffer[nl] === "\r" && this.buffer[nl + 1] === "\n" ? 2 : 1;
      // A lone trailing "\r" may be the first half of "\r\n": wait for more input.
      if (this.buffer[nl] === "\r" && nl + 1 === this.buffer.length) break;
      this.buffer = this.buffer.slice(nl + sep);
      const msg = this.line(line);
      if (msg) out.push(msg);
    }
    return out;
  }

  private line(line: string): SseMessage | null {
    if (line === "") {
      if (!this.data.length) {
        this.event = "";
        return null;
      }
      const msg = { id: this.id, event: this.event || "message", data: this.data.join("\n") };
      this.event = "";
      this.data = [];
      return msg;
    }
    if (line.startsWith(":")) return null; // comment / keep-alive
    const colon = line.indexOf(":");
    const field = colon < 0 ? line : line.slice(0, colon);
    let value = colon < 0 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "data") this.data.push(value);
    else if (field === "event") this.event = value;
    else if (field === "id" && !value.includes("\0")) this.id = value;
    return null;
  }
}
