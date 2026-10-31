import { useState } from "react";
import { stepDuration, totalMs } from "../../canvas/RunParts";
import { formatSeconds } from "../../canvas/useNow";
import { copy } from "../../copy";
import { useRuns } from "../../runs/store";
import type { AnimalMatch, ParentInfo, RealHybrid } from "../../types/api";
import { Button } from "../../ui/Button";
import { Icon } from "../../ui/Icon";
import { Pill } from "../../ui/Pill";
import { Section } from "../../ui/Section";
import { StatCard } from "../../ui/StatCard";
import { Timeline } from "../../ui/Timeline";
import { PARTS } from "../fusion/types";
import { parentName } from "../image-input/species";
import type { NodePanelProps } from "../types";
import { summarize } from "./summary";
import { displayName, type ResultConfig, type ResultData } from "./types";

const t = copy.panel;

function Parent({ p }: { p: ParentInfo }) {
  const r = p.reading;
  const m: AnimalMatch | null = p.match;
  return (
    <li className="parent">
      <span className={`parent__slot parent__slot--${p.slot.toLowerCase()}`} aria-label={`Input ${p.slot}`}>
        {p.slot}
      </span>
      <div className="parent__body">
        <p className="parent__name">
          {parentName(p) ?? "Unknown animal"}{" "}
          {(m?.scientificName ?? r.scientificName) ? <i className="binomial">{m?.scientificName ?? r.scientificName}</i> : null}
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

const piped = (v: string | null | undefined) => (v ? v.split("|").join(" · ") : null);

function Hybrid({ h }: { h: RealHybrid }) {
  const source = h.facts.source_url;
  const cross = piped(h.cross ?? h.facts.cross);
  const fertility = piped(h.fertility ?? h.facts.fertility);
  return (
    <li className="hybrid">
      <p className="hybrid__name">
        <span className="pill__diamond" aria-hidden="true" /> {h.name}
        {h.confidence ? <Pill tone="info">{h.confidence.replace(/_/g, " ")}</Pill> : null}
      </p>
      <dl className="kv">
        {cross ? (
          <div className="kv__row">
            <dt>{t.cross}</dt>
            <dd>{cross}</dd>
          </div>
        ) : null}
        {fertility ? (
          <div className="kv__row">
            <dt>{t.fertility}</dt>
            <dd>{fertility}</dd>
          </div>
        ) : null}
      </dl>
      {source ? (
        <a className="source-link" href={source} target="_blank" rel="noreferrer noopener">
          {t.source}: {source.replace(/^https?:\/\//, "")}
        </a>
      ) : null}
    </li>
  );
}

export function ResultPanel({ node }: NodePanelProps<ResultConfig, ResultData>) {
  const [copied, setCopied] = useState(false);
  const { versions, selected } = node.data;
  const v = versions[Math.min(selected, versions.length - 1)];
  const run = useRuns((s) => (v ? s.runs[v.runId] : undefined));
  if (!v) return null;
  const spec = v.spec;
  const hybrids = spec.realHybrids?.length ? spec.realHybrids : spec.realHybrid ? [spec.realHybrid] : [];
  const warnings = spec.warnings.filter((w) => w.severity === "warning");
  const infos = spec.warnings.length - warnings.length;
  const rules = spec.rulesSummary ?? {};
  const tokens = run?.usage?.tokens;
  const steps = run?.steps ?? [];
  const now = Date.now();
  const sources = [...new Set([...hybrids.map((h) => h.facts.source_url), ...(spec.mythology ?? []).map((m) => m.sourceUrl)].filter(Boolean))] as string[];

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
      <div className="panel__lead">
        <p className="panel__subtitle">
          <span className="panel__name">{displayName(spec)}</span>
          <span className="panel__version">{copy.nodes.result.version(selected + 1, versions.length)}</span>
        </p>
        <Pill tone="indigo">
          <Icon name="leaf" size={12} /> {copy.nodes.result.generated}
        </Pill>
        <div className="panel__summary">
          {summarize(spec).map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      </div>

      <div className="stats" role="group" aria-label="Key numbers">
        {spec.parents.map((p) => (
          <StatCard
            key={p.slot}
            kicker={t.statMatch(p.slot)}
            value={`${Math.round(p.reading.confidence * 100)}%`}
            meta={p.match ? t.tierMeta(parentName(p) ?? p.slot, p.match.tier) : t.notInData}
            tone={p.match ? "success" : "warning"}
          />
        ))}
        <StatCard kicker={t.statRules} value={rules.run ?? null} meta={rules.total !== undefined ? t.statRulesMeta(rules.total) : undefined} />
        <StatCard kicker={t.statWarnings} value={warnings.length} meta={t.statWarningsMeta(infos)} tone={warnings.length ? "warning" : "success"} />
        <StatCard
          kicker={t.statTokens}
          value={tokens !== undefined ? tokens.toLocaleString("en-US") : null}
          meta={tokens !== undefined ? t.statTokensMeta : t.statTokensUnknown}
        />
      </div>

      <Section title={t.pipeline} count={steps.length ? copy.nodes.fusion.summary(steps.length, formatSeconds(totalMs(steps))) : undefined}>
        {steps.length ? (
          <Timeline
            label={t.pipeline}
            items={steps.map((s) => ({
              key: s.key,
              label: s.label,
              status: s.status,
              statusText: copy.steps[s.status],
              duration: stepDuration(s, now),
              detail: s.detail ?? undefined,
            }))}
          />
        ) : (
          <p className="panel__muted">{t.pipelineMissing}</p>
        )}
      </Section>

      <Section title={t.realHybrids} count={hybrids.length}>
        {hybrids.length ? (
          <>
            <ul className="hybrids">
              {hybrids.map((h) => (
                <Hybrid key={h.hybridId} h={h} />
              ))}
            </ul>
            <p className="panel__fine">{t.realHybridNote}</p>
          </>
        ) : (
          <p className="panel__muted">{t.noHybrid}</p>
        )}
      </Section>

      <Section title={t.rules} count={spec.warnings.length}>
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
      </Section>

      <Section title={t.mythology} count={spec.mythology?.length ?? 0}>
        {spec.mythology?.length ? (
          <>
            <ul className="myths">
              {spec.mythology.map((m) => (
                <li key={`${m.creatureName}-${m.culture}`} className="myth">
                  <p className="myth__name">
                    {t.resembles(m.creatureName, m.culture)} <Pill tone="warning">{t.unverifiedTag}</Pill>
                  </p>
                  <p className="myth__parts">
                    {m.componentParts
                      .split("|")
                      .map((g) => g.replace(/:/, ": ").replace(/,/g, ", "))
                      .join(" · ")}
                  </p>
                  {m.verification ? <p className="myth__check">{m.verification}</p> : null}
                  {m.sourceUrl ? (
                    <a className="source-link" href={m.sourceUrl} target="_blank" rel="noreferrer noopener">
                      {t.source}: {m.sourceUrl.replace(/^https?:\/\//, "")}
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
            <p className="panel__fine">{t.mythologyNote}</p>
          </>
        ) : (
          <p className="panel__muted">{t.noMythology}</p>
        )}
      </Section>

      <Section title={t.parents} count={spec.parents.length}>
        <ul className="parents">
          {spec.parents.map((p) => (
            <Parent key={p.slot} p={p} />
          ))}
        </ul>
      </Section>

      <Section title={t.plan}>
        <p className="panel__plan">{spec.bodyPlan}</p>
        <ul className="donors">
          {PARTS.map((k) => (
            <li key={k} className={`donor donor--${spec.partDonors[k].toLowerCase()}`}>
              <span className="donor__part">{t.donors[k]}</span>
              <span className="donor__from">{spec.partDonors[k]}</span>
              {spec.donorSource?.[k] ? (
                <span className={`donor__by donor__by--${spec.donorSource[k]}`}>{spec.donorSource[k] === "user" ? t.byYou : t.byModel}</span>
              ) : null}
            </li>
          ))}
        </ul>
      </Section>

      {spec.rationale ? (
        <Section title={t.plannerNotes}>
          <p className="panel__text">{spec.rationale}</p>
        </Section>
      ) : null}

      <Section title={t.promptSources}>
        <div className="panel__heading-row">
          <h3 className="panel__heading">{t.prompt}</h3>
          <Button size="sm" variant="ghost" icon={copied ? "check" : "copy"} onClick={copyPrompt}>
            {copied ? t.copied : t.copy}
          </Button>
        </div>
        <pre className="prompt-block" tabIndex={0}>
          {spec.prompt}
        </pre>
        <h3 className="panel__heading">{t.models}</h3>
        <p className="panel__mono">
          {spec.model.vision} · {spec.model.image}
        </p>
        {sources.length ? (
          <>
            <h3 className="panel__heading">{t.sources}</h3>
            <ul className="sources">
              {sources.map((u) => (
                <li key={u}>
                  <a className="source-link" href={u} target="_blank" rel="noreferrer noopener">
                    {u.replace(/^https?:\/\//, "")}
                  </a>
                </li>
              ))}
            </ul>
          </>
        ) : null}
      </Section>
    </div>
  );
}
