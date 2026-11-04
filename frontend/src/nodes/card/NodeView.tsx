import { useEffect, useRef, useState } from "react";
import { toAppError } from "../../api/errors";
import { presentError } from "../../api/errorMessages";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { evo } from "../../evo/index";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { labApi, type AnimalCard, type LabVersion } from "../../lab/api";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import type { NodeViewProps } from "../types";
import type { VersionData } from "../version/types";
import { CARD_INPUTS, CARD_OUTPUTS, type CardConfig, type CardData } from "./types";

const POLL_MS = 3000;
const busy = new Set<string>(); // card node ids with a request in flight

const VIEW_LABEL: Record<string, string> = { front: "Front", side: "Side", back: "Back", above: "Above" };

function setCard(nodeId: string, patch: Partial<CardData>): void {
  useGraph.getState().updateNodeData<CardData>(nodeId, (d) => ({ ...d, ...patch }));
}

function errorText(e: unknown): string {
  const p = presentError(toAppError(e));
  return `${p.title}${p.fix ? ` ${p.fix}` : ""}`;
}

/** Ask for the image's card: the server makes it once (in the background) and returns the same card after that. */
async function requestCard(nodeId: string, versionId: string): Promise<void> {
  if (busy.has(nodeId)) return;
  busy.add(nodeId);
  setCard(nodeId, { autoStart: false, error: null, versionId });
  try {
    setCard(nodeId, { card: await labApi.card(versionId) });
  } catch (e) {
    setCard(nodeId, { error: errorText(e) });
  } finally {
    busy.delete(nodeId);
  }
}

/** Follow a card that is being made until it is ready or failed. */
function usePoll(nodeId: string, versionId: string | null, running: boolean): void {
  useEffect(() => {
    if (!running || !versionId) return;
    let stop = false;
    const tick = async () => {
      try {
        const card = await labApi.savedCard(versionId);
        if (!stop && card) setCard(nodeId, { card });
      } catch {
        // offline for a moment: try again on the next tick
      }
    };
    const id = window.setInterval(() => void tick(), POLL_MS);
    void tick();
    return () => {
      stop = true;
      window.clearInterval(id);
    };
  }, [nodeId, versionId, running]);
}

/** The accent panel behind the creature takes the profile's colour (no inline style props: set on the element). */
function useAccent(colour: string | undefined) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (ref.current && colour) ref.current.style.setProperty("--codex-accent", colour);
  }, [colour]);
  return ref;
}

function Codex({ card, version }: { card: AnimalCard; version: LabVersion }) {
  const p = card.profile;
  const accentRef = useAccent(p?.accent_color);
  const [why, setWhy] = useState(false);
  const image = evo().imageUrl(version.imageUrl);
  const name = p?.name || version.title || "Unnamed creature";
  return (
    <div className="codex nodrag nowheel" ref={accentRef}>
      <span className="codex__corner codex__corner--tr" aria-hidden="true" />
      <span className="codex__corner codex__corner--bl" aria-hidden="true" />
      <div className="codex__text">
        <h4 className="codex__name">{name}</h4>
        {p ? (
          <>
            <p className="codex__stat">
              Length - {p.length || "unknown"}
              <span className="codex__gap" />
              Weight - {p.weight || "unknown"}
            </p>
            <p className="codex__stat">Habitat - {p.habitat || "unknown"}</p>
          </>
        ) : null}
        <img className="codex__thumb" src={image} alt="" loading="lazy" decoding="async" />
        {p?.explorers_notes ? (
          <p className="codex__notes">
            <strong>Explorer's Notes -</strong> {p.explorers_notes}
          </p>
        ) : null}
      </div>
      <figure className="codex__hero">
        <span className="codex__panel" aria-hidden="true" />
        <img src={image} alt={`${name}, the main view`} loading="lazy" decoding="async" />
      </figure>
      <ul className="codex__angles" aria-label="Other angles">
        {card.angles.map((a) => (
          <li key={a.view}>
            <img src={evo().imageUrl(a.url)} alt={`${name}, ${VIEW_LABEL[a.view] ?? a.view} view`} loading="lazy" decoding="async" />
            <span>{VIEW_LABEL[a.view] ?? a.view}</span>
          </li>
        ))}
        {Array.from({ length: Math.max(0, 4 - card.angles.length) }, (_, i) => (
          <li key={`empty-${i}`} className="is-empty" aria-hidden="true" />
        ))}
      </ul>
      {p?.trait ? <p className="codex__trait">{p.trait}</p> : null}
      {p?.reasoning ? (
        <div className="codex__why">
          <button type="button" className="btn btn--ghost btn--sm" aria-expanded={why} onClick={() => setWhy((v) => !v)}>
            {why ? "Hide the model's reasoning" : "Why this entry?"}
          </button>
          {why ? <p className="codex__reasoning">{p.reasoning}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

/** The animal card of the connected image (one per image): a field-guide page with four more angles. */
export function CardView({ node, selected }: NodeViewProps<CardConfig, CardData>) {
  const { card, autoStart, error } = node.data;
  const readOnly = useGraph((s) => s.readOnly);
  const parentData = useGraph((s) => {
    const up = upstreamNode(s, node.id, "in");
    return up?.type === "version" ? (up.data as VersionData) : null;
  });
  const version = parentData?.version ?? null;
  const running = card?.status === "running";
  usePoll(node.id, version?.id ?? null, running);

  useEffect(() => {
    if (autoStart && version && !readOnly && !card) void requestCard(node.id, version.id);
  }, [autoStart, version, readOnly, card, node.id]);

  let status: NodeStatus | undefined;
  if (running || busy.has(node.id)) status = { tone: "running", label: "Making the card" };
  else if (error || card?.status === "failed") status = { tone: "error", label: "Failed" };
  else if (card?.status === "ready") status = { tone: "ok", label: "Ready" };

  const canRetry = Boolean(version && !readOnly && (error || card?.status === "failed" || (!card && !autoStart)));
  return (
    <NodeCard
      nodeId={node.id}
      kind="card"
      kicker="Animal card"
      title={`Animal card: ${card?.profile?.name || version?.title || "new creature"}`}
      status={status}
      inputs={CARD_INPUTS}
      outputs={CARD_OUTPUTS}
      selected={selected}
      className={running ? "is-running" : ""}
      media={card?.status === "ready" && version ? <Codex card={card} version={version} /> : undefined}
      footer={
        canRetry ? (
          <Button size="sm" variant="primary" icon="card" className="nodrag" onClick={() => void requestCard(node.id, version!.id)}>
            {card?.status === "failed" || error ? "Try again" : "Make the card"}
          </Button>
        ) : null
      }
    >
      {running ? (
        <p className="node__note">
          <span className="spinner" /> Drawing four more angles and laying out the page. This takes about a minute.
        </p>
      ) : null}
      {!card && !version ? (
        <p className="node__hint">
          <Icon name="info" size={14} /> Connect a finished image to make its card.
        </p>
      ) : null}
      {card?.status === "failed" ? <p className="node__note node__note--warn">{card.error}</p> : null}
      {error ? <p className="node__note node__note--warn">{error}</p> : null}
    </NodeCard>
  );
}
