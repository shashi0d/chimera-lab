import { ApiRequestError } from "../api/errors";
import type { EventStream, EvoTransport, StreamHandlers } from "../evo/transport";
import type { AgentEvent, Parent, RunAccepted, RunSnapshot, StartInput, StartResult } from "../evo/types";
import type { AnimalCard, LabVersion, WorkspaceInfo } from "../lab/api";
import creature from "./creature.json";

/**
 * The tutorial's sandbox. The tutorial runs in the real Lab UI (canvas, Fusion node, run progress, image card, Save,
 * Chimeras), but the calls that belong to it are answered here instead of by the server: the Fusion run is replayed
 * from a creature made once with the live models (Tiger × Bat, anime: public/example/), so no model is called.
 * Everything else goes to the server unchanged.
 */

export const TUTORIAL_WS = "tutorial";
export const TUTORIAL_VERSION = "tutorial_v1";
const RUN_PREFIX = "tutorial_run_";
const STATE_KEY = "chimera.tutorial";

/** The replay's clock (ms after the run starts). A real run takes about a minute; most of it is the model. */
export const REPLAY = { started: 400, step: 9000, render: 9800, finalize: 10400 };
/** How long the animal card takes to "draw" after saving (a real card takes about a minute too). */
export const CARD_MS = 7000;

export const SIRE = "Tiger";
export const DAM = "Bat";
export const STYLE = "anime" as const;

export function isTutorialId(id: string | null | undefined): boolean {
  return Boolean(id && (id === TUTORIAL_WS || id === TUTORIAL_VERSION || id.startsWith(RUN_PREFIX)));
}

// ------------------------------------------------------------------ state (survives a reload)

interface SandboxState {
  runId: string | null;
  runStartedAt: number | null;
  savedAt: number | null;
}

function read(): SandboxState {
  try {
    const s = JSON.parse(localStorage.getItem(STATE_KEY) ?? "null") as SandboxState | null;
    if (s && typeof s === "object") return { runId: s.runId ?? null, runStartedAt: s.runStartedAt ?? null, savedAt: s.savedAt ?? null };
  } catch {
    /* fall through */
  }
  return { runId: null, runStartedAt: null, savedAt: null };
}

function write(patch: Partial<SandboxState>): void {
  try {
    localStorage.setItem(STATE_KEY, JSON.stringify({ ...read(), ...patch }));
  } catch {
    /* storage blocked: the replay still works for this page */
  }
}

/** Forget the tutorial's run and creature (the tour ended or was skipped). */
export function clearSandbox(): void {
  try {
    localStorage.removeItem(STATE_KEY);
  } catch {
    /* nothing to clear */
  }
}

// ------------------------------------------------------------------ the creature

const sire: Parent = { commonName: SIRE, scientificName: null, source: "name", confidence: null };
const dam: Parent = { commonName: DAM, scientificName: null, source: "name", confidence: null };
const base = creature.version as unknown as LabVersion;
const readyCard = base.card as AnimalCard;

function cardNow(now = Date.now()): AnimalCard | null {
  const { savedAt } = read();
  if (savedAt == null) return null;
  return now - savedAt >= CARD_MS ? readyCard : { status: "running", profile: null, angles: [], error: null };
}

/** The tutorial's creature as the server would describe it right now. */
export function tutorialVersion(): LabVersion {
  const { runId, savedAt } = read();
  return {
    ...base,
    id: TUTORIAL_VERSION,
    runId,
    creatureId: null,
    workspaceId: TUTORIAL_WS,
    saved: savedAt != null,
    savedAt: savedAt != null ? new Date(savedAt).toISOString() : null,
    card: cardNow(),
  };
}

// ------------------------------------------------------------------ the Fusion run, replayed

function at(t: number): string {
  return new Date(t).toISOString();
}

function events(runId: string, startedAt: number): AgentEvent[] {
  const url = base.imageUrl;
  return [
    { id: 1, runId, at: at(startedAt + REPLAY.started), type: "started", sire, dam, style: STYLE },
    { id: 2, runId, at: at(startedAt + REPLAY.step), type: "step", n: 1, tool: "render", summary: `rendered: create a hybrid of ${SIRE} and ${DAM}`, ok: true },
    { id: 3, runId, at: at(startedAt + REPLAY.render), type: "render", n: 1, imageId: "img1", url },
    { id: 4, runId, at: at(startedAt + REPLAY.finalize), type: "finalize", creatureId: "tutorial_creature", imageId: "img1", imageUrl: url, title: base.title ?? undefined },
  ];
}

function released(runId: string, now = Date.now()): AgentEvent[] {
  const { runId: id, runStartedAt } = read();
  if (id !== runId || runStartedAt == null) return [];
  return events(runId, runStartedAt).filter((e) => Date.parse(e.at) <= now);
}

function notFound(): never {
  throw new ApiRequestError({ code: "RUN_NOT_FOUND", message: "This run doesn't exist.", retryable: false }, 404);
}

/** The app's transport, with the tutorial's run answered locally. */
export function withTutorial(inner: EvoTransport): EvoTransport {
  return {
    kind: inner.kind,
    health: () => inner.health(),
    getLimits: () => inner.getLimits(),
    imageUrl: (url) => inner.imageUrl(url),

    async startRun(input: StartInput): Promise<StartResult> {
      if (input.workspaceId !== TUTORIAL_WS) return inner.startRun(input);
      const runId = `${RUN_PREFIX}${Date.now().toString(36)}`;
      write({ runId, runStartedAt: Date.now(), savedAt: null });
      const accepted: RunAccepted = { runId, status: "running", position: null, eventsUrl: "", runUrl: "", sire, dam, style: STYLE };
      return { kind: "accepted", ...accepted };
    },

    async getRun(runId: string): Promise<RunSnapshot> {
      if (!isTutorialId(runId)) return inner.getRun(runId);
      const { runStartedAt } = read();
      if (runStartedAt == null || read().runId !== runId) notFound();
      const out = released(runId);
      const last = out[out.length - 1];
      const done = last?.type === "finalize";
      return {
        runId, status: done ? "succeeded" : "running", position: null, sire, dam, style: STYLE,
        createdAt: at(runStartedAt), updatedAt: last?.at ?? at(runStartedAt), lastEventId: last?.id ?? 0,
        creatureId: done ? "tutorial_creature" : null, error: null,
      };
    },

    streamEvents(runId: string, after: number, h: StreamHandlers): EventStream {
      if (!isTutorialId(runId)) return inner.streamEvents(runId, after, h);
      let last = after;
      let stopped = false;
      h.onState?.("connecting");
      const tick = () => {
        if (stopped) return;
        if (read().runId !== runId) {
          stop();
          h.onError?.({ code: "RUN_NOT_FOUND", message: "This run doesn't exist.", retryable: false });
          h.onState?.("closed");
          return;
        }
        for (const e of released(runId)) {
          if (e.id <= last) continue;
          last = e.id;
          h.onEvent(e);
          if (e.type === "finalize") {
            stop();
            h.onState?.("closed");
            return;
          }
        }
      };
      const timer = setInterval(tick, 250);
      const stop = () => {
        stopped = true;
        clearInterval(timer);
      };
      setTimeout(() => {
        if (!stopped) h.onState?.("open");
        tick();
      }, 30);
      return { stop };
    },
  };
}

// ------------------------------------------------------------------ the Lab API calls of the tutorial

const LOOK_AROUND = "In the tutorial you can look around. Try edits in your own workspace.";

function onlyLook(): never {
  throw new ApiRequestError({ code: "VALIDATION_FAILED", message: LOOK_AROUND, retryable: false }, 422);
}

const workspaceInfo = (): WorkspaceInfo => ({ id: TUTORIAL_WS, name: "Tutorial", createdAt: at(Date.now()), updatedAt: at(Date.now()) });

/** Answers for the Lab API calls that belong to the tutorial (lab/api.ts asks before going to the server). */
export const tutorialLab = {
  versionFromRun: async (): Promise<LabVersion> => tutorialVersion(),
  setSaved: async (saved: boolean): Promise<LabVersion> => {
    write({ savedAt: saved ? Date.now() : null });
    return tutorialVersion();
  },
  card: async (): Promise<AnimalCard> => {
    if (read().savedAt == null) write({ savedAt: Date.now() });
    return cardNow()!;
  },
  savedCard: async (): Promise<AnimalCard | null> => cardNow(),
  /** The tutorial creature joins the visitor's own chimeras while the tour runs, once saved. */
  withChimeras: (list: LabVersion[]): LabVersion[] => (read().savedAt != null ? [tutorialVersion(), ...list] : list),
  loadWorkspace: async (): Promise<WorkspaceInfo & { graph: null }> => ({ ...workspaceInfo(), graph: null }),
  saveWorkspace: async (): Promise<WorkspaceInfo> => workspaceInfo(),
  download: async (): Promise<Blob> => (await fetch(base.imageUrl)).blob(),
  onlyLook,
};
