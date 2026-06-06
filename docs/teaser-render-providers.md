# Teaser render providers

`/autonovel:teaser-render` turns shot prompts into actual clips. This page
is the canonical map of the backends, what each one costs, and how to give
it a key. Capabilities live as **data** in
`src/autonovel/teaser/providers.py` (a table, not logic) — this doc mirrors
that table in prose. Verified **2026-06-06**; the market moves fast, so
re-check before relying on a free tier.

> **Golden rule: prove the pipeline for free first.** The real backends
> have small free quotas (grok = 5 generations/day). Validate the whole
> render → cut-list → assemble chain with the offline **`stub`** provider
> (zero network, zero key, zero quota) before you spend a single real
> generation. `/autonovel:teaser-render` does this automatically on a
> fresh teaser.

## The matrix

| Provider | Role | Audio | Free tier | Card? | Key env | Scriptable |
|---|---|---|---|---|---|---|
| **`stub`** | **validate the pipeline** | — | offline placeholder keyframes, unlimited | no | — | yes (local Pillow) |
| **`grok`** | **default real video** | ✅ dialogue+music | 5 gens/day + $25 signup | **no** | `XAI_API_KEY` | yes |
| `kie` | multi-model backstop | ✅ | 80 credits, never expire | **no** | `KIE_API_KEY` | yes |
| `veo` | premium quality | ✅ | $300 GCP credit (Vertex) / paid API | card (not charged on trial) | `GEMINI_API_KEY` | yes |
| `magichour` | recurring free, **silent** | ❌ | 400 signup + 100/day forever | **no** | `MAGICHOUR_API_KEY` | yes |
| `fal` | one-time burst | model-dependent | $20 one-time | no | `FAL_KEY` | yes |
| `flow` | highest quality, **manual** | ✅ | 1,000 credits/mo on AI Pro | (your sub) | — | **no — GUI only** |
| `pollinations` | **image keyframes only** | n/a | free `flux` images | no | `POLLINATIONS_TOKEN` | yes |

`grok` is the default **video** provider; `pollinations` is the default
**image/keyframe** provider (`resolve-image-provider`). Pollinations no
longer offers free video — its free path is `flux` keyframe images, and
even those now need a free account token.

## Giving a backend its key

Resolution order (highest wins): `--token <key>` → the provider's env var
→ a project-local `.env`. Put keys in **`.env`** at the series root — it is
gitignored and never committed:

```bash
# .env  (series root — gitignored)
XAI_API_KEY=xai-...            # grok (default) — free at https://x.ai
# KIE_API_KEY=...              # kie.ai — 80 free credits, no card
# GEMINI_API_KEY=...           # veo via Gemini API
# MAGICHOUR_API_KEY=...        # magichour.ai — 100/day, silent
# FAL_KEY=...                  # fal.ai — $20 one-time
# POLLINATIONS_TOKEN=...       # pollinations flux keyframes
```

Where to get a free key:

- **grok** — https://x.ai → API keys. Free tier is 5 generations/day plus a
  $25 signup credit; no credit card. (The optional $150/mo data-sharing
  tier is **not** available in the EU/UK.)
- **kie** — https://kie.ai → 80 free credits on signup, never expire, no
  card; one key fronts Veo 3 / Kling 2.6 / Grok / Seedance, all with audio.
- **veo** — https://aistudio.google.com/apikey for the Gemini API key
  (paid per second; audio is native). The **$300 Google Cloud welcome
  credit** is *new-account only* and applies **only on the Vertex AI path**
  (gcloud ADC), **not** the AI-Studio API-key path — see "Veo on the $300
  credit" below.
- **magichour** — https://magichour.ai → 100 free credits/day forever, no
  card. Output is **silent**; layer a music bed in
  `/autonovel:teaser-assemble` (`--audio`).
- **fal** — https://fal.ai → $20 one-time signup credit (no card to start).
- **pollinations** — https://auth.pollinations.ai for a free account token.

## The `flow` manual path (Google AI Pro)

Flow (labs.google/flow) gives the highest quality with native
dialogue+music, but it is **GUI-only — there is no API**, so the pipeline
cannot drive it. Use it by hand:

1. `--provider flow` prints the instructions (no HTTP call is made).
2. Render each shot in Flow. On **AI Pro** ($19.99/mo) you get **1,000
   Flow credits/month** ≈ **fifty 8-second Veo 3.1 Fast clips** (or ~ten
   Quality clips). Credits do **not** roll over; Pro output carries a
   visible "Veo" badge.
3. Export each clip and drop it in `books/<book>/teaser/clips/` as
   `shot_<id>.mp4`.
4. `/autonovel:teaser-assemble --book <book>` stitches whatever is on disk.

## Veo on the $300 GCP credit (scriptable, top quality, free-ish)

The $300 Google Cloud welcome credit (90 days, new billing accounts only —
a card is required as a hold but not charged) covers Veo **only via Vertex
AI**, not the AI-Studio Gemini API key. At 720p with audio that is roughly
**50 min (Veo 3.1 Fast) to 12 min (Quality)** — far beyond a 30–180 s
trailer. Eligibility is murky if you have ever had a Cloud billing account.
This adapter drives the **Gemini API-key** path (`GEMINI_API_KEY`); the
Vertex/ADC path for the $300 credit is best done manually with `gcloud` —
documented here as a known follow-up, not yet wired into `teaser-render`.

## Rate limiting & retries

Each backend has a polite default inter-request interval
(`providers.py :: min_interval_s`); override with `--delay <s>`. Transient
`429`/`503` responses are retried with bounded exponential backoff that
honours `Retry-After` (`--max-retries`, default 4). A terminal `402`
(payment) or `401/403` (auth) stops the batch immediately with one
actionable message instead of failing every shot identically.

## Assembly needs ffmpeg

`/autonovel:teaser-assemble` (and the real clip stitch) require **ffmpeg**
on `PATH`. `autonovel doctor` warns if it is missing; install via
`apt install ffmpeg` / `brew install ffmpeg` or
`autonovel install-export-tools`. The offline `stub` render does **not**
need ffmpeg to produce keyframes, but assembling them into a video does.
