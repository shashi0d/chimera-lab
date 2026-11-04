import { useEffect, useState } from "react";
import { blobUrl } from "../../persistence/blobStore";
import type { ImageInputData } from "./types";

/** Object URL of the local copy (works offline). */
export function usePreview(data: Pick<ImageInputData, "blobKey">): string | undefined {
  const [url, setUrl] = useState<string | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    if (data.blobKey) {
      void blobUrl(data.blobKey).then((u) => {
        if (alive) setUrl(u);
      });
    } else setUrl(undefined);
    return () => {
      alive = false;
    };
  }, [data.blobKey]);
  return url;
}
