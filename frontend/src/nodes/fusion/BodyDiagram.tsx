import type { KeyboardEvent } from "react";
import { copy } from "../../copy";
import { useGraph } from "../../graph/store";
import { BODY_REGIONS } from "./bodyRegions";
import { AUTO_DONORS, readDonors, type DonorPin, type FusionConfig, type Part } from "./types";

const t = copy.nodes.fusion;
const NEXT: Record<DonorPin, DonorPin> = { auto: "A", A: "B", B: "auto" };

export interface DonorFace {
  preview?: string;
  name: string;
}

/** Write a new pin map: one undo step; outdates the result. */
export function setDonors(nodeId: string, next: Record<Part, DonorPin>): void {
  const g = useGraph.getState();
  g.updateNodeConfig<FusionConfig>(nodeId, (c) => ({ ...c, donors: next }));
  g.markDownstreamStale(nodeId);
  useGraph.getState().updateNodeData(nodeId, (d) => (d.runIds && (d.runIds as string[]).length ? { ...d, stale: true } : d));
}

export function resetDonors(nodeId: string): void {
  setDonors(nodeId, { ...AUTO_DONORS });
}

/**
 * F1 anatomy pins as a clickable silhouette (U1). Click, Enter or Space cycles Auto → A → B.
 * A pinned part shows the donor parent's portrait and letter; Auto is a dashed outline.
 */
export function BodyDiagram({
  nodeId,
  config,
  disabled,
  faces,
}: {
  nodeId: string;
  config: FusionConfig;
  disabled: boolean;
  faces: Record<"A" | "B", DonorFace>;
}) {
  const donors = readDonors(config);
  const cycle = (part: Part) => {
    if (!disabled) setDonors(nodeId, { ...donors, [part]: NEXT[donors[part]] });
  };
  const onKey = (part: Part) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      cycle(part);
    }
  };

  return (
    <div className={`body-diagram${disabled ? " is-disabled" : ""}`}>
      <div className="body-diagram__head">
        <p className="body-diagram__kicker">{t.anatomy}</p>
        <p className="body-diagram__legend" aria-hidden="true">
          <span className="legend-key legend-key--auto" /> {t.auto}
          <span className="legend-key legend-key--a" /> A
          <span className="legend-key legend-key--b" /> B
        </p>
      </div>
      <svg className="body-diagram__svg nodrag" viewBox="0 0 260 160" role="group" aria-label={t.anatomy} aria-describedby={`${nodeId}-anatomy-hint`}>
        <defs>
          {BODY_REGIONS.map((r) => (
            <clipPath key={r.id} id={`${nodeId}-clip-${r.id}`}>
              <circle cx={r.badge.x} cy={r.badge.y} r={10} />
            </clipPath>
          ))}
        </defs>
        {BODY_REGIONS.map((r) => {
          const v = donors[r.id];
          const name = copy.panel.donors[r.id];
          const face = v === "auto" ? null : faces[v];
          return (
            <g
              key={r.id}
              role="button"
              tabIndex={disabled ? -1 : 0}
              aria-disabled={disabled || undefined}
              aria-label={t.partFrom(name, v)}
              className={`body-region body-region--${r.id} body-region--${v.toLowerCase()}`}
              onClick={() => cycle(r.id)}
              onKeyDown={onKey(r.id)}
            >
              {r.hit ? <path className="body-region__hit" d={r.hit} /> : null}
              <path className="body-region__shape" d={r.d} />
              <text className="body-region__label" x={r.label.x} y={r.label.y} textAnchor="middle">
                {name}
              </text>
              {face ? (
                <g className="body-region__badge" aria-hidden="true">
                  <circle className="body-region__badge-ring" cx={r.badge.x} cy={r.badge.y} r={12} />
                  {face.preview ? (
                    <image
                      href={face.preview}
                      x={r.badge.x - 10}
                      y={r.badge.y - 10}
                      width={20}
                      height={20}
                      preserveAspectRatio="xMidYMid slice"
                      clipPath={`url(#${nodeId}-clip-${r.id})`}
                    />
                  ) : null}
                  <circle className="body-region__badge-tag" cx={r.badge.x + 10} cy={r.badge.y + 9} r={8} />
                  <text className="body-region__badge-letter" x={r.badge.x + 10} y={r.badge.y + 13} textAnchor="middle">
                    {v}
                  </text>
                </g>
              ) : null}
            </g>
          );
        })}
      </svg>
      <p id={`${nodeId}-anatomy-hint`} className="sr-only">
        {t.anatomyHint}
      </p>
    </div>
  );
}
