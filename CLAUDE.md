# Ali HQ — فريج علي

A 16-bit pixel-art AI agent village where Ali's AI agents live and work. Ali is the Chief Human Officer.

## Ground rules

- **Local web app only**: `index.html` (inline CSS/JS), `state/tasks.json`, `agents/`, `outputs/`. No backend, no API keys, no paid image generation. All art is drawn in code.
- **Never** post, publish, send messages or emails, or spend money or credits without Ali's explicit yes. Emails are drafts only.
- **No new agents** without Ali's approval.
- **Ask before deleting files.**
- Always write **"UIC"** (Union of Investment Companies), never "GIC".

## Brands

Every brand house works like a full social media agency: strategy, content, copywriting, design, social media and performance. No PR.

## Rendering conventions

- Everything renders at a low internal resolution of 640x384 on an offscreen canvas using only integer `fillRect` "pixels", then scales to the screen by an integer factor with image smoothing off.
- Static scenery is drawn once to a background canvas; only dynamic things (sea, dhow, fountain, people, night lights) are redrawn each frame.
- Labels and name tags are crisp HTML text (not pixel text): English bold + Arabic in IBM Plex Sans Arabic.
- Day/night follows Kuwait time (Asia/Kuwait). `N` toggles night for testing.

## Run

```bash
python3 -m http.server 3000
```

Then open http://localhost:3000.

## Team structure

Each house has two people who split the six agency functions:
- **Director**: strategy and performance.
- **Worker**: content, copywriting, design and social media.

Agent ids follow `<house>-director` / `<house>-worker`; Rashed is `chief-of-staff`. Houses: `loud`, `tauro`, `bo3li`, `sage`, `lamaat`, `mf`, `dorek`.

## Agents (approved by Ali)

The 15 agent definitions live in `agents/<id>.md`. `.claude/agents` is a symlink to `agents/` so Claude Code can load them as subagents. They may only read, search and write files; they have no tools for posting, sending or spending.

When Ali writes `@<agent-id> ...` (usually a line pasted from the village):
- If the subagent with that id is available, hand the message to it.
- If it is not, read `agents/<agent-id>.md` and answer as that agent, following its rules.

Majlis meetings: for `@chief-of-staff run a majlis meeting with <ids> about: <topic> ...`, ask each listed director for a 3-line update and one blocker (in parallel), then give those updates to `chief-of-staff`, who writes the notes and action items to `outputs/meetings/`.

## Live state

`index.html` polls `state/tasks.json` every 4 seconds and shows LIVE when it loads (DEMO when it cannot). Keep the file valid JSON:

```json
{
  "updated": "ISO 8601 time",
  "agents": { "<agent-id>": { "status": "working | approval | done | idle", "task": "", "notes": [], "lastReply": "" } },
  "approvals": [ { "id": "TAU-1", "title": "", "house": "tauro", "agent": "tauro-director", "summary": "", "path": "outputs/tauro/file.md" } ],
  "outputs": [ { "house": "tauro", "title": "", "path": "outputs/tauro/file.md" } ],
  "board": [ { "item": "", "owner": "<agent-id>", "status": "working" } ]
}
```

Work files go in `outputs/<house>/`; meeting notes in `outputs/meetings/`.

## Privacy

The GitHub repository is public. Everything in `outputs/` (brand briefs, plans, drafts, meeting notes) stays out of git (see `.gitignore`) until Ali says otherwise. Never commit the brand book PDFs. Only the earlier village screenshots in `outputs/screenshots/` are tracked.

## Brand summary PDFs

Ali wants everything done for each brand summarised in a PDF. Each house keeps `outputs/<house>/summary.md` (brand in brief, what we did, current work, decisions waiting on Ali, next steps) and a rendered `outputs/<house>/<Brand>-summary.pdf`. After every milestone for a house (plan written, batch drafted, review done, approvals decided), update its `summary.md` and re-render the PDF: convert the markdown to HTML with IBM Plex Sans / IBM Plex Sans Arabic and print to A4 with Chromium (Playwright `page.pdf`). Then send Ali the new PDF.
