import { useEffect } from "react";
import { toAppError } from "../../api/errors";
import { presentError } from "../../api/errorMessages";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { CardTile } from "../../lab/CardTile";
import { labApi, type LabVersion } from "../../lab/api";
import { updateVersion } from "../../lab/store";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import type { NodeViewProps } from "../types";
import type { VersionData } from "../version/types";
import { CARD_INPUTS, CARD_OUTPUTS, type CardConfig, type CardData } from "./types";

const POLL_MS = 3000;
const busy = new Set<string>(); // card node ids with a request in flight

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

/** The animal card of the connected image (one per image): the field-guide card, opened with a tap. */
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

  const onEdited = (v: LabVersion) => {
    updateVersion(v);
    if (v.card) setCard(node.id, { card: v.card });
  };
  const canRetry = Boolean(version && !readOnly && (error || card?.status === "failed" || (!card && !autoStart)));
  const shown = card && card.status !== "failed" && version ? { ...version, card } : null;
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
      media={shown ? <CardTile version={shown} onChange={onEdited} editable={!readOnly} /> : undefined}
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
          <span className="spinner" /> Drawing four more angles (about a minute). Click the card to open it.
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
