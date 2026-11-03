import { useState } from "react";
import { baseHeaders, request } from "../api/client";
import { Button } from "../ui/Button";

type Message = { role: "user" | "assistant"; content: string };
type Action = { type: "review" | "revise"; reason: string; instruction?: string };
type Answer = { message: string; action: Action | null };

export function StudioCollaborator({ versionId, disabled, onReview, onRevise }: {
  versionId: string; disabled: boolean; onReview: () => void; onRevise: (instruction: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [action, setAction] = useState<Action | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function send() {
    const content = input.trim();
    if (!content) return;
    const next: Message[] = [...messages, { role: "user" as const, content }].slice(-11);
    setMessages(next); setInput(""); setAction(null); setError(""); setLoading(true);
    try {
      const { data } = await request<Answer>(`/evo/studio/versions/${encodeURIComponent(versionId)}/collaborate`, {
        method: "POST", headers: baseHeaders({ "Content-Type": "application/json" }), body: JSON.stringify({ messages: next }),
      });
      setMessages((old) => [...old, { role: "assistant", content: data.message }]); setAction(data.action);
    } catch (e) { setError(e instanceof Error ? e.message : "The collaborator could not respond."); }
    finally { setLoading(false); }
  }
  return <section className="studio-collaborator" aria-label="Creative collaborator">
    <h3>Creative collaborator</h3>
    <p>Talk through this draft. The collaborator can propose a review or an editable revision; you choose whether to run it.</p>
    <p className="studio__note">Each message uses one daily run. The collaborator knows the brief and selected version’s instruction, but cannot see the image. Use visual review for observations.</p>
    {messages.length > 0 && <div className="studio-collaborator__messages" aria-live="polite">{messages.map((m, i) => <p key={i}><strong>{m.role === "user" ? "You" : "Collaborator"}:</strong> {m.content}</p>)}</div>}
    {error && <p className="studio__error" role="alert">{error}</p>}
    {action && <div className="studio-collaborator__action"><p><strong>Suggested {action.type}:</strong> {action.reason}</p>
      {action.type === "revise" && <><label htmlFor="collaborator-instruction">Revision instruction</label>
        <textarea id="collaborator-instruction" className="text-input studio__textarea" rows={3} maxLength={2000} value={action.instruction ?? ""} disabled={disabled || loading}
          onChange={(e) => setAction({ ...action, instruction: e.target.value })} />
        <Button variant="primary" size="sm" disabled={disabled || loading || !action.instruction?.trim()} onClick={() => onRevise(action.instruction!.trim())}>Run this revision</Button></>}
      {action.type === "review" && <Button size="sm" disabled={disabled || loading} onClick={onReview}>Review this draft</Button>}
    </div>}
    <label htmlFor="collaborator-message">Your message</label>
    <textarea id="collaborator-message" className="text-input studio__textarea" rows={2} maxLength={2000} value={input} disabled={disabled || loading}
      placeholder="What could we do to make the transition more organic?" onChange={(e) => setInput(e.target.value)} />
    <Button size="sm" busy={loading} disabled={disabled || loading || !input.trim()} onClick={() => void send()}>Ask collaborator</Button>
  </section>;
}
