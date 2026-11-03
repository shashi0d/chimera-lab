import { Background, BackgroundVariant, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import { useEffect, useMemo, useState } from "react";
import { toAppError, type AppError } from "../api/errors";
import { hrefFor, linkHandler, navigate } from "../app/route";
import { ErrorBlock } from "../canvas/RunParts";
import { copy } from "../copy";
import { evo } from "../evo/index";
import type { Parent, Publication, PublicationStep } from "../evo/types";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { Pill } from "../ui/Pill";
import { useUi } from "../ui/uiStore";

const OPERATION: Record<string, string> = { fusion: "Fusion", revise: "Revise", paint: "Paint" };

type AnimalData = { kind: "animal"; slot: "A" | "B"; parent: Parent | null };
type FusionStepData = { kind: "fusion"; mode: string | null };
type ImageData = { kind: "image"; step: PublicationStep; n: number; final: boolean };
type ProcessData = (AnimalData | FusionStepData | ImageData) & Record<string, unknown>;

function ProcessNode({ data }: NodeProps<Node<ProcessData>>) {
  const d = data as ProcessData;
  if (d.kind === "animal") {
    return (
      <div className="pnode pnode--animal">
        <p className="node__kicker">Animal {d.slot}</p>
        <p className="pnode__title">{d.parent?.commonName ?? "Animal"}</p>
        {d.parent?.scientificName ? <p className="binomial">{d.parent.scientificName}</p> : null}
        <Handle type="source" position={Position.Right} isConnectable={false} />
      </div>
    );
  }
  if (d.kind === "fusion") {
    return (
      <div className="pnode pnode--fusion">
        <Handle type="target" position={Position.Left} isConnectable={false} />
        <Icon name="fusion" size={20} />
        <p className="node__kicker">Fusion agent</p>
        <p className="pnode__title">{d.mode ? copy.modes[d.mode as keyof typeof copy.modes]?.label ?? d.mode : "Fusion"}</p>
        <Handle type="source" position={Position.Right} isConnectable={false} />
      </div>
    );
  }
  const { step, n, final } = d;
  return (
    <figure className={`pnode pnode--image${final ? " is-final" : ""}`}>
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <img src={evo().imageUrl(step.imageUrl)} alt={`Version ${n}`} draggable={false} />
      <figcaption>
        <p className="node__kicker">
          V{n} · {OPERATION[step.operation]}
          {final ? " · final" : ""}
        </p>
        {step.operation !== "fusion" ? <p className="pnode__instruction">{step.instruction}</p> : null}
      </figcaption>
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </figure>
  );
}

const nodeTypes = { process: ProcessNode };

function layout(p: Publication): { nodes: Node<ProcessData>[]; edges: Edge[] } {
  const nodes: Node<ProcessData>[] = [
    { id: "a", type: "process", position: { x: 0, y: 40 }, data: { kind: "animal", slot: "A", parent: p.sire } },
    { id: "b", type: "process", position: { x: 0, y: 260 }, data: { kind: "animal", slot: "B", parent: p.dam } },
    { id: "fusion", type: "process", position: { x: 300, y: 150 }, data: { kind: "fusion", mode: p.mode } },
  ];
  const edges: Edge[] = [
    { id: "a-f", source: "a", target: "fusion", type: "smoothstep" },
    { id: "b-f", source: "b", target: "fusion", type: "smoothstep" },
  ];
  let prev = "fusion";
  p.steps.forEach((step, i) => {
    const id = `v${i + 1}`;
    nodes.push({ id, type: "process", position: { x: 580 + i * 340, y: 40 }, data: { kind: "image", step, n: i + 1, final: i === p.steps.length - 1 } });
    edges.push({ id: `${prev}-${id}`, source: prev, target: id, type: "smoothstep", label: step.operation === "fusion" ? undefined : OPERATION[step.operation] });
    prev = id;
  });
  return { nodes, edges };
}

/** A published creation: its final image and the whole path that made it, laid out like the Lab canvas. */
export function CreationPage({ publicationId }: { publicationId: string }) {
  const [pub, setPub] = useState<Publication | null>(null);
  const [error, setError] = useState<AppError | null>(null);
  const theme = useUi((s) => s.theme);

  useEffect(() => {
    let alive = true;
    setPub(null);
    setError(null);
    evo()
      .getPublication(publicationId)
      .then((p) => alive && setPub(p))
      .catch((e) => alive && setError(toAppError(e)));
    return () => {
      alive = false;
    };
  }, [publicationId]);

  const flow = useMemo(() => (pub ? layout(pub) : null), [pub]);

  if (error) {
    return (
      <div className="page page--creation">
        <ErrorBlock err={error} />
        <Button onClick={() => navigate({ view: "gallery" })}>Back to the gallery</Button>
      </div>
    );
  }
  if (!pub || !flow) {
    return (
      <div className="page page--creation" aria-busy="true">
        <span className="spinner" aria-label="Loading the creation" />
      </div>
    );
  }
  const edits = pub.steps.length - 1;
  return (
    <div className="page page--creation">
      <a className="back-link" href={hrefFor({ view: "gallery" })} onClick={linkHandler({ view: "gallery" })}>
        <Icon name="left" size={16} /> Gallery
      </a>
      <header className="creation__head">
        <div>
          <p className="hero__kicker">Lab creation · {new Date(pub.createdAt).toLocaleDateString()}</p>
          <h1 className="hero__title">{pub.title}</h1>
          <p className="creation__parents">
            {pub.sire?.commonName ?? "Animal A"} × {pub.dam?.commonName ?? "Animal B"}
            {pub.mode ? ` · ${copy.modes[pub.mode]?.label ?? pub.mode}` : ""}
          </p>
          <div className="creation__pills">
            <Pill tone="brand">
              <Icon name="leaf" size={12} /> {copy.labels.generated}
            </Pill>
            <Pill tone="info">{edits === 0 ? "The agent's image, unedited" : `${edits} ${edits === 1 ? "edit" : "edits"} after the agent's image`}</Pill>
          </div>
        </div>
        <div className="creation__actions">
          {pub.sourceCreatureId ? (
            <a className="btn btn--secondary" href={hrefFor({ view: "creature", creatureId: pub.sourceCreatureId })} onClick={linkHandler({ view: "creature", creatureId: pub.sourceCreatureId })}>
              How the agent made V1
            </a>
          ) : null}
          <Button variant="primary" icon="fusion" onClick={() => navigate({ view: "lab", runId: null })}>
            Make your own
          </Button>
        </div>
      </header>

      <figure className="creation__final">
        <img src={evo().imageUrl(pub.imageUrl)} alt={copy.labels.alt(pub.title)} />
      </figure>

      <section className="creation__process" aria-labelledby="process-title">
        <h2 id="process-title">The path</h2>
        <div className="creation__canvas" aria-hidden="true">
          <ReactFlow
            nodes={flow.nodes}
            edges={flow.edges}
            nodeTypes={nodeTypes}
            colorMode={theme}
            fitView
            fitViewOptions={{ padding: 0.15, maxZoom: 1 }}
            minZoom={0.2}
            maxZoom={1.5}
            nodesDraggable={false}
            nodesConnectable={false}
            elementsSelectable={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={28} size={1.6} className="canvas__grid" />
          </ReactFlow>
        </div>
        <ol className="creation__steps">
          <li>
            <strong>Animals:</strong> {pub.sire?.commonName ?? "A"} and {pub.dam?.commonName ?? "B"}
          </li>
          {pub.steps.map((s, i) => (
            <li key={s.versionId}>
              <strong>
                V{i + 1} · {OPERATION[s.operation]}:
              </strong>{" "}
              {s.operation === "fusion" ? "the agent's image" : s.instruction}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
