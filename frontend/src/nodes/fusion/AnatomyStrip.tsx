import { copy } from "../../copy";
import { useGraph } from "../../graph/store";
import { AUTO_DONORS, PARTS, readDonors, type DonorPin, type FusionConfig, type Part } from "./types";

const t = copy.nodes.fusion;
const NEXT: Record<DonorPin, DonorPin> = { auto: "A", A: "B", B: "auto" };

/** F1: pin each body part to parent A or B, or leave it to the model. */
export function AnatomyStrip({ nodeId, config, disabled }: { nodeId: string; config: FusionConfig; disabled: boolean }) {
  const donors = readDonors(config);
  const pinned = PARTS.some((p) => donors[p] !== "auto");

  const set = (next: Record<Part, DonorPin>) => {
    const g = useGraph.getState();
    g.updateNodeConfig<FusionConfig>(nodeId, (c) => ({ ...c, donors: next }));
    g.markDownstreamStale(nodeId);
    useGraph.getState().updateNodeData(nodeId, (d) => (d.runIds && (d.runIds as string[]).length ? { ...d, stale: true } : d));
  };

  return (
    <fieldset className="anatomy" disabled={disabled}>
      <legend className="anatomy__legend">
        <span>{t.anatomy}</span>
        {pinned ? (
          <button type="button" className="link-btn nodrag" onClick={() => set({ ...AUTO_DONORS })}>
            {t.resetAnatomy}
          </button>
        ) : null}
      </legend>
      <div className="anatomy__parts" role="group" aria-describedby={`${nodeId}-anatomy-hint`}>
        {PARTS.map((part) => {
          const v = donors[part];
          const label = copy.panel.donors[part];
          return (
            <button
              key={part}
              type="button"
              className={`anatomy__part anatomy__part--${v.toLowerCase()} nodrag`}
              aria-label={t.partFrom(label, v)}
              onClick={() => set({ ...donors, [part]: NEXT[v] })}
            >
              <span className="anatomy__name">{label}</span>
              <span className="anatomy__value" aria-hidden="true">
                {v === "auto" ? t.auto : v}
              </span>
            </button>
          );
        })}
      </div>
      <p id={`${nodeId}-anatomy-hint`} className="sr-only">
        {t.anatomyHint}
      </p>
    </fieldset>
  );
}
