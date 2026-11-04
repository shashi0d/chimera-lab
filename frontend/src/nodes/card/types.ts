import type { PortSpec } from "../../graph/types";
import type { AnimalCard } from "../../lab/api";

/** The animal card of the connected image: generated on demand (one lab action), kept on the server and here. */
export interface CardData extends Record<string, unknown> {
  card: AnimalCard | null;
  /** The version the card describes. */
  versionId: string | null;
  /** Make the card as soon as the image is ready (set when the card is added from an image). */
  autoStart?: boolean;
  error: string | null;
}

export type CardConfig = Record<string, never>;

export const CARD_INPUTS: PortSpec[] = [{ id: "in", accepts: ["version"] }];
export const CARD_OUTPUTS: PortSpec[] = [];
