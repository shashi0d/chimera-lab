import { useReactFlow } from "@xyflow/react";
import { useEffect, useId, useState } from "react";
import { useShallow } from "zustand/react/shallow";
import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { hrefFor, linkHandler } from "../app/route";
import { evo } from "../evo/index";
import { useGraph } from "../graph/store";
import type { GraphNode } from "../graph/types";
import type { VersionData } from "../nodes/version/types";
import { Button, IconButton } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { labApi, type LabVersion } from "./api";
import { addEditNode, lineage, treeOf, versionNumber } from "./graph";
import { downloadVersion, updateVersion, useLab } from "./store";

const OPERATION: Record<string, string> = { fusion: "Fusion", revise: "Revise", paint: "Paint" };

function errorText(e: unknown): string {
  const p = presentError(toAppError(e));
  return p.fix ? `${p.title} ${p.fix}` : p.title;
}

function useFocusNode() {
  const flow = useReactFlow();
  return (node: GraphNode) => {
    useGraph.getState().setSelection([node.id]);
    void flow.setCenter(node.position.x + 170, node.position.y + 220, { zoom: Math.max(flow.getZoom(), 0.8), duration: 300 });
  };
}

// ------------------------------------------------------------------ sections

function Path({ nodeId }: { nodeId: string }) {
  // Shallow: the selector builds a new array each time; its items are the store's own node objects.
  const path = useGraph(useShallow(() => lineage(nodeId)));
  const focus = useFocusNode();
  return (
    <section className="tools__section" aria-labelledby="tools-path">
      <h3 id="tools-path">Path to this image</h3>
      <ol className="tools-path">
        {path.map((n, i) => {
          const v = (n.data as VersionData).version;
          return (
            <li key={n.id} className={n.id === nodeId ? "is-current" : ""}>
              <button type="button" className="tools-path__step" onClick={() => focus(n)} aria-current={n.id === nodeId ? "step" : undefined}>
                {v ? <img src={evo().imageUrl(v.imageUrl)} alt="" /> : <span className="tools-path__blank" />}
                <span>
                  <strong>
                    V{i + 1} · {OPERATION[v?.operation ?? "fusion"]}
                  </strong>
                  <span>{v?.operation === "fusion" ? v.title : v?.instruction}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

function Compare({ nodeId, version }: { nodeId: string; version: LabVersion }) {
  const others = useGraph(useShallow(() => treeOf(nodeId).filter((n) => n.id !== nodeId && (n.data as VersionData).version)));
  const [otherId, setOtherId] = useState("");
  const selectId = useId();
  const other = others.find((n) => n.id === otherId);
  const otherVersion = other ? (other.data as VersionData).version : null;
  if (!others.length) return null;
  return (
    <section className="tools__section" aria-labelledby="tools-compare">
      <h3 id="tools-compare">Compare</h3>
      <label htmlFor={selectId} className="sr-only">
        Compare with
      </label>
      <select id={selectId} className="text-input" value={otherId} onChange={(e) => setOtherId(e.target.value)}>
        <option value="">Compare with another version…</option>
        {others.map((n) => (
          <option key={n.id} value={n.id}>
            V{versionNumber(n.id)} · {OPERATION[(n.data as VersionData).version?.operation ?? "fusion"]}
            {(n.data as VersionData).version?.isFinal ? " · final" : ""}
          </option>
        ))}
      </select>
      {otherVersion ? (
        <div className="tools-compare">
          <figure>
            <img src={evo().imageUrl(version.imageUrl)} alt="This version" />
            <figcaption>This · V{versionNumber(nodeId)}</figcaption>
          </figure>
          <figure>
            <img src={evo().imageUrl(otherVersion.imageUrl)} alt="The other version" />
            <figcaption>V{versionNumber(other!.id)}</figcaption>
          </figure>
        </div>
      ) : null}
    </section>
  );
}

function Publish({ version }: { version: LabVersion }) {
  const [title, setTitle] = useState(version.title ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fieldId = useId();
  useEffect(() => setTitle(version.title ?? ""), [version.id, version.title]);
  const act = async (fn: () => Promise<LabVersion>) => {
    setBusy(true);
    setError("");
    try {
      updateVersion(await fn());
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <section className="tools__section" aria-labelledby="tools-publish">
      <h3 id="tools-publish">Gallery</h3>
      {version.publicationId ? (
        <>
          <p className="tools__note">
            <Icon name="globe" size={14} /> This version is in the gallery with its whole path.
          </p>
          <div className="tools__row">
            <a className="btn btn--secondary btn--sm" href={hrefFor({ view: "creation", publicationId: version.publicationId })} onClick={linkHandler({ view: "creation", publicationId: version.publicationId })}>
              View in the gallery
            </a>
            <Button size="sm" variant="ghost" busy={busy} disabled={busy} onClick={() => void act(() => labApi.unpublish(version.id))}>
              Remove from the gallery
            </Button>
          </div>
        </>
      ) : (
        <>
          <p className="tools__note">Publishing shows this image and every step that led to it. Your photos are never published.</p>
          <label htmlFor={fieldId}>Title</label>
          <input id={fieldId} className="text-input" maxLength={80} value={title} onChange={(e) => setTitle(e.target.value)} />
          <Button size="sm" variant="primary" icon="globe" busy={busy} disabled={busy || !title.trim()} onClick={() => void act(() => labApi.publish(version.id, title.trim()))}>
            Publish to the gallery
          </Button>
        </>
      )}
      {error ? (
        <p className="tools__error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}

// ------------------------------------------------------------------ panel

/** Tools for the selected image card (FLORA-style: the canvas holds the path, the panel acts on one image). */
export function ToolsPanel({ nodeId }: { nodeId: string }) {
  const node = useGraph((s) => s.nodes.find((n) => n.id === nodeId));
  const limits = useLab((s) => s.limits);
  const [finalBusy, setFinalBusy] = useState(false);
  const version = (node?.data as VersionData | undefined)?.version ?? null;
  const n = useGraph(() => versionNumber(nodeId));
  useEffect(() => {
    void useLab.getState().refreshLimits();
  }, [nodeId]);
  if (!node || !version) return null;
  const label = `${version.title ?? "creature"} V${n}`;

  const toggleFinal = async () => {
    setFinalBusy(true);
    try {
      updateVersion(await labApi.setFinal(version.id, !version.isFinal));
    } finally {
      setFinalBusy(false);
    }
  };

  return (
    <aside className="tools-panel" aria-label="Image tools">
      <header className="tools-panel__head">
        <div>
          <p className="node__kicker">
            V{n} · {OPERATION[version.operation]}
          </p>
          <h2>{version.title ?? "Creature"}</h2>
        </div>
        <IconButton icon="close" label="Close the tools" onClick={() => useGraph.getState().setSelection([])} />
      </header>
      <div className="tools-panel__body">
        <figure className="tools-panel__image">
          <img src={evo().imageUrl(version.imageUrl)} alt={`${label}`} />
          {version.operation !== "fusion" ? <figcaption>{version.instruction}</figcaption> : null}
        </figure>
        <div className="tools__row tools__row--wrap">
          <Button size="sm" variant="primary" icon="replace" onClick={() => addEditNode(nodeId, "revise")}>
            Revise
          </Button>
          <Button size="sm" icon="brush" onClick={() => addEditNode(nodeId, "paint")}>
            Paint an area
          </Button>
          <Button size="sm" icon="star" busy={finalBusy} aria-pressed={version.isFinal} onClick={() => void toggleFinal()}>
            {version.isFinal ? "Final ✓" : "Mark as final"}
          </Button>
          <Button size="sm" variant="ghost" icon="download" onClick={() => void downloadVersion(version, label)}>
            Download
          </Button>
        </div>
        {limits && limits.limit !== null ? (
          <p className="tools__note">
            {Math.max(0, limits.limit - limits.used)} of {limits.limit} lab actions left today (edits and cards). Resets at 00:00 UTC.
          </p>
        ) : null}
        <Path nodeId={nodeId} />
        <Compare nodeId={nodeId} version={version} />
        <Publish version={version} />
        {version.operation === "fusion" && version.creatureId ? (
          <p className="tools__note">
            <a href={hrefFor({ view: "creature", creatureId: version.creatureId })} onClick={linkHandler({ view: "creature", creatureId: version.creatureId })}>
              Open the Fusion run's creature card
            </a>
          </p>
        ) : null}
      </div>
    </aside>
  );
}
