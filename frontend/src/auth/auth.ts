import { createClient, type Session, type SupabaseClient } from "@supabase/supabase-js";
import { create } from "zustand";
import { request, setAccessTokenProvider } from "../api/client";

/**
 * Sign-in with Supabase Auth (email magic link). The project URL and publishable key come from the backend
 * (GET /evo/config), so one .env configures both. Supabase keeps the session in this browser and refreshes the
 * access token; every API request sends it (api/client.ts), and the backend verifies it.
 */

export type AuthStatus = "loading" | "signed-out" | "signed-in" | "unavailable";

interface AuthState {
  status: AuthStatus;
  userId: string | null;
  email: string | null;
  /** The address a magic link was just sent to (shown until the user signs in). */
  linkSentTo: string | null;
  error: string | null;
}

export const useAuth = create<AuthState>()(() => ({
  status: "loading",
  userId: null,
  email: null,
  linkSentTo: null,
  error: null,
}));

interface PublicConfig {
  supabaseUrl: string | null;
  supabasePublishableKey: string | null;
  authConfigured: boolean;
}

let client: SupabaseClient | null = null;
let token: string | null = null;
let started: Promise<void> | null = null;

setAccessTokenProvider(() => token);

function apply(session: Session | null): void {
  token = session?.access_token ?? null;
  if (session) {
    useAuth.setState({ status: "signed-in", userId: session.user.id, email: session.user.email ?? null, linkSentTo: null, error: null });
  } else {
    useAuth.setState({ status: "signed-out", userId: null, email: null });
  }
}

/** Load the sign-in settings and the saved session (once). A callback from a magic link is completed here. */
export function initAuth(): Promise<void> {
  started ??= (async () => {
    try {
      const { data } = await request<PublicConfig>("/evo/config", { timeoutMs: 10000 });
      if (!data.authConfigured || !data.supabaseUrl || !data.supabasePublishableKey) {
        useAuth.setState({ status: "unavailable", error: "Sign-in is not configured on this server." });
        return;
      }
      client = createClient(data.supabaseUrl, data.supabasePublishableKey, {
        auth: { flowType: "pkce", persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, storageKey: "chimera.auth" },
      });
      client.auth.onAuthStateChange((_event, session) => apply(session));
      const { data: current } = await client.auth.getSession();
      apply(current.session);
    } catch {
      useAuth.setState({ status: "unavailable", error: "Couldn't reach the server to sign in. Check your connection and reload." });
    }
  })();
  return started;
}

/** Email a sign-in link that returns to the Lab. */
export async function sendMagicLink(email: string): Promise<boolean> {
  const address = email.trim();
  if (!client || !address) return false;
  useAuth.setState({ error: null });
  const redirect = `${window.location.origin}/?view=lab`;
  const { error } = await client.auth.signInWithOtp({ email: address, options: { emailRedirectTo: redirect, shouldCreateUser: true } });
  if (error) {
    useAuth.setState({ error: error.status === 429 ? "Too many sign-in emails for now. Wait a few minutes and try again." : error.message });
    return false;
  }
  useAuth.setState({ linkSentTo: address });
  return true;
}

export async function signOut(): Promise<void> {
  await client?.auth.signOut();
  apply(null);
}

/** Tests: set the session state directly (no Supabase client). */
export function setTestSession(user: { id: string; email: string } | null, accessToken = "test-token"): void {
  token = user ? accessToken : null;
  useAuth.setState(user ? { status: "signed-in", userId: user.id, email: user.email, linkSentTo: null, error: null } : { status: "signed-out", userId: null, email: null });
}
