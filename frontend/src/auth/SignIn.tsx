import { useId, useState } from "react";
import { Button } from "../ui/Button";
import { Icon } from "../ui/Icon";
import { sendMagicLink, useAuth } from "./auth";

/** The Lab needs an account: your workspaces, creatures and edits are saved to it. */
export function SignIn() {
  const status = useAuth((s) => s.status);
  const error = useAuth((s) => s.error);
  const sentTo = useAuth((s) => s.linkSentTo);
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const fieldId = useId();

  const submit = async () => {
    setBusy(true);
    await sendMagicLink(email);
    setBusy(false);
  };

  return (
    <section className="signin" aria-labelledby="signin-title">
      <div className="signin__card">
        <p className="hero__kicker">CHIMERA LAB</p>
        <h1 id="signin-title">Sign in to create</h1>
        <p className="signin__lead">
          Your Lab is saved to your account: every creature, each edit and the path from the two animals to your final image. We email you a sign-in link; no password.
        </p>
        {status === "unavailable" ? (
          <p className="signin__error" role="alert">
            <Icon name="alert" size={14} /> {error}
          </p>
        ) : sentTo ? (
          <div className="signin__sent" role="status">
            <Icon name="check" size={16} />
            <p>
              Check <strong>{sentTo}</strong> for a sign-in link. Open it in this browser to come back to the Lab.
            </p>
            <Button size="sm" variant="ghost" onClick={() => useAuth.setState({ linkSentTo: null })}>
              Use another address
            </Button>
          </div>
        ) : (
          <form
            className="signin__form"
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
          >
            <label htmlFor={fieldId}>Email</label>
            <input id={fieldId} className="text-input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" />
            <Button type="submit" variant="primary" busy={busy} disabled={busy || !email.includes("@")}>
              Email me a sign-in link
            </Button>
            {error ? (
              <p className="signin__error" role="alert">
                {error}
              </p>
            ) : null}
          </form>
        )}
      </div>
    </section>
  );
}
