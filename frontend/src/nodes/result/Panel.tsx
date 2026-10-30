import { useState } from "react";
import { copy } from "../../copy";
import type { AnimalMatch, ParentInfo } from "../../types/api";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import type { NodePanelProps } from "../types";
import { displayName, type ResultConfig, type ResultData } from "./types";

const t = copy.panel;
const DONOR_KEYS = ["head", "body", "limbs", "covering", "tail"] as const;

function Parent({ p }: { p: ParentInfo }) {
  const r = p.reading;
  const m: AnimalMatch | null = p.match;
  return (
    <li className="parent">
      <span className="parent__slot" aria-label={`Input ${p.slot}`}>
        {p.slot}
      </span>
      <div className="parent__body">
        <p className="parent__name">
          {m?.commonName ?? r.commonName ?? "Unknown animal"}{" "}
          {m?.scientificName ?? r.scientificName ? <i className="binomial">{m?.scientificName ?? r.scientificName}</i> : null}
        </p>
        <p className="parent__meta">
          <span>{t.confidence(r.confidence)}</span>
          <span className={m ? "parent__match" : "parent__unmatched"}>{m ? t.matched(m.tier) : t.unmatched}</span>
        </p>
        {r.visibleParts.length ? (
          <p className="parent__parts">
            {t.visibleParts}: {r.visibleParts.join(", ")}
          </p>
        ) : null}
      </div>
    </li>
  );
}

export function ResultPanel({ node }: NodePanelProps<ResultConfig, ResultData>) {
  const [copied, setCopied] = useState(false);
  const { versions, selected } = node.data;
  const v = versions[Math.min(selected, versions.length - 1)];
  if (!v) return null;
  const spec = v.spec;
  const facts = spec.realHybrid ? Object.entries(spec.realHybrid.facts) : [];

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(spec.prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked: the prompt is still selectable */
    }
  };

  return (
    <div className="panel-body">
      <p className="panel__subtitle">
        <span className="panel__name">{displayName(spec)}</span>
        <span className="panel__version">{copy.nodes.result.version(selected + 1, versions.length)}</span>
      </p>
      <p className="panel__generated">
        <Icon name="leaf" size={14} /> {copy.nodes.result.generated}
      </p>

      <section className="panel__section" aria-labelledby="pn-parents">
        <h3 id="pn-parents" className="panel__heading">
          {t.parents}
        </h3>
        <ul className="parents">
          {spec.parents.map((p) => (
            <Parent key={p.slot} p={p} />
          ))}
        </ul>
      </section>

      <section className="panel__section" aria-labelledby="pn-hybrid">
        <h3 id="pn-hybrid" className="panel__heading">
          {t.realHybrid}
        </h3>
        {spec.realHybrid ? (
          <div className="hybrid-card">
            <p className="hybrid-card__name">
              <span className="badge__diamond" aria-hidden="true" /> {spec.realHybrid.name}
            </p>
            <dl className="kv">
              {facts.map(([k, val]) => (
                <div key={k} className="kv__row">
                  <dt>{k.replace(/_/g, " ")}</dt>
                  <dd>{val.split("|").join(" · ")}</dd>
                </div>
              ))}
            </dl>
            <p className="panel__fine">{t.realHybridNote}</p>
          </div>
        ) : (
          <p className="panel__muted">{t.noHybrid}</p>
        )}
      </section>

      <section className="panel__section" aria-labelledby="pn-plan">
        <h3 id="pn-plan" className="panel__heading">
          {t.plan}
        </h3>
        <p className="panel__plan">{spec.bodyPlan}</p>
        <ul className="donors">
          {DONOR_KEYS.map((k) => (
            <li key={k} className={`donor donor--${spec.partDonors[k].toLowerCase()}`}>
              <span className="donor__part">{t.donors[k]}</span>
              <span className="donor__from">{spec.partDonors[k]}</span>
            </li>
          ))}
        </ul>
        {spec.rationale ? (
          <p className="panel__text">
            <span className="panel__label">{t.rationale}: </span>
            {spec.rationale}
          </p>
        ) : null}
      </section>

      <section className="panel__section" aria-labelledby="pn-notes">
        <h3 id="pn-notes" className="panel__heading">
          {t.notes}
        </h3>
        {spec.warnings.length ? (
          <ul className="notes">
            {spec.warnings.map((w) => (
              <li key={w.ruleId} className={`note note--${w.severity}`}>
                <Icon name={w.severity === "warning" ? "alert" : "info"} size={14} />
                <span className="note__id">{w.ruleId}</span>
                <span className="note__text">{w.message}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="panel__muted">{t.noNotes}</p>
        )}
      </section>

      <section className="panel__section" aria-labelledby="pn-prompt">
        <div className="panel__heading-row">
          <h3 id="pn-prompt" className="panel__heading">
            {t.prompt}
          </h3>
          <Button size="sm" variant="ghost" icon={copied ? "check" : "copy"} onClick={copyPrompt}>
            {copied ? t.copied : t.copy}
          </Button>
        </div>
        <pre className="prompt-block" tabIndex={0}>
          {spec.prompt}
        </pre>
      </section>

      <section className="panel__section" aria-labelledby="pn-models">
        <h3 id="pn-models" className="panel__heading">
          {t.models}
        </h3>
        <p className="panel__mono">
          {spec.model.vision} · {spec.model.image}
        </p>
      </section>
    </div>
  );
}
