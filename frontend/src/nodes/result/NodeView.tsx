import { useState } from "react";
import { absoluteUrl } from "../../api/client";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { copy } from "../../copy";
import { useGraph } from "../../graph/store";
import { useRuns } from "../../runs/store";
import { TERMINAL } from "../../runs/transport";
import { Button, IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Pill } from "../../ui/Pill";
import { SegmentedTabs } from "../../ui/SegmentedTabs";
import { useUi } from "../../ui/uiStore";
import type { FusionData } from "../fusion/types";
import type { NodeViewProps } from "../types";
import { findFreeSpot } from "../../canvas/addImages";
import { createNode } from "../registry";
import { displayName, RESULT_INPUTS, RESULT_OUTPUTS, type ResultConfig, type ResultData } from "./types";

const t = copy.nodes.result;
/** Images already revealed this session: the develop effect plays once per version. */
const developed = new Set<string>();

function useUpstreamRunStatus(nodeId: string): string | undefined {
  const fusionId = useGraph((s) => s.edges.find((e) => e.target === nodeId && e.targetPort === "in")?.source);
  const runId = useGraph((s) => (fusionId ? (s.nodes.find((n) => n.id === fusionId)?.data as FusionData | undefined)?.activeRunId : null));
  return useRuns((s) => (runId ? s.runs[runId]?.status : undefined));
}

function useUpstreamRunActive(nodeId: string): boolean {
  const fusionId = useGraph((s) => s.edges.find((e) => e.target === nodeId && e.targetPort === "in")?.source);
  const runId = useGraph((s) => (fusionId ? (s.nodes.find((n) => n.id === fusionId)?.data as FusionData | undefined)?.activeRunId : null));
  const starting = useRuns((s) => (fusionId ? Boolean(s.starting[fusionId]) : false));
  const status = useRuns((s) => (runId ? s.runs[runId]?.status : undefined));
  return starting || (status !== undefined && !TERMINAL.has(status));
}

function Plate({ url, runId, name }: { url: string; runId: string; name: string }) {
  const [attempt, setAttempt] = useState(0);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(developed.has(runId));
  const src = absoluteUrl(url) + (attempt ? `${url.includes("?") ? "&" : "?"}retry=${attempt}` : "");
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

/** F2: add a Field card wired to this Result (or select the existing one). */
function makeFieldCard(resultId: string): void {
  const g = useGraph.getState();
  const existing = g.edges.find((e) => e.source === resultId && g.nodes.find((n) => n.id === e.target)?.type === "field-card");
  if (existing) {
    g.setSelection([existing.target]);
    return;
  }
  const res = g.nodes.find((n) => n.id === resultId);
  const pos = findFreeSpot({ x: (res?.position.x ?? 0) + 580, y: res?.position.y ?? 0 }, 340, 620);
  const card = createNode("field-card", pos);
  g.addNodes(
    [card],
    [
      {
        id: `e-${card.id}`,
        source: resultId,
        sourcePort: "out",
        target: card.id,
        targetPort: "in",
      },
    ],
  );
  g.setSelection([card.id]);
}

export function ResultView({ node, selected }: NodeViewProps<ResultConfig, ResultData>) {
  const { versions, selected: sel } = node.data;
  const active = useUpstreamRunActive(node.id);
  const upstream = useUpstreamRunStatus(node.id);
  const openPanel = useUi((s) => s.openPanel);
  const update = useGraph((s) => s.updateNodeData);
  const readOnly = useGraph((s) => s.readOnly);
  const idx = Math.min(Math.max(0, sel), versions.length - 1);
  const version = versions[idx];
  const spec = version?.spec;
  const warnCount = spec ? (spec.warnings ?? []).filter((w) => w.severity === "warning").length : 0;
  const name = spec ? displayName(spec) : "";

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
  ) : active ? (
    <div className="plate plate--skeleton" aria-label={t.generating}>
      <span className="skeleton skeleton--fill" />
      <span className="plate__overlay-label">{t.generating}</span>
    </div>
  ) : (
    <div className={`plate plate--empty${upstream === "failed" || upstream === "interrupted" ? " is-muted" : ""}`}>
      <Icon name="result" size={28} />
      <p>{upstream === "failed" || upstream === "interrupted" ? t.noImageYet : t.waiting}</p>
    </div>
  );

  return (
    <NodeCard
      nodeId={node.id}
      kind="result"
      kicker={version ? t.kicker(idx + 1) : t.title}
      title={version ? name || t.untitledTitle : t.title}
      status={status}
      inputs={RESULT_INPUTS}
      outputs={RESULT_OUTPUTS}
      media={media}
      toolbar={version && !readOnly ? <IconButton icon="card" label={t.makeCard} onClick={() => makeFieldCard(node.id)} /> : null}
      selected={selected}
      className={[active ? "is-generating" : "", node.data.stale ? "is-stale" : "", version ? "" : "node--result-empty"].filter(Boolean).join(" ")}
    >
      {version && spec ? (
        <>
          <div className="result-node__pills">
            <Pill tone="indigo">
              <Icon name="leaf" size={12} /> {t.generated}
            </Pill>
            {spec.realHybrid ? (
              <Pill tone="info" className="badge--hybrid">
                <span className="pill__diamond" aria-hidden="true" /> {t.realHybrid}: {spec.realHybrid.name}
              </Pill>
            ) : null}
            {warnCount ? (
              <Pill tone="warning" className="badge--warn">
                <Icon name="alert" size={12} /> {t.warnings(warnCount)}
              </Pill>
            ) : null}
          </div>
          <div className="result-node__bar">
            {versions.length > 1 ? (
              <SegmentedTabs
                label={t.versions}
                value={String(idx)}
                onChange={(v) =>
                  update<ResultData>(node.id, (d) => ({
                    ...d,
                    selected: Number(v),
                  }))
                }
                items={versions.map((_, i) => ({
                  value: String(i),
                  label: `v${i + 1}`,
                  ariaLabel: t.versionAria(i + 1, versions.length),
                }))}
              />
            ) : (
              <span className="result-node__single">v1</span>
            )}
            <Button size="sm" variant="secondary" icon="info" className="nodrag" onClick={() => openPanel(node.id)}>
              {t.howMade}
            </Button>
          </div>
        </>
      ) : null}
    </NodeCard>
  );
}
