import { CURRENT_SCHEMA_VERSION, type GraphDoc } from "../graph/types";
import type { LabVersion } from "../lab/api";
import { nodeRegistry } from "../nodes/registry";
import data from "./example.json";

/**
 * The tutorial's example workspace: one real creature (Tiger × Bat, anime) made once by scripts/make_example.py and
 * shipped as static files (public/example/). It lives only in the browser: read-only, never saved, no API calls.
 */

export const EXAMPLE_WS = "example";
export const EXAMPLE_IDS = { fusion: "example-fusion", version: "example-v1", card: "example-card" } as const;

export const exampleVersion = data.version as unknown as LabVersion;

export function isExampleWorkspace(id: string | null | undefined): boolean {
  return id === EXAMPLE_WS;
}

function defaults(type: string) {
  const def = nodeRegistry[type]!;
  return { version: def.version, config: { ...def.defaultConfig }, data: def.defaultData() };
}

/** Fusion (Tiger + Bat, anime) → its image (V1) → the animal card, laid out left to right. */
export function exampleGraph(): GraphDoc {
  const fusion = defaults("fusion");
  const version = defaults("version");
  const card = defaults("card");
  return {
    schemaVersion: CURRENT_SCHEMA_VERSION,
    graphId: "example",
    nodes: [
      {
        id: EXAMPLE_IDS.fusion, type: "fusion", version: fusion.version, position: { x: 0, y: 0 },
        config: { ...fusion.config, style: data.style }, data: { ...fusion.data, activeRunId: null, runIds: [], names: data.names },
      },
      {
        id: EXAMPLE_IDS.version, type: "version", version: version.version, position: { x: 410, y: 0 },
        config: version.config, data: { ...version.data, version: exampleVersion, runId: null, error: null },
      },
      {
        id: EXAMPLE_IDS.card, type: "card", version: card.version, position: { x: 840, y: 0 },
        config: card.config, data: { ...card.data, card: exampleVersion.card, versionId: exampleVersion.id, autoStart: false, error: null },
      },
    ],
    edges: [
      { id: "example-e1", source: EXAMPLE_IDS.fusion, sourcePort: "out", target: EXAMPLE_IDS.version, targetPort: "in" },
      { id: "example-e2", source: EXAMPLE_IDS.version, sourcePort: "out", target: EXAMPLE_IDS.card, targetPort: "in" },
    ],
  };
}
