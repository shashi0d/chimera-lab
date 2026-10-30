import { useEffect, useState } from "react";
import { absoluteUrl } from "../../api/client";
import { blobUrl } from "../../persistence/blobStore";
import type { ImageInputData } from "./types";

/** Local copy first (works offline), then the server URL. */
export function usePreview(data: Pick<ImageInputData, "blobKey" | "serverUrl">): string | undefined {
  const [url, setUrl] = useState<string | undefined>(undefined);
  useEffect(() => {
    let alive = true;
    if (data.blobKey) {
      void blobUrl(data.blobKey).then((u) => {
        if (alive) setUrl(u ?? (data.serverUrl ? absoluteUrl(data.serverUrl) : undefined));
      });
    } else {
      setUrl(data.serverUrl ? absoluteUrl(data.serverUrl) : undefined);
    }
    return () => {
      alive = false;
    };
  }, [data.blobKey, data.serverUrl]);
  return url;
}
