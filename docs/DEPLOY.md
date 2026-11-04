# Deploying Chimera Lab (Modal) and CI/CD

One Modal app serves everything: the built site at `/` and the API under `/evo` (one URL, no CORS setup).

```
push to any branch / pull request ──► CI: backend ruff + pytest (Python 3.11), frontend tsc + vitest + CSS rules + build
push to main ──► Deploy: the same checks, then build the site and `modal deploy backend/app/modal_app.py`
```

- `.github/workflows/ci.yml`: checks only; needs no secrets (the tests use fakes and never call a paid model).
- `.github/workflows/deploy.yml`: production. One deploy at a time; "Run workflow" in the Actions tab redeploys
  `main` by hand. A deploy restarts the container, so a Fusion or card running at that moment is marked interrupted
  and can be run again.

## One-time setup

1. **Modal secret with the app's settings.** The deployed app reads a Modal secret named `chimera-lab`, never `.env`.
   From the repo root, make a copy of `.env` without the deploy tokens and the database password, then upload it:

   ```bash
   grep -v -E '^\s*(MODAL_|SUPABASE_DB_URL)' .env > .env.modal     # .env.modal is git-ignored
   modal secret create chimera-lab --from-dotenv .env.modal --force
   ```

   Run the same two lines whenever a key or setting changes, then redeploy ("Run workflow").

2. **GitHub secrets for the deploy job** (repo Settings > Secrets and variables > Actions > New repository secret):
   `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`. With the GitHub CLI:

   ```bash
   gh secret set MODAL_TOKEN_ID      # paste the value when asked
   gh secret set MODAL_TOKEN_SECRET
   ```

3. **First deploy** (from your machine, or by merging to `main`):

   ```bash
   cd frontend && npm ci && npm run build && cd ..
   modal deploy backend/app/modal_app.py      # prints the app's URL
   ```

4. **Production URL** (lets the deploy job check the site after each deploy):
   `gh variable set PRODUCTION_URL --body "https://<workspace>--chimera-lab-fastapi-app.modal.run"`

5. **Supabase sign-in** (Authentication > URL Configuration): set the **Site URL** to the production URL and add
   `<production URL>/**` to the **Redirect URLs**. Without this, sign-in links lead to localhost.

6. **Email for friends** (Authentication > Emails > SMTP settings): Supabase's built-in email only delivers to your
   own project team's addresses, a few per hour. To let friends sign in, connect an SMTP provider (Resend, Postmark,
   SendGrid, Amazon SES and others have free tiers).

## Settings worth reviewing for a public link

- `EVO_LIMITS_ENABLED`: `false` means anyone signed in can run Fusions and edits without a cap, on your Meta key.
  `true` turns on the daily caps (`EVO_VISITOR_DAILY_RUNS`, `LAB_USER_DAILY_ACTIONS`, ...); raise them as needed.
- The container is kept warm around the clock (`min_containers=1`): runs and jobs live in the web process, so it
  costs a small always-on container. Moving jobs to Modal functions removes this limit (the next step).

## Checking a deploy

- `modal app logs chimera-lab` streams the server's logs.
- `<production URL>/health` answers `{"status":"ok"}`.
- Roll back: redeploy an earlier commit (check it out, build, `modal deploy`), or revert the commit on `main`.
