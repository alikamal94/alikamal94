# Tauro Marketing AI Agent Team

The build from the Tauro build spec (27 Sep 2026) and the KNINV agent map. Eight agents plan, write, design and
check Tauro's Arabic-first posts. **Nothing publishes without Ali's tap on Telegram.**

This is **Phase 0 (foundations) + the Phase 1 core team (agents 1–5)**. Phase 0 is done when a test post renders correctly from a hand-written brief: `samples/` holds a hand-written brief for each of the 7 templates, and `docs/previews/` shows what they render to.

## What's built

| # | Agent | File | How it works |
|---|-------|------|--------------|
| 1 | Market Intelligence & News | `tauro/agents/market_intel.py` | Claude + web search. Big-move check (e.g. gold ±1% in 4h) is plain code on price data |
| 2 | Content Strategist | `tauro/agents/strategist.py` | Claude Opus 5.5 → daily plan + one brief JSON per post |
| 3 | Design Agent | `tauro/agents/designer.py` | Deterministic: HTML/CSS templates → PNG with headless Chromium; chart drawn in code |
| 4 | Arabic Copywriter | `tauro/agents/copywriter.py` | Claude Sonnet 5.5, Kuwaiti dialect, voice + compliance files in the prompt |
| 5 | Compliance & Brand QA | `tauro/agents/qa.py` + `tauro/qa_rules.py` | Code checks hard rules first; Claude Opus 5.5 looks at the rendered image for the rest |
| — | Orchestrator | `tauro/orchestrator.py` | Plain code: schedule (Kuwait time), handoffs, retries (max 2, then Ali), logs |
| — | Approval bot | `tauro/telegram_bot.py` | Approve / Edit / Reject buttons; only Ali + backup approver |

Agents 6–8 (Publisher, Analytics, Competitor Watch) are Phases 2–3 and not built yet. The kill switch is already in place
(`python -m tauro kill`) and the Publisher will check it before every publish.

**Guardrails in code:** structured JSON validated at every handoff · every prompt, output, QA verdict and approval logged
(`out/tauro.db`) · sample price data is stamped "SAMPLE DATA" and QA always blocks it · offers blocked until listed in
`knowledge/brand_facts.md` · re-running a brief never sends it twice.

## The 7 templates

`news_card` · `gold_chart` · `calendar_card` · `edu_carousel` (cover → 4 slides → red CTA) · `tip_card` · `workshop_promo` · `poll_card`.
Each one follows the brand guide: Cairo font, right-to-left Arabic with Arabic-Indic digits, reversed logo top right, red rule under the headline, one red CTA strip, and the handle and risk line in the footer. Backgrounds follow the grid: dark for analysis and education, white for trust, red for promo.

## Run it on your laptop

You need Python 3.11+.

```bash
cd tauro-agents
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env                                     # then fill in the keys

python -m pytest                                          # 31 tests, no API keys needed
python -m tauro render samples/*.json                     # PNGs → out/renders/
python -m tauro qa-check samples/*.json                   # code-level QA rules
```

With `ANTHROPIC_API_KEY` set:

```bash
python -m tauro run morning      # one batch now: brief → plan → copy → design → QA → approval
python -m tauro bot              # Telegram approval bot (needs TELEGRAM_BOT_TOKEN)
python -m tauro schedule         # the daily schedule, Kuwait time, until stopped
python -m tauro kill             # pause all publishing   (--off to resume)
```

Until the Telegram token is set, approval cards are written to `out/approvals/` instead.

**Telegram setup:** create a bot with @BotFather, put the token in `.env`, run `python -m tauro bot`, and send the bot any
message. It replies with your chat id, which goes in `TELEGRAM_APPROVER_CHAT_ID`.

## Daily schedule (Kuwait time)

06:00 Market Brief · 07:00 morning batch (plan → copy → design → QA → Telegram, ready for the 09:15 window) ·
12:00 midday update · 14:00 afternoon batch (ready for 14:45) · every 30 min 06:15–21:45 breaking-news scan
(a breaking item fast-tracks one reactive post) · every 5 min: Ali's edit notes go back to the makers.

## Knowledge base (`knowledge/`)

Every agent reads these before it works. Ali owns them. Items marked `TODO(Ali)` still need input:

- **Instagram handle:** the spec says `@tauromarketsme`, the brand guide says `@tauromarkets_me`. The code currently uses the brand guide's spelling.
- **Risk disclaimer:** the exact wording, and which regulator applies (needs compliance counsel).
- **Approved offers:** none yet, so QA blocks every offer.
- **Gold levels:** your current H4 zones.
- **Voice guide:** about 20 sample captions you've approved.
- **Competitors:** the handles to monitor.

## Not done yet / needs from Tauro

- **Logo:** `assets/logo/` holds low-res extracts from the brand-guide PDF. Replace them with the original PNG files.
- **Price feed:** the MT5 feed is coded (`tauro/data/prices.py`) but untested. It needs an MT5 investor login on a Windows host.
- **Canva:** edit links are not built yet. They need the Canva plan / Connect API confirmed.
- **Database:** the code uses SQLite for now. The tables move to Postgres for production.
- **Deployment:** an always-on server (e.g. a DigitalOcean droplet) running `schedule` and `bot`.
