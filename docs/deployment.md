# Deployment recommendation and operating guide

Lumen is prepared for a **single Docker web service on Render**, with FastAPI
serving the production Vite build. The browser and API share one origin; the
OpenAI key stays on the Python server. No deployment, purchase, account creation,
GitHub publication or external secret upload has been performed.

## Hosting comparison

Official documentation was retrieved on October 24–25, 2026. Prices are published
list prices, not an account-specific quote or a commitment to purchase.

| Option | Fit | Storage / reliability | Cost and decision |
|---|---|---|---|
| Render Docker, paid compute + disk | Full Python dependency support, normal long-lived process, background agent requests, managed HTTPS and secret environment variables | Mount `/app/runtime`; one instance and one worker. Disk survives restarts; deployment can interrupt a running review. | Published `0.5c-512mb` compute is **$7/month**; 1 GB SSD is **$0.25/month**. About **$7.25/month base**, before bandwidth/build overages, taxes and model use. Recommended live-demo candidate; validate actual memory on the host. |
| Render Free Docker | Same application and saved real review workflows | Spins down after **15 idle minutes**; restart can take **about one minute**. Local files are lost on spin-down/restart/redeploy. **No persistent disk**. | **750 free instance hours/workspace/month**, with bandwidth/build limits. Good free preview, but live AI must stay disabled with this SQLite design. Not an always-instant experience. |
| Railway Docker + volume | Compatible with the same container and long-running FastAPI process; secret variables and volume support | Persistent volume required at `/app/runtime`; one replica | Hobby has a **$5 monthly minimum with $5 included usage**; additional resource use is billed. Viable alternative, but estimate combined compute/storage and set platform spend controls. Free/trial allowances are limited; not a permanent free live-hosting assumption. |
| Vercel frontend / Python functions | React hosting and Python functions are supported | This implementation relies on a resident async worker and durable SQLite. Serverless execution/storage would require external job and database services. | Not selected for this implementation. Splitting hosting adds deployment, CORS, storage and lifecycle complexity without helping this demonstration. |

Sources:

- [Render web services](https://render.com/docs/web-services)
- [Render free-service limitations](https://render.com/docs/free)
- [Render persistent disks](https://render.com/docs/disks)
- [Render pricing](https://render.com/pricing)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
- [Railway plans](https://docs.railway.com/pricing/plans)
- [Railway volumes](https://docs.railway.com/reference/volumes)
- [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)

## Two prepared delivery modes

`render.yaml` is the **free preview** candidate: public browsing, live AI disabled,
no API key required. The professor can open the URL, explore three honestly
labeled saved real-agent reviews, validate CSV/XLSX packages, inspect evidence and
download reports. It does not pretend that a new AI review has run.

`render-live.yaml` is the **paid live-demo** candidate: persistent 1 GB disk,
server-side key, shared access code, and six live reviews per rolling 24 hours.
Browsing needs no account. Only starting a live review needs the owner's code.
The code should be given privately to the professor; never put it in the URL,
repository, screenshots, client build, or README. It is kept only in the open
review dialog's memory and sent in a request header.

Choose a mode and approve external publication (and paid hosting, if selected)
before executing any hosting setup. These files are reviewable configurations;
they have not been submitted to a hosting provider.

## Deployment steps after approval

1. Publish **only the contents of `Final Project`** to a dedicated repository.
   Review the staged files; do not publish the surrounding course workspace.
   The supplied Blueprints assume this project is the repository root. If using
   a monorepo instead, set `rootDir: Final Project` and select the Blueprint's
   path under that directory. Never include `.env`, `.venv`, `runtime`, or
   `node_modules`. The Docker context also uses an explicit allowlist.
2. Create a Render Docker web service using the selected Blueprint. Set
   `WEB_ORIGIN` to the exact HTTPS origin, e.g. `https://your-service.onrender.com`
   (no path). The service fails startup for unsafe public settings. Initially
   leave live AI disabled while checking the deployment.
3. For the approved live option, attach the disk to **`/app/runtime`**. Verify it
   exists before enabling live requests. The container initializes the mount's
   top directory and drops to UID/GID 10001 before running the server. Keep one
   instance and one Uvicorn worker. The SQLite ledger is not a distributed quota.
4. Enter `OPENAI_API_KEY` and a fresh random **16+ character `WEB_ACCESS_CODE`**
   through the host's secret-variable UI. `WEB_PUBLIC_MODE=true` is mandatory.
   Set `WEB_LIVE_ENABLED=true` only after the persistent disk and limits are
   verified. Configure any available OpenAI project-level spend limit
   separately; application token limits are not a dollar-billing cap.
5. Verify `/health`, the saved examples, upload validation, memo export, session
   isolation and a fresh live review. Test from an incognito window. Confirm the
   older `/reviews` endpoint returns 403 and a missing/wrong code cannot start AI.
6. Restart the service and confirm review history and admission counts survive.
   Check CPU/memory and logs during a real request. The published 512 MB candidate
   has not been load-tested on Render; upgrade only with owner approval if its
   memory is insufficient. A 2 GB plan currently lists at $25/month.
7. Share the URL and the private live-review code separately. Rehearse close to
   the demonstration. Turn off `WEB_LIVE_ENABLED` after assessment; saved examples
   remain usable. Do not redeploy during an active review.

## Abuse controls and boundaries

- Live public reviews require a code, an exact configured Origin, same-site
  browser requests and a session cookie. The cookie is random, HttpOnly,
  SameSite=Strict and Secure in public mode. It is not a user account.
- A persistent SQLite transaction reserves admission **before** any AI request:
  defaults are **6 total reviews / rolling 24 hours**, **2 / browser**, and **1
  concurrent review**. Failed/partial/interrupted reviews still count. Clearing
  cookies can evade the browser allowance, but cannot evade the global limit.
- All browser POSTs share an in-process **30/minute** throttle. This is a burst
  defense, not a durable account quota. Proxy/client IP headers are not trusted.
- Combined POST bodies are capped at **2 MB**, including multipart overhead;
  packages have exactly three files and at most **500 segments**. The numerical
  CLI's existing 5,000-row cap is unchanged. XLSX formulas are rejected and
  expanded archives are capped at 20 MB; XML uses `defusedxml`.
- The existing per-review ceilings remain: 12 requests (including retries), 6 per
  agent, 16 tools per agent, 3,600 completion tokens/request, 80,000 request bytes,
  180 seconds total and bounded narrative/tool output. The 80,000 reported-token
  stopping threshold can be crossed by the last request; it is not a prepaid
  token or dollar cap. Six admitted reviews allow at most 72 model requests under
  the default application request ceiling.
- `WEB_LIVE_ENABLED=false` is the immediate kill switch. Misconfigured public
  startup fails closed. No endpoint lets a browser change budgets or the model.
- Results are scoped to the owning browser. Guessing another review ID is
  insufficient. History contains only that browser's jobs. There is no public
  list of uploaded filings. Full traces are downloadable only by the owner;
  the three intentionally public examples contain exclusively synthetic data.
- Runtime web data is under `runtime/web/lumen.sqlite3`, with a default **24-hour
  retention**. Cleanup runs on reads/admissions and every 60 seconds while the
  application is running. Admissions retain a rolling 24-hour window independent
  of review retention. Temporary upload directories are removed after parsing.
  Host backups/snapshots have separate retention controlled by the host.
- A worker restart marks unfinished jobs interrupted on repository initialization.
  A job never silently resumes, repeats a model call, or returns invented success.
  Agent/provider failures returned by the controller retain deterministic results
  as a partial review; an abrupt process failure may leave no final result.
- HTML reports escape all source/model strings. React renders them as text.
  Security headers restrict scripts/frames, and API responses use `no-store`.
  The answer key and evaluation code are excluded from the container context.

This is bounded demonstration access, not a general public insurance platform.
Do not accept real policyholder/insurer data. A leaked code can consume the small
shared allowance or deny service until the allowance resets. Larger deployments
need real authentication, durable queue workers, centralized quotas, monitoring,
and a reviewed data-retention policy.

## Local / container fallback

The main README contains the tested Windows setup. Local execution is the reliable
fallback if hosting is not approved. Saved reviews work without a model key.

If Docker is available, from this project:

```powershell
docker compose build
docker compose up
```

Compose automatically reads a **project** `.env`. To use a parent `.env` when no
local file exists, explicitly select it: `docker compose --env-file ../.env up`.
Only `OPENAI_API_KEY` is passed into the container; the source `.env` is never
baked into the image. Use the normal Python fallback to exercise the application's
automatic root-then-parent dotenv selection. Do not run `docker compose config`
where its expanded environment would expose a secret.

**Verification limit:** Docker is not installed in this workspace, so the Linux
image build, container mount permissions and hosted smoke test have not been
executed. Local production-build browser tests and real agent integration passed.
Those container/host checks remain deployment acceptance steps after approval.
