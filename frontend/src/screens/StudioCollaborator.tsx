import { useEffect, useRef, useState } from "react";
import { baseHeaders, request } from "../api/client";
import { Button } from "../ui/Button";

type Message = { role: "user" | "assistant"; content: string };
type Action = { type: "review" | "revise"; reason: string; instruction?: string };
type VisualReview = { observation: string; suggestions: string };
type Answer = { message: string; action: Action | null; review?: VisualReview | null; steps?: { tool: string; reason: string }[] };

function restore(versionId: string): { messages: Message[]; action: Action | null } {
  try {
    const value = JSON.parse(localStorage.getItem(`chimera.studio.chat.${versionId}`) || "{}");
    return { messages: Array.isArray(value.messages) ? value.messages.filter((m: Message) => (m.role === "user" || m.role === "assistant") && typeof m.content === "string").slice(-12) : [],
      action: value.action?.type === "revise" || value.action?.type === "review" ? value.action : null };
  } catch { return { messages: [], action: null }; }
}

export function StudioCollaborator({ versionId, hasReview, disabled, onReview, onRevise, onInspected, onBusyChange }: {
  versionId: string; hasReview: boolean; disabled: boolean; onReview: () => void; onRevise: (instruction: string) => void; onInspected: (review: VisualReview) => void; onBusyChange: (busy: boolean) => void;
}) {
  const [messages, setMessages] = useState<Message[]>(() => restore(versionId).messages);
  const [input, setInput] = useState("");
  const [action, setAction] = useState<Action | null>(() => restore(versionId).action);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(false);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; onBusyChange(false); }; }, [onBusyChange]);
  useEffect(() => { try { localStorage.setItem(`chimera.studio.chat.${versionId}`, JSON.stringify({ messages, action })); } catch { /* local storage is optional */ } }, [versionId, messages, action]);

  async function send() {
    const content = input.trim();
    if (!content) return;
    const next: Message[] = [...messages, { role: "user" as const, content }].slice(-11);
    setMessages(next); setInput(""); setAction(null); setError(""); setLoading(true); onBusyChange(true);
    try {
      const { data } = await request<Answer>(`/evo/studio/versions/${encodeURIComponent(versionId)}/collaborate`, {
        method: "POST", headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ messages: next }),
      });
      const description = data.action?.type === "revise" ? ` Suggested revision: ${data.action.instruction}` : data.action?.type === "review" ? " Suggested a visual review." : "";
      const steps = data.steps?.map((step) => `Inspected the selected draft: ${step.reason}`).join("\n") ?? "";
      const completed: Message[] = [...next, { role: "assistant", content: `${steps}${steps ? "\n" : ""}${data.message}${description}`.slice(0, 2000) }];
      // The request may finish after the creator leaves this draft. Keep its reply with the originating version.
      try { localStorage.setItem(`chimera.studio.chat.${versionId}`, JSON.stringify({ messages: completed, action: data.action })); } catch { /* storage is optional */ }
      if (mounted.current) { setMessages(completed); setAction(data.action); if (data.review) onInspected(data.review); }
    } catch (e) { if (mounted.current) setError(e instanceof Error ? e.message : "The collaborator could not respond."); }
    finally { if (mounted.current) { setLoading(false); onBusyChange(false); } }
  }
  return <section className="studio-collaborator" aria-label="Creative collaborator">
    <h3>Creative collaborator</h3>
    <p>Talk through this draft. The collaborator can inspect it and propose an editable revision; you choose whether to generate it.</p>
    <p className="studio__note">Each message uses one studio action and may make several model calls. {hasReview ? "The collaborator can use this draft’s saved visual review, which may be mistaken." : "Ask the collaborator to inspect the image, or run visual review below."} Conversation is saved in this browser.</p>
    {messages.length > 0 && <div className="studio-collaborator__messages" aria-live="polite">{messages.map((m, i) => <p key={i}><strong>{m.role === "user" ? "You" : "Collaborator"}:</strong> {m.content}</p>)}</div>}
    {error && <p className="studio__error" role="alert">{error}</p>}
    {action && <div className="studio-collaborator__action"><p><strong>Suggested {action.type}:</strong> {action.reason}</p>
      {action.type === "revise" && <><label htmlFor="collaborator-instruction">Revision instruction</label>
        <textarea id="collaborator-instruction" className="text-input studio__textarea" rows={3} maxLength={2000} value={action.instruction ?? ""} disabled={disabled || loading}
          onChange={(e) => setAction({ ...action, instruction: e.target.value })} />
        <Button variant="primary" size="sm" disabled={disabled || loading || !action.instruction?.trim()} onClick={() => { onRevise(action.instruction!.trim()); setAction(null); }}>Run this revision</Button></>}
      {action.type === "review" && <Button size="sm" disabled={disabled || loading} onClick={onReview}>Review this draft</Button>}
    </div>}
    <label htmlFor="collaborator-message">Your message</label>
    <textarea id="collaborator-message" className="text-input studio__textarea" rows={2} maxLength={2000} value={input} disabled={disabled || loading}
      placeholder="What could we do to make the transition more organic?" onChange={(e) => setInput(e.target.value)} />
    <Button size="sm" busy={loading} disabled={disabled || loading || !input.trim()} onClick={() => void send()}>Ask collaborator</Button>
  </section>;
}
