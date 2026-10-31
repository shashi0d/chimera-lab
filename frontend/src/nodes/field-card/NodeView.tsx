import { useState } from "react";
import { absoluteUrl } from "../../api/client";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { ErrorBlock, StepList, useCountdown } from "../../canvas/RunParts";
import { useNow } from "../../canvas/useNow";
import { copy } from "../../copy";
import { useGraph } from "../../graph/store";
import { useRuns } from "../../runs/store";
import { TERMINAL } from "../../runs/transport";
import type { FieldCard } from "../../types/api";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { toast } from "../../ui/toastStore";
import type { NodeViewProps } from "../types";
import { downloadBlob, renderCardPng } from "./renderPng";
import { FIELD_CARD_INPUTS, type FieldCardConfig, type FieldCardData } from "./types";
import { upstreamVersion } from "./upstream";

const t = copy.nodes.fieldCard;

function slug(s: string): string {
  return (
    s
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "") || "creature"
  );
}

function CardBody({ card, imageUrl }: { card: FieldCard; imageUrl: string }) {
  return (
    <article className="field-card" aria-label={`${t.title}: ${card.commonName}`}>
      <img className="field-card__plate" src={absoluteUrl(imageUrl)} alt={copy.nodes.result.alt(card.commonName)} draggable={false} />
      <p className="field-card__binomial">
        <i className="binomial">{card.binomial}</i> <span className="field-card__tag">{t.invented}</span>
      </p>
      <dl className="field-card__rows">
        {(
          [
            [t.habitat, card.habitat],
            [t.diet, card.diet],
            [t.size, card.size],
            [t.behaviour, card.behaviour],
          ] as const
        ).map(([k, v]) => (
          <div key={k} className="field-card__row">
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="field-card__provenance">
        <Icon name="leaf" size={12} /> {card.provenance}
      </p>
    </article>
  );
}

export function FieldCardView({ node, selected, issues }: NodeViewProps<FieldCardConfig, FieldCardData>) {
  const runId = node.data.activeRunId ?? null;
  const run = useRuns((s) => (runId ? s.runs[runId] : undefined));
  const starting = useRuns((s) => Boolean(s.starting[node.id]));
  const startError = useRuns((s) => s.startErrors[node.id]);
  const start = useRuns((s) => s.start);
  const nodes = useGraph((s) => s.nodes);
  const edges = useGraph((s) => s.edges);
  const [exporting, setExporting] = useState(false);

  const active = starting || (run !== undefined && !TERMINAL.has(run.status));
  const now = useNow(active, 500);
  const blocking = issues.filter((i) => i.severity === "block");
  const runError = run && (run.status === "failed" || run.status === "interrupted") ? run.error : null;
  const shownError = startError ?? runError ?? null;
  const write = () => void start(node.id);
  const countdown = useCountdown(shownError, write);
  const card = node.data.card ?? null;

  const up = upstreamVersion({ nodes, edges }, node.id);
  const madeFor = up.result
    ? ((up.result.data.versions as Array<{ creatureId: string }> | undefined) ?? []).findIndex((v) => v.creatureId === node.data.creatureId)
    : -1;
  const outOfDate = Boolean(card && up.version && up.version.creatureId !== node.data.creatureId);

  let status: NodeStatus;
  if (active) status = { tone: "running", label: t.writing.replace("…", "") };
  else if (shownError) status = { tone: "error", label: copy.status.failed };
  else if (outOfDate) status = { tone: "stale", label: copy.status.stale };
  else if (card) status = { tone: "ok", label: copy.status.succeeded };
  else
    status = {
      tone: "idle",
      label: blocking.length ? copy.status.idle : copy.status.ready,
    };

  const exportPng = async () => {
    if (!card || !node.data.imageUrl) return;
    setExporting(true);
    try {
      downloadBlob(await renderCardPng(card, node.data.imageUrl), `${slug(card.commonName)}-field-card.png`);
    } catch {
      toast.error(t.exportFailed);
    } finally {
      setExporting(false);
    }
  };

  const writeLabel = shownError ? t.retry : card ? (outOfDate ? t.rewriteFor(up.index + 1) : t.rewrite) : t.write;

  return (
    <NodeCard
      nodeId={node.id}
      kind="field-card"
      kicker={t.kicker}
      title={card && !active ? card.commonName : t.title}
      status={status}
      inputs={FIELD_CARD_INPUTS}
      outputs={[]}
      selected={selected}
      className={[active ? "is-running" : "", shownError ? "node--error" : "", outOfDate ? "is-stale" : ""].filter(Boolean).join(" ")}
      footer={
        <>
          <Button
            variant={card && !outOfDate && !shownError ? "secondary" : "primary"}
            size={card ? "sm" : "md"}
            icon={card ? "refresh" : "card"}
            className="nodrag"
            disabled={blocking.length > 0 || active || countdown !== null}
            busy={active}
            onClick={write}
          >
            {active ? t.writing : writeLabel}
          </Button>
          {card ? (
            <Button variant="primary" size="sm" icon="upload" className="nodrag field-card__download" busy={exporting} disabled={exporting} onClick={exportPng}>
              {t.download}
            </Button>
          ) : null}
        </>
      }
    >
      {active && run ? (
        <>
          <div className="field-card field-card--skeleton" aria-hidden="true">
            <span className="skeleton field-card__plate" />
          </div>
          <StepList steps={run.steps} now={now} />
        </>
      ) : card && node.data.imageUrl ? (
        <CardBody card={card} imageUrl={node.data.imageUrl} />
      ) : (
        <p className="node__text field-card__empty">{t.empty}</p>
      )}
      <div className="fusion-node__messages" aria-live="polite">
        {!active && blocking[0] ? (
          <p className="node__hint">
            <Icon name="info" size={14} /> {blocking[0].message}
          </p>
        ) : null}
        {outOfDate && !active ? (
          <p className="node__note node__note--warn">
            <Icon name="refresh" size={14} /> {t.outOfDate(madeFor + 1, up.index + 1)}
          </p>
        ) : null}
        {!active && shownError ? <ErrorBlock err={shownError} countdown={countdown} /> : null}
      </div>
    </NodeCard>
  );
}
