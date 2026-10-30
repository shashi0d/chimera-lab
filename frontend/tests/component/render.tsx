import { ReactFlowProvider } from "@xyflow/react";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { useGraph } from "../../src/graph/store";
import { getDefinition } from "../../src/nodes/registry";
import type { ValidationIssue } from "../../src/nodes/types";
import { useConnectivity } from "../../src/connectivity/store";

export function renderInFlow(ui: ReactElement) {
  return render(<ReactFlowProvider>{ui}</ReactFlowProvider>);
}

/** Render one node by id from the graph store, with its real validation issues. */
export function renderNode(id: string) {
  const Node = () => {
    const node = useGraph((s) => s.nodes.find((n) => n.id === id));
    const nodes = useGraph((s) => s.nodes);
    const edges = useGraph((s) => s.edges);
    const connectivity = useConnectivity((s) => s.status);
    if (!node) return null;
    const def = getDefinition(node.type);
    if (!def) return null;
    const issues: ValidationIssue[] = def.validate(node, { graph: { nodes, edges }, connectivity, readOnly: false });
    return <def.View node={node} selected={false} issues={issues} catalog={1} />;
  };
  return renderInFlow(<Node />);
}
