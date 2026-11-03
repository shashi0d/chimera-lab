import { useEffect, useRef, useState } from "react";
import { absoluteUrl, baseHeaders, request } from "../api/client";
import { Button } from "../ui/Button";
import { StudioCanvas, type StudioVersion as Version } from "./StudioCanvas";

type Review = { observation: string; suggestions: string };
type Job = { id: string; operation: string; status: string; stage: string; result: Version | null; error: string | null };
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
  const [jobs, setJobs] = useState<Job[]>([]);
  const known = useRef(new Set(restore().map((v) => v.id)));
  const [review, setReview] = useState<Review | null>(null);
  const [error, setError] = useState("");
  const current = versions.find((v) => v.id === selected);
  const activeJob = jobs.find((job) => job.status === "queued" || job.status === "running");
  const working = busy || Boolean(activeJob);

  useEffect(() => { try { localStorage.setItem(STORAGE, JSON.stringify(versions)); } catch { /* storage may be unavailable */ } }, [versions]);
  useEffect(() => {
    let cancelled = false;
    void request<{ versions: Version[] }>("/evo/studio/versions", { headers: baseHeaders() }).then(({ data }) => {
      if (cancelled) return;
      setVersions(data.versions);
      setSelected((old) => data.versions.some((v) => v.id === old) ? old : data.versions.at(-1)?.id ?? null);
    }).catch(() => { /* Keep the local copy available when offline. */ });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => { setReview(null); }, [selected]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const { data } = await request<{ jobs: Job[] }>("/evo/studio/jobs", { headers: baseHeaders() });
        if (cancelled) return;
        setJobs(data.jobs);
        for (const job of data.jobs) {
          if (job.status === "succeeded" && job.result && !known.current.has(job.result.id)) {
            known.current.add(job.result.id);
            setVersions((old) => old.some((v) => v.id === job.result!.id) ? old : [...old, job.result!]);
            setSelected(job.result.id);
          }
        }
      } catch { /* Keep polling if the network drops. */ }
      if (!cancelled) timer = setTimeout(() => void poll(), 2000);
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, []);

  async function create() {
    setBusy(true); setError("");
    try {
      const form = new FormData();
      names.forEach((name, i) => { if (name.trim()) form.append(`animal${i + 1}`, name.trim()); });
      files.forEach((file, i) => { if (file) form.append(`image${i + 1}`, file); });
      form.append("brief", brief);
      const { data } = await request<Job>("/evo/studio/concept?background=1", { method: "POST", headers: baseHeaders(), body: form });
      setJobs((old) => [data, ...old.filter((job) => job.id !== data.id)]);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not create the concept."); }
    finally { setBusy(false); }
  }
  async function revise() {
    if (!current) return;
    setBusy(true); setError("");
    try {
      const { data } = await request<Job>(`/evo/studio/versions/${encodeURIComponent(current.id)}/revise?background=1`, {
        method: "POST", headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ instruction: edit }),
      });
      setJobs((old) => [data, ...old.filter((job) => job.id !== data.id)]); setEdit("");
    } catch (e) { setError(e instanceof Error ? e.message : "Could not revise the draft."); }
    finally { setBusy(false); }
  }
  async function askForReview() {
    if (!current) return;
    setBusy(true); setError(""); setReview(null);
    try {
      const { data } = await request<Review>(`/evo/studio/versions/${encodeURIComponent(current.id)}/review`, {
        method: "POST", headers: baseHeaders(),
      });
      setReview(data);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not review this draft."); }
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
          <input id={`animal-${i}`} className="text-input" value={names[i]} maxLength={80} placeholder={i === 0 ? "e.g. monkey" : "e.g. spider"} disabled={working}
            onChange={(e) => setNames((old) => old.map((v, n) => n === i ? e.target.value : v))} />
          <label className="studio__upload" htmlFor={`image-${i}`}>Reference image (optional)</label>
          <input id={`image-${i}`} type="file" accept="image/png,image/jpeg,image/webp" disabled={working}
            onChange={(e) => setFiles((old) => old.map((v, n) => n === i ? e.target.files?.[0] ?? null : v))} />
        </div>)}
        <label htmlFor="studio-idea">What do you imagine?</label>
        <textarea id="studio-idea" className="text-input studio__textarea" value={brief} maxLength={2000} rows={5} disabled={working}
          placeholder="A monkey's upper body joined to a spider's abdomen and eight legs..." onChange={(e) => setBrief(e.target.value)} />
        <Button variant="primary" busy={working} disabled={working || !brief.trim() || names.some((n, i) => !n.trim() && !files[i])} onClick={() => void create()}>
          {working ? "Working on your idea…" : "Generate concept"}
        </Button>
        <p className="studio__note">Each generation or revision uses one daily run. Images can take a few minutes.</p>
      </section>
      <section className="studio__workspace" aria-labelledby="studio-draft">
        <div className="studio__workspace-head"><div><p className="studio__eyebrow">02 / EXPLORE & REFINE</p><h2 id="studio-draft">Your concept</h2></div>
          {current && <span className="studio__badge">{current.mode === "mock" ? "Mock preview" : "Generated image"}</span>}</div>
        {activeJob && <p className="studio__job" role="status">{activeJob.stage} · You can refresh or return while this runs.</p>}
        {!activeJob && jobs[0] && (jobs[0].status === "failed" || jobs[0].status === "interrupted") && <p className="studio__error" role="alert">{jobs[0].error}</p>}
        {error && <p className="studio__error" role="alert">{error}</p>}
        <div className="studio__canvas">{current ? <img src={absoluteUrl(current.imageUrl)} alt="Selected generated chimera concept" /> :
          <div><span aria-hidden="true">✳</span><p>Your first concept will appear here.</p><small>Describe your creature to begin.</small></div>}</div>
        {current && <>
          <p className="studio__instruction"><strong>{current.parentId ? "Revision" : "Your brief"}:</strong> {current.instruction}</p>
          {current.direction && <details><summary>See the collaborator’s direction</summary><p>{current.direction}</p></details>}
          <div className="studio__review">
            <h3>Creative review</h3>
            <p>Ask the collaborator to look at this version and suggest possible next steps. You decide what to change.</p>
            <Button size="sm" disabled={working} onClick={() => void askForReview()}>Review selected draft</Button>
            <p className="studio__note">A review uses one daily run. Visual observations can be mistaken.</p>
            {review && <div aria-live="polite"><p><strong>What the reviewer observed:</strong> {review.observation}</p>
              <p className="studio__suggestions"><strong>Ideas to consider:</strong>{"\n"}{review.suggestions}</p>
              <p className="studio__note">Choose the ideas you like and write or paste them into the revision field below.</p></div>}
          </div>
          <label htmlFor="studio-edit">What would you like to change?</label>
          <textarea id="studio-edit" className="text-input studio__textarea" rows={3} maxLength={2000} value={edit} disabled={working}
            placeholder="Make the spider legs longer, keeping the monkey's expression..." onChange={(e) => setEdit(e.target.value)} />
          <div className="studio__actions"><Button variant="primary" busy={working} disabled={working || !edit.trim()} onClick={() => void revise()}>Revise selected draft</Button>
            <a className="btn btn--secondary" href={absoluteUrl(current.imageUrl)} download target="_blank" rel="noreferrer">Open image</a></div>
          <p className="studio__note">Revisions use the selected image as their starting point. The model may change other details too.</p>
        </>}
        {versions.length > 0 && <div className="studio__history"><h3>Creative canvas</h3><p>Drag to arrange, zoom to explore, and select a version to review or branch from it.</p>
          <StudioCanvas versions={versions} selected={selected} onSelect={(id) => { if (!working) setSelected(id); }} />
          <div className="studio__versions" aria-label="Choose a version">
            {versions.map((v, i) => <button type="button" key={v.id} className={`studio__version${v.id === selected ? " is-selected" : ""}`} aria-pressed={v.id === selected} disabled={working} onClick={() => setSelected(v.id)}>
              <span>Version {i + 1}{v.parentId ? ` · from ${versions.findIndex((p) => p.id === v.parentId) + 1}` : " · concept"}</span>
            </button>)}
          </div>
        </div>}
      </section>
    </div>
  </div>;
}
