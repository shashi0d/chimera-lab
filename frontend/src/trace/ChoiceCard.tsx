import { useNow } from "../canvas/useNow";
import { copy } from "../copy";
import { useEvoRuns, useRunRecord } from "../evo/runs";
import type { NeedsChoiceEvent } from "../evo/types";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { remaining } from "./time";

const t = copy.trace.choice;

/** The agent asked the user (ask_user on a host tie). The run waits until answered or expired. */
export function ChoiceCard({ runId, choice }: { runId: string; choice: NeedsChoiceEvent }) {
  const rec = useRunRecord(runId);
  const answer = useEvoRuns((s) => s.answerChoice);
  const now = useNow(true, 1000);
  const left = remaining(choice.expiresAt, now);
  const expired = Date.parse(choice.expiresAt) <= now;
  const sending = rec?.choice.sending ?? false;
  const sent = rec?.choice.sent ?? null;
  const err = rec?.choice.error ?? null;

  return (
    <section className="choice" aria-labelledby={`choice-${choice.choiceId}`}>
      <p className="choice__kicker">{t.kicker}</p>
      <h3 id={`choice-${choice.choiceId}`} className="choice__question">
        {choice.question}
      </h3>
      <p className="choice__body">{t.body}</p>
      <div className="choice__options" role="group" aria-label={t.optionsLabel}>
        {choice.options.map((o) => (
          <Button
            key={o}
            variant={sent === o ? "primary" : "secondary"}
            className="choice__option"
            busy={sending && sent === null ? false : undefined}
            disabled={sending || Boolean(sent) || expired}
            onClick={() => void answer(runId, choice.choiceId, o)}
          >
            {o}
          </Button>
        ))}
      </div>
      <p className="choice__timer" aria-live="off">
        <Icon name="info" size={14} /> {expired ? t.expired : sent ? t.sent(sent) : sending ? t.sending : t.expires(left)}
      </p>
      {err ? (
        <p className="choice__error" role="alert">
          <Icon name="error" size={14} /> {err.code === "VALIDATION_FAILED" ? t.conflict : t.failed}
        </p>
      ) : null}
    </section>
  );
}
