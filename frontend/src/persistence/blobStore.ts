import { createStore, del, get, set } from "idb-keyval";

// Local copies of input images: previews work offline and queued uploads survive reloads.
let store: ReturnType<typeof createStore> | null = null;
function db() {
  store ??= createStore("chimera-lab-blobs", "blobs");
  return store;
}

const objectUrls = new Map<string, string>();

export async function putBlob(key: string, blob: Blob): Promise<void> {
  await set(key, blob, db());
}

export async function getBlob(key: string): Promise<Blob | undefined> {
  try {
    return (await get(key, db())) as Blob | undefined;
  } catch {
    return undefined;
  }
}

export async function deleteBlob(key: string): Promise<void> {
  const url = objectUrls.get(key);
  if (url) URL.revokeObjectURL(url);
  objectUrls.delete(key);
  await del(key, db());
}

/** Object URL for a stored blob, cached per key. */
export async function blobUrl(key: string): Promise<string | undefined> {
  const cached = objectUrls.get(key);
  if (cached) return cached;
  const blob = await getBlob(key);
  if (!blob) return undefined;
  const url = URL.createObjectURL(blob);
  objectUrls.set(key, url);
  return url;
}

export function rememberBlobUrl(key: string, blob: Blob): string {
  const url = URL.createObjectURL(blob);
  objectUrls.set(key, url);
  return url;
}
