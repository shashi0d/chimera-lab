import { useState } from "react";
import { navigate } from "../../app/route";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { copy } from "../../copy";
import { useCreature } from "../../evo/data";
import { evo } from "../../evo/index";
import { isTerminal, useRun } from "../../evo/runs";
import { useGraph } from "../../graph/store";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Pill } from "../../ui/Pill";
import { SegmentedTabs } from "../../ui/SegmentedTabs";
import type { FusionData } from "../fusion/types";
import { useFusionStart } from "../fusion/start";
import type { NodeViewProps } from "../types";
import { RESULT_INPUTS, RESULT_OUTPUTS, type ResultConfig, type ResultData } from "./types";

const t = copy.nodes.result;
/** Images already revealed this session: the develop effect plays once per version. */
const developed = new Set<string>();

/** The upstream Fusion node's latest run, as the Result node needs it. */
function useUpstreamRun(nodeId: string) {
  const fusionId = useGraph((s) => s.edges.find((e) => e.target === nodeId && e.targetPort === "in")?.source);
  const runId = useGraph((s) => (fusionId ? (s.nodes.find((n) => n.id === fusionId)?.data as FusionData | undefined)?.activeRunId : null));
  const starting = useFusionStart((s) => (fusionId ? Boolean(s.starting[fusionId]) : false));
  const run = useRun(runId);
  const active = starting || Boolean(run && !isTerminal(run.status));
  return { run, active };
}

function Plate({ url, runId, name }: { url: string; runId: string; name: string }) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(developed.has(runId));
  const base = evo().imageUrl(url);
  const src = base + (attempt ? `${base.includes("?") ? "&" : "?"}retry=${attempt}` : "");
  if (failed) {
    return (
      <div className="plate plate--failed" role="alert">
        <Icon name="image" size={28} />
        <p>{t.imageFailed}</p>
        <Button
          size="sm"
          icon="refresh"
          className="nodrag"
          onClick={() => {
            setFailed(false);
            setAttempt((a) => a + 1);
          }}
        >
          {t.reloadImage}
        </Button>
      </div>
    );
  }
  return (
    <figure className="plate">
      <div className="plate__frame">
        <img
          key={src}
          className={`plate__img${loaded ? " is-loaded" : ""}`}
          src={src}
          alt={t.alt(name)}
          draggable={false}
          onLoad={() => {
            developed.add(runId);
            setLoaded(true);
          }}
          onError={() => setFailed(true)}
        />
      </div>
    </figure>
  );
}

export function ResultView({ node, selected }: NodeViewProps<ResultConfig, ResultData>) {
  const { versions, selected: sel } = node.data;
  const { run, active } = useUpstreamRun(node.id);
  const update = useGraph((s) => s.updateNodeData);
  const idx = Math.min(Math.max(0, sel), versions.length - 1);
  const version = versions[idx];
  const creature = useCreature(version?.creatureId);
  const name = version?.title || t.untitledTitle;
  const failed = run && (run.status === "failed" || run.status === "interrupted");
  const latest = run?.images[run.images.length - 1];

  let status: NodeStatus | undefined;
  if (active) status = { tone: "running", label: t.generating.replace("…", "") };
  else if (node.data.stale && version) status = { tone: "stale", label: copy.status.stale };
  else if (version) status = { tone: "ok", label: copy.status.succeeded };

  const media = version ? (
    <div className="result-node__stage">
      <Plate url={version.imageUrl} runId={version.runId} name={name} />
      {active ? (
        <div className="plate__overlay" aria-hidden="true">
          <span className="skeleton skeleton--fill" />
          <span className="plate__overlay-label">{t.generating}</span>
        </div>
      ) : null}
    </div>
  ) : active && latest ? (
    // While the agent works, its latest attempt stands in for the hero, clearly marked as work in progress.
    <figure className="plate plate--wip">
      <div className="plate__frame">
        <img className="plate__img is-loaded" src={evo().imageUrl(latest.url)} alt={copy.trace.imageAlt(latest.imageId)} draggable={false} />
      </div>
      <figcaption className="plate__overlay-label plate__wip-label">{t.latest(latest.imageId)}</figcaption>
    </figure>
  ) : active ? (
    <div className="plate plate--skeleton" aria-label={t.generating}>
      <span className="skeleton skeleton--fill" />
      <span className="plate__overlay-label">{t.generating}</span>
    </div>
  ) : (
    <div className={`plate plate--empty${failed ? " is-muted" : ""}`}>
      <Icon name="result" size={28} />
      <p>{failed ? t.noImageYet : t.waiting}</p>
    </div>
  );

  const cardRoute = version ? ({ view: "creature", creatureId: version.creatureId } as const) : null;

  return (
    <NodeCard
      nodeId={node.id}
      kind="result"
      kicker={version ? t.kicker(idx + 1) : t.title}
      title={version ? name : t.title}
      status={status}
      inputs={RESULT_INPUTS}
      outputs={RESULT_OUTPUTS}
      media={media}
      selected={selected}
      className={[active ? "is-generating" : "", node.data.stale ? "is-stale" : "", version ? "" : "node--result-empty"].filter(Boolean).join(" ")}
    >
      {version && cardRoute ? (
        <>
          <div className="result-node__pills">
            <Pill tone="brand">
              <Icon name="leaf" size={12} /> {t.generated}
            </Pill>
            {creature.data?.realHybrid ? (
              <Pill tone="info" className="badge--hybrid">
                <span className="pill__diamond" aria-hidden="true" /> {t.realHybrid}
              </Pill>
            ) : null}
          </div>
          {creature.data ? <p className="result-node__live">{creature.data.canItLive.summary}</p> : null}
          <div className="result-node__bar">
            {versions.length > 1 ? (
              <SegmentedTabs
                label={t.versions}
                value={String(idx)}
                onChange={(v) => update<ResultData>(node.id, (d) => ({ ...d, selected: Number(v) }))}
                items={versions.map((_, i) => ({ value: String(i), label: `v${i + 1}`, ariaLabel: t.versionAria(i + 1, versions.length) }))}
              />
            ) : (
              <span className="result-node__single">v1</span>
            )}
            <Button
              size="sm"
              variant="secondary"
              icon="card"
              className="nodrag"
              onClick={() => navigate(cardRoute)}
            >
              {t.openCard}
            </Button>
          </div>
        </>
      ) : null}
    </NodeCard>
  );
}
