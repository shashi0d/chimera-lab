import { upstreamNode } from "../../graph/queries";
import type { GraphDoc } from "../../graph/types";
import type { ResultData } from "../result/types";

/** The Result feeding this card and its currently selected version, if any. */
export function upstreamVersion(graph: Pick<GraphDoc, "nodes" | "edges">, cardId: string) {
  const src = upstreamNode(graph, cardId, "in");
  if (!src || src.type !== "result") return { result: undefined, version: undefined, index: -1, count: 0 };
  const data = src.data as ResultData;
  const versions = data.versions ?? [];
  const index = Math.min(Math.max(0, data.selected ?? 0), versions.length - 1);
  return { result: src, version: versions[index], index, count: versions.length };
}
