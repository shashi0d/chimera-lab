import { useReactFlow, useViewport } from "@xyflow/react";
import { copy } from "../copy";
import { IconButton } from "../ui/Button";

export function ZoomControls() {
  const { zoom } = useViewport();
  const flow = useReactFlow();
  return (
    <div className="zoom-controls" role="group" aria-label="Zoom">
      <IconButton icon="minus" label={copy.toolbar.zoomOut} onClick={() => void flow.zoomOut({ duration: 150 })} />
      <span className="zoom-controls__value" aria-live="off">
        {Math.round(zoom * 100)}%
      </span>
      <IconButton icon="plus" label={copy.toolbar.zoomIn} onClick={() => void flow.zoomIn({ duration: 150 })} />
    </div>
  );
}
