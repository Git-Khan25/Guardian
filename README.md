# Contract Guardian

**Verify the promise, not the prose.**

There is no accessible way for a consumer or a business to verify — with
evidence, not trust — whether a website's real behavior matches what its
privacy policy promises. Policy summarizers make text readable but verify
nothing. Network monitors show raw traffic but can't connect it to any
specific promise.

Contract Guardian closes that gap: it extracts the concrete, checkable
claims from a site's privacy policy, captures the site's real network
traffic, classifies who it's actually talking to, and produces a
per-claim verdict — **confirmed / contradicted / unverifiable** — grounded
in the specific evidence from that scan. Nothing is asserted without the
domain-level evidence to back it up.

## How it works

```
fetch policy → extract claims → capture traffic → classify domains → generate verdict
```

1. **Policy Fetcher** — loads the target site with a headless browser
   (JS-rendered, not a bare HTTP GET) and locates its privacy policy via
   common URL patterns or a footer-link crawl.
2. **Claim Extractor** — pulls only concrete, checkable promises out of
   the policy text, force-fit to a strict JSON schema across six fixed
   categories. Vague marketing language ("we take your privacy
   seriously") is filtered out, both in the prompt and again in code.
3. **Traffic Capturer** — logs every outgoing request during page load
   plus a short idle window. **Domain-level only** — this never inspects
   encrypted payload contents, by design.
4. **Domain Classifier** — matches each domain against a bundled
   tracker/ad blocklist first (instant, explainable). Anything unresolved
   is sent to a small model for classification by domain name/metadata
   pattern. If no classification key is configured, the domain is
   explicitly marked `unknown` and that fallback is surfaced in the
   report, never silently dropped.
5. **Verdict Agent** — takes the claims list *and* the classified-domains
   list, both passed explicitly into the prompt as grounding context, and
   produces a verdict per claim. Every verdict returned is re-validated in
   code against the actual domains seen in that scan — if a verdict cites
   evidence that isn't real, it's downgraded to `unverifiable` rather than
   trusted blindly. If no reasoning-model key is configured, a
   deterministic rule-based fallback still produces fully
   evidence-grounded verdicts.

Every node degrades gracefully on failure — a soft error is logged to
`state["errors"]` and the pipeline continues with partial results rather
than crashing the scan.

## Product framing

- **Consumer**: paste a URL, see a Trust Score and the evidence behind it,
  shareable as a simple embeddable badge.
- **B2B procurement**: the same pipeline, run continuously against vendor
  sites, becomes a lightweight privacy-compliance monitor — flagging when
  a vendor's actual behavior drifts from what they contractually promised.

## Explicit scope boundaries

- Web/SaaS sites only — no mobile app scanning.
- Domain-level traffic capture only — never TLS payload inspection.
- No external calls inside the per-domain classification loop beyond the
  one classification call itself.
- No user accounts, no auth, no persistent database — flat JSON is enough
  for a stateless demo tool ("future work" in a real product).
- A single node failing never crashes the whole scan — it degrades to a
  partial result with an explicit "unavailable" state.

## Project structure

```
contract-guardian/
├── backend/
│   ├── main.py                    FastAPI app entrypoint
│   ├── api/routes.py              /scan, /scan/{id}/status, /scan/{id}/report, /demo/{app}, /health
│   ├── pipeline/
│   │   ├── policy_fetcher.py
│   │   ├── claim_extractor.py
│   │   ├── traffic_capturer.py    domain-level only
│   │   ├── domain_classifier.py   blocklist + extended pattern check
│   │   ├── verdict_agent.py       evidence-grounded
│   │   └── graph.py               pipeline wiring, per-node error handling
│   ├── models/schemas.py          Pydantic schemas for every structured output
│   ├── data/
│   │   ├── blocklist.json         bundled tracker/ad domain list
│   │   └── demo_scans/            3 pre-scanned demo reports
│   ├── Dockerfile
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/App.jsx                two screens via state, no router
│   ├── src/components/
│   │   ├── ScanInput.jsx
│   │   ├── PipelineProgress.jsx
│   │   ├── ReportCard.jsx
│   │   ├── TrustScoreBadge.jsx
│   │   └── PresetAppPicker.jsx
│   ├── src/api/client.js
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## Running it

### Quickest path — pre-scanned demo data (no API keys needed)

```bash
docker compose up --build
```

Then open **http://localhost:5173**, click one of the three preset exhibits
(ShopNest, Chatly, FitTrack), and the full report loads instantly from
bundled pre-scanned data — this is the default, reliable demo path.

The backend comes up on **http://localhost:8000** (`/health` for a quick
check).

### Enabling the live pipeline

1. Copy `backend/.env.example` → `backend/.env` and fill in:
   - `OPENAI_API_KEY` — powers claim extraction and verdict generation
   - `GEMINI_API_KEY` — powers the second-pass domain classifier
2. `docker compose up --build` again.
3. On the home screen, paste a live URL into the scan box and click
   **Open case**. This runs the real five-stage pipeline end-to-end.

Every key-gated node falls back gracefully if a key is missing — the app
never crashes for lack of credentials, it just returns fewer confirmed/
contradicted verdicts (more `unverifiable`) and a rule-based grounding pass
for the Verdict Agent.

### Running without Docker

```bash
# backend
cd backend
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000

# frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Demo script

1. Home screen → click a preset app → pipeline lights up all 5 stages in
   order (briefly animated, even though it's instant from cache — same UI
   path a live scan takes).
2. Report screen loads: Trust Score at top, hero contradiction highlighted
   if one exists.
3. Expand a **Contradicted** card → shows which domain, and whether it was
   classified via the static blocklist or the extended check.
4. Expand an **Unverifiable** card → the system doesn't force false
   confidence when evidence is inconclusive.
5. *(Bonus, only if rehearsed clean)* paste a live URL and let it run in
   front of an audience.

## Known limitations / future work

- No persistent database — scans live in memory for the process lifetime.
- No user accounts or auth.
- No mobile app scanning or TLS payload inspection (out of scope by
  design, not an oversight).
- No PDF/ToS document upload flow.
- Domain classification is name/metadata-pattern based, not a full
  behavioral traffic analysis.
- The bundled blocklist is a trimmed sample, not a full production-scale
  tracker list.
