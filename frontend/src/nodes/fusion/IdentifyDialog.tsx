import { useEffect, useId, useRef, useState } from "react";
import { copy } from "../../copy";
import { upstreamNode } from "../../graph/queries";
import { useGraph } from "../../graph/store";
import { Button } from "../../ui/Button";
import type { ImageInputData } from "../image-input/types";
import { usePreview } from "../image-input/usePreview";
import { confirmIdentify, useFusionStart } from "./start";
import { cleanName } from "./types";

const t = copy.identify;
const OTHER = "__other__";

/**
 * POST /evo/agent/runs answered needs_choice: the photo wasn't identified with confidence. No run exists yet;
 * the user confirms the animal and we post again with names only.
 */
export function IdentifyDialog() {
  const pending = useFusionStart((s) => s.identify);
  const dismiss = useFusionStart((s) => s.dismissIdentify);
  const ref = useRef<HTMLDialogElement>(null);
  const [pick, setPick] = useState<string>("");
  const [other, setOther] = useState("");
  const otherId = useId();
  const slotPort = pending?.choice.slot === "dam" ? "b" : "a";
  const photoNode = useGraph((s) => (pending ? upstreamNode(s, pending.nodeId, slotPort) : undefined));
  const preview = usePreview((photoNode?.data as ImageInputData | undefined) ?? {});

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (pending && !d.open) {
      setPick(pending.choice.options[0]?.commonName ?? OTHER);
      setOther("");
      d.showModal?.();
    }
    if (!pending && d.open) d.close();
  }, [pending]);

  const answer = pick === OTHER ? cleanName(other) : pick;
  const slotLetter = pending?.choice.slot === "dam" ? "B" : "A";

  return (
    <dialog ref={ref} className="modal identify" aria-labelledby="identify-title" onClose={() => dismiss()}>
      {pending ? (
        <form
          method="dialog"
          onSubmit={(e) => {
            e.preventDefault();
            if (answer) void confirmIdentify(answer);
          }}
        >
          <p className="modal__kicker">{t.kicker(slotLetter)}</p>
          <h2 id="identify-title" className="modal__title">
            {pending.choice.question}
          </h2>
          <div className="identify__row">
            {preview ? <img className="identify__photo" src={preview} alt={t.photoAlt(slotLetter)} /> : null}
            <p className="identify__body">{t.body}</p>
          </div>
          <fieldset className="identify__options">
            <legend className="sr-only">{pending.choice.question}</legend>
            {pending.choice.options.map((o) => (
              <label key={o.commonName} className={`identify__option${pick === o.commonName ? " is-checked" : ""}`}>
                <input type="radio" name="identify" value={o.commonName} checked={pick === o.commonName} onChange={() => setPick(o.commonName)} />
                <span className="identify__name">{o.commonName}</span>
                {o.scientificName ? <span className="identify__sci binomial">{o.scientificName}</span> : null}
                {o.confidence !== null ? <span className="identify__conf">{t.sure(o.confidence)}</span> : null}
              </label>
            ))}
            {pending.choice.allowOther ? (
              <label className={`identify__option identify__option--other${pick === OTHER ? " is-checked" : ""}`}>
                <input type="radio" name="identify" value={OTHER} checked={pick === OTHER} onChange={() => setPick(OTHER)} />
                <span className="identify__name">{t.other}</span>
              </label>
            ) : null}
          </fieldset>
          {pick === OTHER ? (
            <div className="identify__other">
              <label className="field-label" htmlFor={otherId}>
                {t.otherLabel}
              </label>
              <input id={otherId} className="text-input" value={other} maxLength={60} autoComplete="off" onChange={(e) => setOther(e.target.value)} />
            </div>
          ) : null}
          <p className="identify__note">{t.note}</p>
          <div className="modal__actions">
            <Button variant="ghost" onClick={() => dismiss()}>
              {t.cancel}
            </Button>
            <Button variant="primary" type="submit" icon="check" disabled={!answer}>
              {t.confirm}
            </Button>
          </div>
        </form>
      ) : null}
    </dialog>
  );
}
