import { defineNode } from "../types";
import { handleFieldCardRun } from "./actions";
import { FieldCardView } from "./NodeView";
import { FIELD_CARD_INPUTS, type FieldCardConfig, type FieldCardData } from "./types";
import { validateFieldCard } from "./validate";

/** F2: field-guide card for the upstream Result's selected version. */
export const fieldCardNode = defineNode<FieldCardConfig, FieldCardData>({
  type: "field-card",
  version: 1,
  label: "Field card",
  category: "output",
  icon: "card",
  addable: false, // created from a Result node ("Make field card") or wired by hand
  inputs: FIELD_CARD_INPUTS,
  outputs: [],
  defaultConfig: {},
  defaultData: () => ({ activeRunId: null, runIds: [], card: null }),
  validate: validateFieldCard,
  View: FieldCardView,
  runnable: true,
  onRunUpdate: handleFieldCardRun,
});
