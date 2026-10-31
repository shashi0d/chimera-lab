import type { CreatureSpec } from "../../types/api";
import { parentName } from "../image-input/species";
import { PARTS } from "../fusion/types";

// U1: the drawer's plain-language lead, built from structured fields only (never model prose).
// L2: a backend summary field, when it exists, replaces this function's output here.

function list(xs: string[]): string {
  if (xs.length <= 1) return xs.join("");
  return `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`;
}

function lower(s: string): string {
  return s.toLowerCase();
}

export function summarize(spec: CreatureSpec): string[] {
  const nameOf = (slot: "A" | "B") => {
    const p = spec.parents.find((x) => x.slot === slot);
    return (p && parentName(p)) || `parent ${slot}`;
  };
  const names = { A: nameOf("A"), B: nameOf("B") };
  const donors = spec.partDonors as unknown as Record<string, "A" | "B">;
  const parts = PARTS.filter((id) => donors[id]);
  const fromA = parts.filter((p) => donors[p] === "A");
  const fromB = parts.filter((p) => donors[p] === "B");
  const out: string[] = [];

  if (!fromA.length || !fromB.length) {
    const only = fromA.length ? names.A : names.B;
    out.push(`Every body part comes from the ${lower(only)}.`);
  } else {
    const verb = (xs: string[]) => (xs.length === 1 ? "comes" : "come");
    const cap = (s: string) => s[0]!.toUpperCase() + s.slice(1);
    out.push(`${cap(`the ${list(fromA)}`)} ${verb(fromA)} from the ${lower(names.A)}; the ${list(fromB)} ${verb(fromB)} from the ${lower(names.B)}.`);
  }

  const hybrids = spec.realHybrids?.length ? spec.realHybrids : spec.realHybrid ? [spec.realHybrid] : [];
  const myth = spec.mythology?.[0];
  const hybridText = hybrids.length
    ? `Real hybrids of these parents exist (${list(hybrids.map((h) => h.name))})`
    : "No real hybrid of these parents is documented";
  out.push(myth ? `${hybridText}, and the pair resembles the ${myth.creatureName} of ${myth.culture} myth (unverified).` : `${hybridText}.`);

  const warnings = (spec.warnings ?? []).filter((w) => w.severity === "warning").length;
  out.push(warnings ? `The anatomy rules raised ${warnings} warning${warnings === 1 ? "" : "s"}.` : "The anatomy rules raised no warnings.");
  return out;
}
