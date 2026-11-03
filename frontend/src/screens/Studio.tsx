import { useEffect, useState } from "react";
import { absoluteUrl, baseHeaders, request } from "../api/client";
import { Button } from "../ui/Button";

type Version = { id: string; parentId: string | null; imageUrl: string; instruction: string; direction: string; createdAt: string; mode: string };
const STORAGE = "chimera.studio.versions.v1";

function restore(): Version[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE) || "[]");
    return Array.isArray(value) ? value.filter((v): v is Version => typeof v?.id === "string" && typeof v?.imageUrl === "string") : [];
  } catch { return []; }
}

export function Studio() {
  const [names, setNames] = useState(["", ""]);
  const [files, setFiles] = useState<Array<File | null>>([null, null]);
  const [brief, setBrief] = useState("");
  const [edit, setEdit] = useState("");
  const [versions, setVersions] = useState<Version[]>(restore);
  const [selected, setSelected] = useState<string | null>(() => restore().at(-1)?.id ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const current = versions.find((v) => v.id === selected);

  useEffect(() => { try { localStorage.setItem(STORAGE, JSON.stringify(versions)); } catch { /* storage may be unavailable */ } }, [versions]);

  const add = (v: Version) => { setVersions((old) => [...old, v]); setSelected(v.id); };
  async function create() {
    setBusy(true); setError("");
    try {
      const form = new FormData();
      names.forEach((name, i) => { if (name.trim()) form.append(`animal${i + 1}`, name.trim()); });
      files.forEach((file, i) => { if (file) form.append(`image${i + 1}`, file); });
      form.append("brief", brief);
      const { data } = await request<Version>("/evo/studio/concept", { method: "POST", headers: baseHeaders(), body: form });
      add(data);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create the concept."); }
    finally { setBusy(false); }
  }
  async function revise() {
    if (!current) return;
    setBusy(true); setError("");
    try {
      const { data } = await request<Version>(`/evo/studio/versions/${encodeURIComponent(current.id)}/revise`, {
        method: "POST", headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ instruction: edit }),
      });
      add(data); setEdit("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not revise the draft."); }
    finally { setBusy(false); }
  }

  return <div className="studio page">
    <header className="studio__heading"><p className="hero__kicker">CREATIVE STUDIO · EARLY DEMO</p>
      <h1 className="hero__title">Imagine it together.</h1>
      <p className="hero__lead">Start with an idea, explore a concept, then direct the next version. Your vision leads.</p>
    </header>
    <div className="studio__layout">
      <section className="studio__panel" aria-labelledby="studio-brief">
        <p className="studio__eyebrow">01 / YOUR IDEA</p><h2 id="studio-brief">Create a concept</h2>
        <p>Give each animal a name, an image, or both. Images are sent as visual references.</p>
        {[0, 1].map((i) => <div className="studio__animal" key={i}>
          <label htmlFor={`animal-${i}`}>Animal {i + 1}</label>
          <input id={`animal-${i}`} className="text-input" value={names[i]} maxLength={80} placeholder={i === 0 ? "e.g. monkey" : "e.g. spider"} disabled={busy}
            onChange={(e) => setNames((old) => old.map((v, n) => n === i ? e.target.value : v))} />
          <label className="studio__upload" htmlFor={`image-${i}`}>Reference image (optional)</label>
          <input id={`image-${i}`} type="file" accept="image/png,image/jpeg,image/webp" disabled={busy}
            onChange={(e) => setFiles((old) => old.map((v, n) => n === i ? e.target.files?.[0] ?? null : v))} />
        </div>)}
        <label htmlFor="studio-idea">What do you imagine?</label>
        <textarea id="studio-idea" className="text-input studio__textarea" value={brief} maxLength={2000} rows={5} disabled={busy}
          placeholder="A monkey's upper body joined to a spider's abdomen and eight legs..." onChange={(e) => setBrief(e.target.value)} />
        <Button variant="primary" busy={busy} disabled={busy || !brief.trim() || names.some((n, i) => !n.trim() && !files[i])} onClick={() => void create()}>
          {busy ? "Working on your idea…" : "Generate concept"}
        </Button>
        <p className="studio__note">Each generation or revision uses one daily run. Images can take a few minutes.</p>
      </section>
      <section className="studio__workspace" aria-labelledby="studio-draft">
        <div className="studio__workspace-head"><div><p className="studio__eyebrow">02 / EXPLORE & REFINE</p><h2 id="studio-draft">Your concept</h2></div>
          {current && <span className="studio__badge">{current.mode === "mock" ? "Mock preview" : "Generated image"}</span>}</div>
        {error && <p className="studio__error" role="alert">{error}</p>}
        <div className="studio__canvas">{current ? <img src={absoluteUrl(current.imageUrl)} alt="Selected generated chimera concept" /> :
          <div><span aria-hidden="true">✳</span><p>Your first concept will appear here.</p><small>Describe your creature to begin.</small></div>}</div>
        {current && <>
          <p className="studio__instruction"><strong>{current.parentId ? "Revision" : "Your brief"}:</strong> {current.instruction}</p>
          {current.direction && <details><summary>See the collaborator’s direction</summary><p>{current.direction}</p></details>}
          <label htmlFor="studio-edit">What would you like to change?</label>
          <textarea id="studio-edit" className="text-input studio__textarea" rows={3} maxLength={2000} value={edit} disabled={busy}
            placeholder="Make the spider legs longer, keeping the monkey's expression..." onChange={(e) => setEdit(e.target.value)} />
          <div className="studio__actions"><Button variant="primary" busy={busy} disabled={busy || !edit.trim()} onClick={() => void revise()}>Revise selected draft</Button>
            <a className="btn btn--secondary" href={absoluteUrl(current.imageUrl)} download target="_blank" rel="noreferrer">Open image</a></div>
          <p className="studio__note">Revisions use the selected image as their starting point. The model may change other details too.</p>
        </>}
        {versions.length > 0 && <div className="studio__history"><h3>Versions</h3><p>Choose any version to branch from it.</p><div className="studio__versions">
          {versions.map((v, i) => <button type="button" key={v.id} className={`studio__version${v.id === selected ? " is-selected" : ""}`} aria-pressed={v.id === selected} disabled={busy} onClick={() => setSelected(v.id)}>
            <img src={absoluteUrl(v.imageUrl)} alt="" /><span>Version {i + 1}{v.parentId ? ` · from ${versions.findIndex((p) => p.id === v.parentId) + 1}` : " · concept"}</span>
          </button>)}
        </div></div>}
      </section>
    </div>
  </div>;
}
