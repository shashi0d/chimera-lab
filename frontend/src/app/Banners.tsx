import { useConnectivity } from "../connectivity/store";
import { copy } from "../copy";
import { isExampleWorkspace } from "../example/example";
import { useGraph } from "../graph/store";
import { useWorkspaces } from "../persistence/workspaces";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";

export function Banners() {
  const status = useConnectivity((s) => s.status);
  const check = useConnectivity((s) => s.check);
  // The tutorial's example is read-only on purpose: the tour explains it, so no banner.
  const example = useWorkspaces((s) => isExampleWorkspace(s.currentId));
  const readOnly = useGraph((s) => s.readOnly) && !example;
  return (
    <div className="banners" aria-live="polite">
      {status === "offline" ? (
        <div className="banner banner--offline" role="status">
          <Icon name="offline" size={16} />
          <p>{copy.connectivity.offline}</p>
        </div>
      ) : status === "unreachable" ? (
        <div className="banner banner--unreachable" role="status">
          <Icon name="alert" size={16} />
          <p>{copy.connectivity.unreachable}</p>
          <Button size="sm" variant="ghost" icon="refresh" onClick={() => void check()}>
            {copy.connectivity.retryNow}
          </Button>
        </div>
      ) : null}
      {readOnly ? (
        <div className="banner banner--readonly" role="status">
          <Icon name="info" size={16} />
          <p>{copy.graph.newerVersion}</p>
        </div>
      ) : null}
    </div>
  );
}
