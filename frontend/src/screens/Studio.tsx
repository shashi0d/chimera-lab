import { useEffect, useRef, useState } from "react";
import { absoluteUrl, baseHeaders, parseError, request } from "../api/client";
import { Button } from "../ui/Button";
import { StudioCanvas, type StudioVersion as Version } from "./StudioCanvas";
import { RegionEditor } from "./RegionEditor";
import { StudioCollaborator } from "./StudioCollaborator";
import { groupProjects, projectId } from "./studioProjects";

type Review = { observation: string; suggestions: string };
type Job = { id: string; operation: string; status: string; stage: string; result: Version | null; error: string | null };
type StudioLimits = { used: number; limit: number; totalUsed: number; totalLimit: number };
const STORAGE = "chimera.studio.versions.v1";
const SELECTED = "chimera.studio.selected.v1";
const PROJECT_SELECTIONS = "chimera.studio.project-selections.v1";

function restore(): Version[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(STORAGE) || "[]");
    return Array.isArray(value) ? value.filter((v): v is Version => typeof v?.id === "string" && typeof v?.imageUrl === "string") : [];
  } catch { return []; }
}

function remembered(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(PROJECT_SELECTIONS) || "{}"); } catch { return {}; }
}

export function Studio() {
  const [names, setNames] = useState(["", ""]);
  const [files, setFiles] = useState<Array<File | null>>([null, null]);
  const [brief, setBrief] = useState("");
  const [edit, setEdit] = useState("");
  const [versions, setVersions] = useState<Version[]>(restore);
  const [selected, setSelected] = useState<string | null>(() => {
    try { return localStorage.getItem(SELECTED) || restore().at(-1)?.id || null; } catch { return restore().at(-1)?.id ?? null; }
  });
  const [hydrated, setHydrated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [limits, setLimits] = useState<StudioLimits | null>(null);
  const known = useRef(new Set(restore().map((v) => v.id)));
  const [review, setReview] = useState<Review | null>(null);
  const [regionOpen, setRegionOpen] = useState(false);
  const [compareId, setCompareId] = useState("");
  const [useSources, setUseSources] = useState(false);
  const [error, setError] = useState("");
  const current = versions.find((v) => v.id === selected);
  const selectedRef = useRef(selected);
  selectedRef.current = selected;
  const projects = groupProjects(versions);
  const currentProject = current ? projectId(current, versions) : null;
  const projectVersions = projects.find((project) => project.id === currentProject)?.versions ?? [];
  const compared = projectVersions.find((v) => v.id === compareId && v.id !== selected);
  const root = currentProject ? versions.find((v) => v.id === currentProject) : undefined;
  const hasSources = Boolean(root?.sources?.some((source) => source.hasImage));
  const activeJob = jobs.find((job) => job.status === "queued" || job.status === "running");
  const working = busy || Boolean(activeJob) || !hydrated;

  useEffect(() => { try { localStorage.setItem(STORAGE, JSON.stringify(versions)); } catch { /* storage may be unavailable */ } }, [versions]);
  useEffect(() => {
    if (!current || !currentProject) return;
    try { const selections = remembered(); selections[currentProject] = current.id; localStorage.setItem(PROJECT_SELECTIONS, JSON.stringify(selections)); localStorage.setItem(SELECTED, current.id); } catch { /* storage is optional */ }
  }, [current?.id, currentProject]);
  useEffect(() => {
    let cancelled = false;
    const refresh = () => void request<StudioLimits>("/evo/studio/limits", { headers: baseHeaders() })
      .then(({ data }) => { if (!cancelled) setLimits(data); }).catch(() => { /* quota is displayed when available */ });
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => { cancelled = true; clearInterval(timer); };
  }, [busy, activeJob?.status]);
  useEffect(() => {
    let cancelled = false;
    void request<{ versions: Version[] }>("/evo/studio/versions", { headers: baseHeaders() }).then(({ data }) => {
      if (cancelled) return;
      known.current = new Set(data.versions.map((v) => v.id));
      setVersions(data.versions);
      setSelected((old) => data.versions.some((v) => v.id === old) ? old : data.versions.at(-1)?.id ?? null);
    }).catch(() => { /* Keep the local copy available when offline. */ }).finally(() => { if (!cancelled) setHydrated(true); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    if (!hydrated) return;
    let cancelled = false;
    setReview(null);
    setUseSources(false);
    if (selected) void request<{ review: Review | null }>(`/evo/studio/versions/${encodeURIComponent(selected)}/review`, { headers: baseHeaders() })
      .then(({ data }) => { if (!cancelled) setReview(data.review); }).catch(() => { /* review is optional */ });
    return () => { cancelled = true; };
  }, [selected, hydrated]);

  useEffect(() => {
    if (!hydrated) return;
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
  }, [hydrated]);

  function selectProject(id: string) {
    const group = projects.find((project) => project.id === id);
    if (!group) return;
    const last = remembered()[id];
    setSelected(group.versions.find((version) => version.id === last)?.id ?? group.versions.at(-1)?.id ?? null);
    setCompareId(""); setRegionOpen(false);
  }

  function versionLabel(version: Version): string {
    const n = projectVersions.findIndex((item) => item.id === version.id) + 1;
    return `Version ${n}${version.isFinal ? " · final" : ""}`;
  }

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
  async function revise(instruction: string = edit) {
    if (!current) return;
    setBusy(true); setError("");
    try {
      const { data } = await request<Job>(`/evo/studio/versions/${encodeURIComponent(current.id)}/revise?background=1`, {
        method: "POST", headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ instruction, useSources }),
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
  async function editRegion(mask: Blob, instruction: string) {
    if (!current) return;
    setBusy(true); setError("");
    try {
      const form = new FormData(); form.append("mask", mask, "mask.png"); form.append("instruction", instruction);
      const { data } = await request<Job>(`/evo/studio/versions/${encodeURIComponent(current.id)}/region?background=1`, { method: "POST", headers: baseHeaders(), body: form });
      setJobs((old) => [data, ...old.filter((job) => job.id !== data.id)]); setRegionOpen(false);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not start the painted edit."); }
    finally { setBusy(false); }
  }
  async function setFinal(isFinal: boolean) {
    if (!current) return;
    setBusy(true); setError("");
    try {
      await request(`/evo/studio/versions/${encodeURIComponent(current.id)}/final`, { method: "PUT",
        headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ isFinal }) });
      setVersions((old) => old.map((v) => v.id === current.id ? { ...v, isFinal } : v));
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update the final choice."); }
    finally { setBusy(false); }
  }
  async function download() {
    if (!current) return;
    setBusy(true); setError("");
    try {
      const response = await fetch(absoluteUrl(`/evo/studio/versions/${encodeURIComponent(current.id)}/download`), { headers: baseHeaders() });
      if (!response.ok) throw await parseError(response);
      const blob = await response.blob(), url = URL.createObjectURL(blob);
      const ext = blob.type === "image/png" ? "png" : blob.type === "image/jpeg" ? "jpg" : "webp";
      const anchor = document.createElement("a"); anchor.href = url; anchor.download = `chimera-${current.id}.${ext}`;
      document.body.appendChild(anchor); anchor.click(); anchor.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not download this image."); }
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
        <p>Give each animal a name, an image, or both. Reference images are sent to the model and saved privately with the concept.</p>
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
        <p className="studio__note">Each generation, revision, review or collaborator message uses one studio action. Images can take a few minutes.
          {limits ? ` ${Math.max(0, limits.limit - limits.used)} of ${limits.limit} personal actions remain today; ${Math.max(0, limits.totalLimit - limits.totalUsed)} remain for the workspace. Resets at 00:00 UTC.` : ""}</p>
      </section>
      <section className="studio__board" aria-labelledby="studio-board-title">
        <div className="studio__board-head"><div><p className="studio__eyebrow">02 / YOUR CREATIVE CANVAS</p><h2 id="studio-board-title">Explore your ideas</h2></div>
          <span className="studio__badge">{projectVersions.length} {projectVersions.length === 1 ? "version" : "versions"}</span></div>
        {projects.length > 1 && <><label htmlFor="studio-project">Creature idea</label>
          <select id="studio-project" className="text-input studio__project-select" value={currentProject ?? ""} disabled={working} onChange={(event) => selectProject(event.target.value)}>
            {projects.map((project, index) => {
              const concept = project.versions.find((v) => v.id === project.id) ?? project.versions[0]!;
              const title = concept.sources?.map((source) => source.name).join(" × ") || concept.instruction;
              return <option key={project.id} value={project.id}>{`Idea ${index + 1} · ${title.slice(0, 65)}`}</option>;
            })}
          </select></>}
        <p className="studio__board-help">Select a version to work on it. Drag cards to arrange your ideas and zoom to explore branches.</p>
        {projectVersions.length > 0 ? <>
          <StudioCanvas key={currentProject} versions={projectVersions} selected={selected} onSelect={(id) => { if (!working) setSelected(id); }} />
          <div className="studio__versions" aria-label="Choose a version">
            {projectVersions.map((v, i) => <button type="button" key={v.id} className={`studio__version${v.id === selected ? " is-selected" : ""}`} aria-pressed={v.id === selected} disabled={working} onClick={() => setSelected(v.id)}>
              <span>Version {i + 1}{v.parentId ? ` · from ${projectVersions.findIndex((p) => p.id === v.parentId) + 1}` : " · concept"}{v.isFinal ? " · final" : ""}</span>
            </button>)}
          </div>
          {current && projectVersions.length > 1 && <div className="studio__compare">
            <label htmlFor="compare-version">Compare selected draft with</label>
            <select id="compare-version" className="text-input" value={compared?.id ?? ""} onChange={(event) => setCompareId(event.target.value)}>
              <option value="">Choose another version</option>
              {projectVersions.map((v) => v.id !== current.id && <option key={v.id} value={v.id}>{versionLabel(v)}</option>)}
            </select>
            {compared && <div className="studio__compare-images"><figure><img src={absoluteUrl(current.imageUrl)} alt="Selected draft for comparison" /><figcaption>Selected · {versionLabel(current)}</figcaption></figure>
              <figure><img src={absoluteUrl(compared.imageUrl)} alt="Comparison draft" /><figcaption>{versionLabel(compared)}</figcaption></figure></div>}
          </div>}
        </> : <div className="studio__board-empty"><span aria-hidden="true">✳</span><h3>Your canvas starts with an idea</h3><p>Describe your creature and generate a concept. Each new version will grow from the one you choose.</p></div>}
      </section>
      <section className="studio__workspace" aria-labelledby="studio-draft">
        <div className="studio__workspace-head"><div><p className="studio__eyebrow">03 / CREATE & REFINE</p><h2 id="studio-draft">Selected draft</h2></div>
          {current && <span className="studio__badge">{current.mode === "mock" ? "Mock preview" : "Generated image"}</span>}</div>
        {activeJob && <p className="studio__job" role="status">{activeJob.stage} · You can refresh or return while this runs.</p>}
        {!activeJob && jobs[0] && (jobs[0].status === "failed" || jobs[0].status === "interrupted") && <p className="studio__error" role="alert">{jobs[0].error}</p>}
        {error && <p className="studio__error" role="alert">{error}</p>}
        <div className="studio__canvas">{current ? <img src={absoluteUrl(current.imageUrl)} alt="Selected generated chimera concept" /> :
          <div><span aria-hidden="true">✳</span><p>Your first concept will appear here.</p><small>Describe your creature to begin.</small></div>}</div>
        {current && <>
          <p className="studio__instruction"><strong>{current.parentId ? "Revision" : "Your brief"}:</strong> {current.instruction}</p>
          <div className="studio__actions"><Button size="sm" disabled={working} onClick={() => void setFinal(!current.isFinal)}>{current.isFinal ? "Remove final mark" : "Mark as final"}</Button>
            <Button size="sm" disabled={working} onClick={() => void download()}>Download image</Button></div>
          {current.isFinal && <p className="studio__note">You marked this version as a final choice. You can continue editing or change your mind.</p>}
          {current.direction && <details><summary>See the collaborator’s direction</summary><p>{current.direction}</p></details>}
          <StudioCollaborator key={current.id} versionId={current.id} hasReview={Boolean(review)} disabled={working} onReview={() => void askForReview()} onBusyChange={setBusy}
            onInspected={(result) => { if (selectedRef.current === current.id) setReview(result); }} onRevise={(instruction) => void revise(instruction)} />
          <div className="studio__review">
            <h3>Creative review</h3>
            <p>Ask the collaborator to look at this version and suggest possible next steps. You decide what to change.</p>
            <Button size="sm" disabled={working} onClick={() => void askForReview()}>Review selected draft</Button>
            <p className="studio__note">A review uses one studio action. Visual observations can be mistaken.</p>
            {review && <div aria-live="polite"><p><strong>What the reviewer observed:</strong> {review.observation}</p>
              <p className="studio__suggestions"><strong>Ideas to consider:</strong>{"\n"}{review.suggestions}</p>
              <p className="studio__note">Choose the ideas you like and write or paste them into the revision field below.</p></div>}
          </div>
          <label htmlFor="studio-edit">What would you like to change?</label>
          {hasSources && <label className="studio__source-toggle"><input type="checkbox" checked={useSources} disabled={working} onChange={(event) => setUseSources(event.target.checked)} /> Include original animal images in the next revision</label>}
          {hasSources && useSources && <p className="studio__note">The selected draft and source images will be sent as references. This can change the composition more than a chained edit.</p>}
          <textarea id="studio-edit" className="text-input studio__textarea" rows={3} maxLength={2000} value={edit} disabled={working}
            placeholder="Make the spider legs longer, keeping the monkey's expression..." onChange={(e) => setEdit(e.target.value)} />
          <div className="studio__actions"><Button variant="primary" busy={working} disabled={working || !edit.trim()} onClick={() => void revise()}>Revise selected draft</Button>
            <Button disabled={working} onClick={() => setRegionOpen((open) => !open)}>{regionOpen ? "Close painted edit" : "Paint an area to edit"}</Button></div>
          <p className="studio__note">Revisions use the selected image as their starting point. The model may change other details too.</p>
          {regionOpen && <RegionEditor key={current.id} imageUrl={current.imageUrl} disabled={working} onSubmit={(mask, instruction) => void editRegion(mask, instruction)} />}
        </>}
      </section>
    </div>
  </div>;
}
