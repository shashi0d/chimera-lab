import { ACCEPT_ATTR } from "../nodes/image-input/validate";

/** Opens the native file picker; resolves with the chosen files (empty if dismissed). */
export function pickImages(multiple = true): Promise<File[]> {
  return new Promise((resolve) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ACCEPT_ATTR;
    input.multiple = multiple;
    input.className = "sr-only";
    input.setAttribute("data-testid", "file-picker");
    let settled = false;
    const done = (files: File[]) => {
      if (settled) return;
      settled = true;
      input.remove();
      resolve(files);
    };
    input.addEventListener("change", () => done(Array.from(input.files ?? [])));
    input.addEventListener("cancel", () => done([]));
    document.body.appendChild(input);
    input.click();
  });
}
