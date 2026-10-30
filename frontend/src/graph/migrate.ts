import { CURRENT_SCHEMA_VERSION, type GraphDoc, type GraphEdge, type GraphNode } from "./types";

export interface NodeMigrator {
  version: number;
  migrate?: (config: unknown, data: unknown, fromVersion: number) => { config: Record<string, unknown>; data: Record<string, unknown> };
}

export interface LoadReport {
  graph: GraphDoc;
  readOnly: boolean;
  orphanEdgesRemoved: number;
  migratedFrom: number | null;
  unknownTypes: string[];
}

export class GraphLoadError extends Error {}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

/**
 * Schema migrations, oldest first. v0 was the prototype format, which stored
 * `links: [{from, fromPort, to, toPort}]` and node `pos`.
 */
const MIGRATIONS: Record<number, (doc: Record<string, unknown>) => Record<string, unknown>> = {
  0: (doc) => {
    const links = Array.isArray(doc.links) ? (doc.links as Array<Record<string, unknown>>) : [];
    const nodes = Array.isArray(doc.nodes) ? (doc.nodes as Array<Record<string, unknown>>) : [];
    return {
      schemaVersion: 1,
      graphId: doc.graphId ?? doc.id,
      nodes: nodes.map((n) => ({ ...n, position: n.position ?? n.pos, version: n.version ?? 1 })),
      edges: links.map((l, i) => ({
        id: String(l.id ?? `e-migrated-${i}`),
        source: l.from,
        sourcePort: l.fromPort ?? "out",
        target: l.to,
        targetPort: l.toPort,
      })),
    };
  },
};

function coerceNode(raw: unknown): GraphNode | null {
  if (!isObject(raw) || typeof raw.id !== "string" || typeof raw.type !== "string") return null;
  const pos = isObject(raw.position) ? raw.position : {};
  return {
    id: raw.id,
    type: raw.type,
    version: typeof raw.version === "number" ? raw.version : 1,
    position: { x: Number(pos.x) || 0, y: Number(pos.y) || 0 },
    config: isObject(raw.config) ? raw.config : {},
    data: isObject(raw.data) ? raw.data : {},
  };
}

function coerceEdge(raw: unknown): GraphEdge | null {
  if (!isObject(raw)) return null;
  const { id, source, sourcePort, target, targetPort } = raw;
  if ([id, source, sourcePort, target, targetPort].some((v) => typeof v !== "string")) return null;
  return { id, source, sourcePort, target, targetPort } as GraphEdge;
}

/** Validate, migrate and repair a stored graph. Throws GraphLoadError if it's unusable. */
export function loadGraph(raw: unknown, nodeMigrators: (type: string) => NodeMigrator | undefined): LoadReport {
  if (!isObject(raw)) throw new GraphLoadError("not an object");
  let doc = raw;
  let version = typeof doc.schemaVersion === "number" ? doc.schemaVersion : 0;
  const startVersion = version;
  if (version > CURRENT_SCHEMA_VERSION) {
    // Newer than this app: show it read-only rather than risk corrupting it.
    const nodes = (Array.isArray(doc.nodes) ? doc.nodes : []).map(coerceNode).filter((n): n is GraphNode => n !== null);
    const edges = (Array.isArray(doc.edges) ? doc.edges : []).map(coerceEdge).filter((e): e is GraphEdge => e !== null);
    if (typeof doc.graphId !== "string") throw new GraphLoadError("missing graphId");
    return { graph: { schemaVersion: version, graphId: doc.graphId, nodes, edges }, readOnly: true, orphanEdgesRemoved: 0, migratedFrom: null, unknownTypes: [] };
  }
  while (version < CURRENT_SCHEMA_VERSION) {
    const step = MIGRATIONS[version];
    if (!step) throw new GraphLoadError(`no migration from schema ${version}`);
    doc = step(doc);
    version = typeof doc.schemaVersion === "number" ? doc.schemaVersion : version + 1;
  }
  if (typeof doc.graphId !== "string" || !Array.isArray(doc.nodes) || !Array.isArray(doc.edges)) {
    throw new GraphLoadError("malformed graph");
  }
  const unknownTypes: string[] = [];
  const nodes: GraphNode[] = [];
  const seen = new Set<string>();
  for (const rawNode of doc.nodes) {
    const node = coerceNode(rawNode);
    if (!node || seen.has(node.id)) continue;
    seen.add(node.id);
    const migrator = nodeMigrators(node.type);
    if (!migrator) {
      unknownTypes.push(node.type);
    } else if (node.version < migrator.version && migrator.migrate) {
      const next = migrator.migrate(node.config, node.data, node.version);
      node.config = next.config;
      node.data = next.data;
      node.version = migrator.version;
    }
    nodes.push(node);
  }
  const edges: GraphEdge[] = [];
  let orphans = 0;
  for (const rawEdge of doc.edges) {
    const edge = coerceEdge(rawEdge);
    if (!edge || !seen.has(edge.source) || !seen.has(edge.target)) {
      orphans++;
      continue;
    }
    edges.push(edge);
  }
  if (orphans) console.info(`[graph] removed ${orphans} orphan edge(s) on load`);
  return {
    graph: { schemaVersion: CURRENT_SCHEMA_VERSION, graphId: doc.graphId, nodes, edges },
    readOnly: false,
    orphanEdgesRemoved: orphans,
    migratedFrom: startVersion < CURRENT_SCHEMA_VERSION ? startVersion : null,
    unknownTypes,
  };
}
