import { defineNode } from "../types";
import { CardView } from "./NodeView";
import { CARD_INPUTS, CARD_OUTPUTS, type CardConfig, type CardData } from "./types";

export const cardNode = defineNode<CardConfig, CardData>({
  type: "card",
  version: 1,
  label: "Animal card",
  category: "output",
  icon: "card",
  addable: false, // added from an image card (toolbar, or the menu when dragging from its output)
  inputs: CARD_INPUTS,
  outputs: CARD_OUTPUTS,
  defaultConfig: {},
  defaultData: () => ({ card: null, versionId: null, error: null }),
  validate: () => [],
  View: CardView,
  runnable: false,
});
