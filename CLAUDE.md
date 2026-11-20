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
