import type { StudioVersion } from "./StudioCanvas";

/** Group versions by their oldest available ancestor without hiding incomplete histories. */
export function projectId(version: StudioVersion, versions: StudioVersion[]): string {
  const byId = new Map(versions.map((v) => [v.id, v]));
  let node = version;
  const seen = new Set<string>();
  while (node.parentId) {
    if (seen.has(node.id)) return [...seen].sort()[0] ?? node.id;
    seen.add(node.id);
    const parent = byId.get(node.parentId);
    if (!parent) break;
    node = parent;
  }
  return node.id;
}

export function groupProjects(versions: StudioVersion[]): { id: string; versions: StudioVersion[] }[] {
  const groups = new Map<string, StudioVersion[]>();
  for (const version of versions) {
    const id = projectId(version, versions);
    const group = groups.get(id) ?? [];
    group.push(version);
    groups.set(id, group);
  }
  return [...groups].map(([id, items]) => ({ id, versions: items }));
}
