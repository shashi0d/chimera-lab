import { useEffect, useLayoutEffect, useRef, useState, type ClipboardEvent, type KeyboardEvent } from "react";
import { toAppError } from "../api/errors";
import { presentError } from "../api/errorMessages";
import { evo } from "../evo/index";
import { toast } from "../ui/toastStore";
import { labApi, type CreatureProfile, type LabVersion } from "./api";

/**
 * The animal card (field-guide page). Closed, it shows only the creature and its name; a tap opens the whole page:
 * the name moves to the heading, the frame draws itself, the stats and notes reveal, the four angles slide in and the
 * trait stamps down. Laid out in a fixed 1100×1010 space and scaled to the width it is given. Its text can be edited.
 */

const STAGE_W = 1100;
const STAGE_H = 1010;
const VIEWS: { key: string; label: string }[] = [
  { key: "front", label: "FRONT" },
  { key: "side", label: "SIDE" },
  { key: "back", label: "BACK" },
  { key: "above", label: "ABOVE" },
];

type Field = "name" | "length" | "weight" | "habitat" | "explorers_notes";

function profileOf(version: LabVersion): CreatureProfile | null {
  return version.card?.profile ?? version.profile ?? null;
}

export function CodexCard({ version, onChange, startOpen = false, autoOpen = false, editable = true, onClose }: {
  version: LabVersion;
  onChange?: (v: LabVersion) => void;
  startOpen?: boolean;
  /** Play the opening animation as soon as the card is shown (the card modal). */
  autoOpen?: boolean;
  editable?: boolean;
  /** Called after the card closes (the modal closes with it). */
  onClose?: () => void;
}) {
  const wrap = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const fields = useRef<Partial<Record<Field, HTMLElement | null>>>({});
  const [open, setOpen] = useState(startOpen);
  const [pressed, setPressed] = useState(false);
  const [editing, setEditing] = useState(false);
  const [saved, setSaved] = useState("");
  const p = profileOf(version);
  const card = version.card;
  const name = p?.name || version.title || "Unnamed creature";
  const angles = new Map((card?.angles ?? []).map((a) => [a.view, a.url]));
  const drawing = card?.status === "running";

  // Scale the fixed stage to the width available (no inline style props: set on the elements).
  useLayoutEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const fit = () => {
      const w = el.parentElement?.clientWidth ?? STAGE_W;
      const s = Math.max(Math.min(w, STAGE_W), 240) / STAGE_W;
      stage.current?.style.setProperty("--fit", String(s));
      el.style.width = `${STAGE_W * s}px`;
      el.style.height = `${STAGE_H * s}px`;
    };
    fit();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(fit) : null;
    if (el.parentElement) ro?.observe(el.parentElement);
    return () => ro?.disconnect();
  }, []);

  useEffect(() => {
    if (p?.accent_color) cardRef.current?.style.setProperty("--slate", p.accent_color);
  }, [p?.accent_color]);

  const openCard = () => {
    if (open) return;
    setPressed(true);
    window.setTimeout(() => {
      setPressed(false);
      setOpen(true);
    }, 110);
  };
  const closeCard = () => {
    setOpen(false);
    if (onClose) window.setTimeout(onClose, 420); // let the card fold back first
  };

  useEffect(() => {
    if (!autoOpen) return;
    const id = window.setTimeout(() => setOpen(true), 160);
    return () => window.clearTimeout(id);
  }, [autoOpen]);

  const save = async () => {
    const read = (f: Field) => (fields.current[f]?.textContent ?? "").replace(/\s+/g, " ").trim();
    const body = { name: read("name"), length: read("length"), weight: read("weight"), habitat: read("habitat"), explorers_notes: read("explorers_notes") };
    try {
      const v = await labApi.editProfile(version.id, body);
      onChange?.(v);
      setSaved("Saved");
    } catch (e) {
      const err = presentError(toAppError(e));
      toast.error(`${err.title}${err.fix ? ` ${err.fix}` : ""}`);
      setSaved("Not saved");
    }
    window.setTimeout(() => setSaved(""), 1600);
  };

  const toggleEdit = () => {
    if (editing) void save();
    setEditing((v) => !v);
    if (!editing) window.setTimeout(() => fields.current.name?.focus(), 0);
  };

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (!open && (e.key === "Enter" || e.key === " ")) {
      e.preventDefault();
      openCard();
    } else if (open && e.key === "Escape" && !editing) {
      e.stopPropagation();
      closeCard();
    }
  };

  const editProps = (f: Field) => ({
    ref: (el: HTMLElement | null) => {
      fields.current[f] = el;
    },
    contentEditable: editing,
    suppressContentEditableWarning: true,
    onPaste: (e: ClipboardEvent) => {
      e.preventDefault();
      document.execCommand("insertText", false, e.clipboardData.getData("text/plain"));
    },
  });

  return (
    <div className="codex2-wrap nodrag nowheel" ref={wrap}>
      <div className="codex2-stage" ref={stage}>
        <div className={`codex2-press${pressed ? " down" : ""}`}>
          <div
            ref={cardRef}
            className={`codex2${open ? " open" : ""}${editing ? " editing" : ""}`}
            role={open ? "group" : "button"}
            tabIndex={0}
            aria-expanded={open}
            aria-label={open ? `${name} card` : `${name}. Open card`}
            onClick={(e) => {
              if (!(e.target as HTMLElement).closest("button")) openCard();
            }}
            onKeyDown={onKey}
          >
            <svg className="codex2__frame codex2__abs" viewBox="0 0 1100 1010" aria-hidden="true">
              <path pathLength={1} className="d1" d="M38 32 H1058" />
              <path pathLength={1} className="d2" d="M1028 24 H1074 V52" />
              <path pathLength={1} className="d2" d="M28 954 V986 H74" />
              <path pathLength={1} className="d3" d="M74 980 H1066" />
            </svg>

            <div className="codex2__slate codex2__abs" />
            <div className="codex2__hero codex2__abs">
              <img src={evo().imageUrl(version.imageUrl)} alt={`${name}${p?.summary ? `: ${p.summary}` : ""}`} decoding="async" />
            </div>

            <h3 className="codex2__name codex2__abs" {...editProps("name")}>
              {name}
            </h3>
            <div className="codex2__underline codex2__abs" />
            <p className="codex2__hint codex2__abs">{drawing ? "Drawing the card…" : "Tap to open"}</p>

            <p className="codex2__stats codex2__abs codex2__reveal r1">
              Length - <span {...editProps("length")}>{p?.length || "unknown"}</span>
              {"   "}Weight - <span {...editProps("weight")}>{p?.weight || "unknown"}</span>
            </p>
            <p className="codex2__habitat codex2__abs codex2__reveal r2">
              Habitat - <span {...editProps("habitat")}>{p?.habitat || "unknown"}</span>
            </p>
            <p className="codex2__notes codex2__abs">
              <b>Explorer's Notes - </b>
              <span {...editProps("explorers_notes")}>{p?.explorers_notes || "This creature has no notes yet."}</span>
            </p>

            {VIEWS.map((v, i) => {
              const url = angles.get(v.key);
              return (
                <div key={v.key} className={`codex2__thumb codex2__abs t${i + 1}${url ? "" : " is-empty"}${drawing ? " is-drawing" : ""}`}>
                  {url ? <img src={evo().imageUrl(url)} alt={`${name}, ${v.label.toLowerCase()} view`} loading="lazy" decoding="async" /> : <i aria-hidden="true" />}
                  <span>{v.label}</span>
                </div>
              );
            })}

            {p?.trait ? <p className="codex2__stamp codex2__abs">{p.trait}</p> : null}
            {editable ? (
              <button type="button" className={`codex2__edit codex2__abs codex2__reveal r5${editing ? " on" : ""}`} onClick={(e) => {
                e.stopPropagation();
                toggleEdit();
              }}>
                {editing ? "Save" : "Edit"}
              </button>
            ) : null}
            <span className={`codex2__saved codex2__abs${saved ? " show" : ""}`} aria-live="polite">
              {saved}
            </span>
            <button
              type="button"
              className="codex2__close codex2__abs"
              aria-label="Close card"
              onClick={(e) => {
                e.stopPropagation();
                if (editing) toggleEdit();
                closeCard();
                cardRef.current?.focus();
              }}
            >
              ×
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
