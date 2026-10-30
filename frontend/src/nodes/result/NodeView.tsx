import { useState } from "react";
import { absoluteUrl } from "../../api/client";
import { NodeCard, type NodeStatus } from "../../canvas/NodeCard";
import { copy } from "../../copy";
import { useGraph } from "../../graph/store";
import { useRuns } from "../../runs/store";
import { TERMINAL } from "../../runs/transport";
import { Button, IconButton } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { useUi } from "../../ui/uiStore";
import type { FusionData } from "../fusion/types";
import type { NodeViewProps } from "../types";
import { displayName, RESULT_INPUTS, type ResultConfig, type ResultData } from "./types";

const t = copy.nodes.result;
/** Images already revealed this session: the develop effect plays once per version. */
const developed = new Set<string>();

function useUpstreamRunActive(nodeId: string): boolean {
  const fusionId = useGraph((s) => s.edges.find((e) => e.target === nodeId && e.targetPort === "in")?.source);
  const runId = useGraph((s) => (fusionId ? (s.nodes.find((n) => n.id === fusionId)?.data as FusionData | undefined)?.activeRunId : null));
  const starting = useRuns((s) => (fusionId ? Boolean(s.starting[fusionId]) : false));
  const status = useRuns((s) => (runId ? s.runs[runId]?.status : undefined));
  return starting || (status !== undefined && !TERMINAL.has(status));
}

function Plate({ url, runId, plateNo, name }: { url: string; runId: string; plateNo: number; name: string }) {
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
      <figcaption className="plate__caption">
        <span className="plate__no">{t.plate(plateNo)}</span>
        <span className="plate__generated">
          <Icon name="leaf" size={12} /> {t.generated}
        </span>
      </figcaption>
    </figure>
  );
}

export function ResultView({ node, selected, catalog }: NodeViewProps<ResultConfig, ResultData>) {
  const { versions, selected: sel } = node.data;
  const active = useUpstreamRunActive(node.id);
  const openPanel = useUi((s) => s.openPanel);
  const update = useGraph((s) => s.updateNodeData);
  const idx = Math.min(Math.max(0, sel), versions.length - 1);
  const version = versions[idx];
  const spec = version?.spec;
  const warnCount = spec ? spec.warnings.filter((w) => w.severity === "warning").length : 0;
  const name = spec ? displayName(spec) : "";

  let status: NodeStatus | undefined;
  if (active) status = { tone: "running", label: t.generating.replace("…", "") };
  else if (node.data.stale && version) status = { tone: "stale", label: copy.status.stale };
  else if (warnCount) status = { tone: "warn", label: t.warnings(warnCount) };
  else if (version) status = { tone: "ok", label: copy.status.succeeded };

  const go = (delta: number) => update<ResultData>(node.id, (d) => ({ ...d, selected: Math.min(d.versions.length - 1, Math.max(0, d.selected + delta)) }));

  return (
    <NodeCard
      nodeId={node.id}
      kind="result"
      catalog={catalog}
      title={t.title}
      icon="result"
      status={status}
      inputs={RESULT_INPUTS}
      outputs={[]}
      selected={selected}
      className={[active ? "is-generating" : "", node.data.stale ? "is-stale" : ""].filter(Boolean).join(" ")}
    >
      {version ? (
        <div className="result-node__stage">
          <Plate url={version.imageUrl} runId={version.runId} plateNo={idx + 1} name={name} />
          {active ? (
            <div className="plate__overlay" aria-hidden="true">
              <span className="skeleton skeleton--plate" />
              <span className="plate__overlay-label">{t.generating}</span>
            </div>
          ) : null}
        </div>
      ) : active ? (
        <div className="plate plate--skeleton" aria-label={t.generating}>
          <span className="skeleton skeleton--plate" />
          <span className="plate__overlay-label">{t.generating}</span>
        </div>
      ) : (
        <div className="plate plate--empty">
          <Icon name="result" size={28} />
          <p>{t.waiting}</p>
        </div>
      )}
      {version && spec ? (
        <>
          <h4 className="result-node__name">{name}</h4>
          <div className="result-node__badges">
            {spec.realHybrid ? (
              <span className="badge badge--hybrid">
                <span className="badge__diamond" aria-hidden="true" /> {t.realHybrid}: {spec.realHybrid.name}
              </span>
            ) : null}
            {warnCount ? (
              <span className="badge badge--warn">
                <Icon name="alert" size={12} /> {t.warnings(warnCount)}
              </span>
            ) : null}
          </div>
          <div className="result-node__bar">
            {versions.length > 1 ? (
              <div className="version-switch" role="group" aria-label={t.version(idx + 1, versions.length)}>
                <IconButton icon="left" label={t.prev} className="nodrag" disabled={idx === 0} onClick={() => go(-1)} />
                <span className="version-switch__label" aria-live="polite">
                  v{idx + 1}
                  <span className="version-switch__of"> / {versions.length}</span>
                </span>
                <IconButton icon="right" label={t.next} className="nodrag" disabled={idx === versions.length - 1} onClick={() => go(1)} />
              </div>
            ) : (
              <span className="version-switch__single">v1</span>
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
