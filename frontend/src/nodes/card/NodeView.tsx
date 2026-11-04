import { useEffect, useState } from "react";
import { toAppError } from "../../api/errors";
import { presentError } from "../../api/errorMessages";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { labApi, type AnimalCard } from "../../lab/api";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import type { NodeViewProps } from "../types";
import type { VersionData } from "../version/types";
import { CARD_INPUTS, CARD_OUTPUTS, type CardConfig, type CardData } from "./types";

const busy = new Set<string>(); // node ids generating now (one request per card at a time)

async function generate(nodeId: string, versionId: string, setLoading: (v: boolean) => void): Promise<void> {
  if (busy.has(nodeId)) return;
  busy.add(nodeId);
  setLoading(true);
  const g = useGraph.getState();
  g.updateNodeData<CardData>(nodeId, (d) => ({ ...d, autoStart: false, error: null }));
  try {
    const card = await labApi.card(versionId);
    useGraph.getState().updateNodeData<CardData>(nodeId, (d) => ({ ...d, card, versionId, error: null }));
  } catch (e) {
    const p = presentError(toAppError(e));
    useGraph.getState().updateNodeData<CardData>(nodeId, (d) => ({ ...d, error: `${p.title}${p.fix ? ` ${p.fix}` : ""}` }));
  } finally {
    busy.delete(nodeId);
    setLoading(false);
  }
}

function Field({ label, value }: { label: string; value: string }) {
  return value ? (
    <div className="card-node__field">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  ) : null;
}

function List({ label, items }: { label: string; items: string[] }) {
  return items.length ? (
    <div className="card-node__field">
      <dt>{label}</dt>
      <dd>
        <ul>
          {items.map((x) => (
            <li key={x}>{x}</li>
          ))}
        </ul>
      </dd>
    </div>
  ) : null;
}

function CardBody({ card }: { card: AnimalCard }) {
  const [why, setWhy] = useState(false);
  return (
    <div className="card-node__body nodrag nowheel">
      {card.scientific_style_name ? <p className="card-node__latin">{card.scientific_style_name}</p> : null}
      {card.tagline ? <p className="card-node__tagline">{card.tagline}</p> : null}
      <dl className="card-node__fields">
        {card.inherited.map((r) => (
          <List key={r.parent} label={`From the ${r.parent}`} items={r.traits} />
        ))}
        <Field label="Appearance" value={card.appearance} />
        <Field label="Size" value={card.size} />
        <Field label="Habitat" value={card.habitat} />
        <Field label="Diet" value={card.diet} />
        <Field label="Behaviour" value={card.behaviour} />
        <List label="Abilities" items={card.abilities} />
        <List label="Weaknesses" items={card.weaknesses} />
        <Field label="Fun fact" value={card.fun_fact} />
      </dl>
      {card.reasoning ? (
        <div className="card-node__why">
          <button type="button" className="btn btn--ghost btn--sm" aria-expanded={why} onClick={() => setWhy((v) => !v)}>
            {why ? "Hide the model's reasoning" : "Why this card?"}
          </button>
          {why ? <p className="card-node__reasoning">{card.reasoning}</p> : null}
        </div>
      ) : null}
    </div>
  );
}

/** The animal card of the connected image: name, traits from each parent, habitat, diet, abilities, reasoning. */
export function CardView({ node, selected }: NodeViewProps<CardConfig, CardData>) {
  const { card, versionId, autoStart, error } = node.data;
  const readOnly = useGraph((s) => s.readOnly);
  const parent = useGraph((s) => upstreamNode(s, node.id, "in"));
  const version = parent?.type === "version" ? (parent.data as VersionData).version : null;
  const [loading, setLoading] = useState(() => busy.has(node.id));
  const outdated = Boolean(card && version && versionId !== version.id);

  useEffect(() => {
    if (autoStart && version && !readOnly && !card) void generate(node.id, version.id, setLoading);
  }, [autoStart, version, readOnly, card, node.id]);

  let status: NodeStatus | undefined;
  if (loading) status = { tone: "running", label: "Writing" };
  else if (error) status = { tone: "error", label: "Failed" };
  else if (card && !outdated) status = { tone: "ok", label: "Ready" };

  const action = version && !readOnly && !loading ? (
    <Button size="sm" variant={card ? "ghost" : "primary"} icon="card" className="nodrag" onClick={() => void generate(node.id, version.id, setLoading)}>
      {card ? (outdated ? "Write for this image" : "Write again") : "Write the card"}
    </Button>
  ) : null;

  return (
    <NodeCard
      nodeId={node.id}
      kind="card"
      kicker="Animal card"
      title={card?.name || "Animal card"}
      status={status}
      inputs={CARD_INPUTS}
      outputs={CARD_OUTPUTS}
      selected={selected}
      className={loading ? "is-running" : ""}
      footer={action}
    >
      {card ? <CardBody card={card} /> : null}
      {!card && loading ? <p className="node__note"><span className="spinner" /> Reading the image and how it was made…</p> : null}
      {!card && !loading && !version ? (
        <p className="node__hint">
          <Icon name="info" size={14} /> Connect a finished image to write its card.
        </p>
      ) : null}
      {outdated ? (
        <p className="node__hint node__hint--warn">
          <Icon name="info" size={14} /> This card describes a different image.
        </p>
      ) : null}
      {error ? <p className="node__note node__note--warn">{error}</p> : null}
    </NodeCard>
  );
}
