<div align="center">

# 🤖 Free Multi-Agent AI Council for macOS

### JARVIS: one chat, a whole AI team

**A free, open-source multi-agent AI app for your Mac.**
One chat orchestrates Claude Code, Codex and Gemini agents as a council.

![Platform](https://img.shields.io/badge/platform-macOS%2014%2B-black?logo=apple)
![Version](https://img.shields.io/badge/version-0.7.4-4cc9f0)
![Tests](https://img.shields.io/badge/tests-118%20passing-2ea44f)
![Python](https://img.shields.io/badge/python-stdlib%20only-3776ab?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)
![Price](https://img.shields.io/badge/price-free-2ea44f)

</div>

---

## ✨ What is this?

A **free, open-source** native Mac app (Swift shell around a Python standard-library server on `127.0.0.1` and a plain JS front end) that puts an AI council behind **one chat**. The app itself costs nothing (MIT), has no paid API fallback, and uses the official CLIs of the subscriptions or free tiers you already have. You talk to the coordinator (JARVIS); it routes work to the right specialist, and you can call any agent by name in the same conversation. Model calls go through the official CLIs of the providers you sign in with (Claude Code, Codex, Antigravity/Gemini).

## 🧑‍🤝‍🧑 The team

| Agent | Engine | Role |
|---|---|---|
| **JARVIS** | Gemini | Coordinator: plans, hands work off, answers simple questions itself |
| **VISION** | Claude Code (your own Claude sign-in) | Lead developer, pure code |
| **FRIDAY** | Codex (ChatGPT) | Helper developer, research, tests, and image reading |
| **EDITH** | Gemini | Researcher / designer |

## 🧠 What it can do in v0.7.4

- **Agents in the same chat.** `VISION, come here`, `Call EDITH and FRIDAY`: the called agent answers under its own name and sees the latest conversation. Several agents speak in turn; each sees the previous reply.
- **JARVIS delegates by itself.** It ends a reply with a hidden `HANDOFF: NAME: task` line and the app calls that agent in the same chat. At most 2 handoffs per turn, an agent never speaks twice, agents out of quota or switched off are skipped, and the chain stops if you change chats. Can be switched off in settings.
- **Simple code requests go straight to a coding agent** (VISION first, then Codex, then Antigravity Claude, skipping agents that are out of quota), so no Gemini call is wasted.
- **Effort grading.** JARVIS rates a job `low / medium / high` and the called agent thinks only that hard.
- **Team charter.** Every prompt starts with the same short charter, so every agent knows who does what without being taught.
- **Permission levels.** The permission menu has **Full access · Turbo**: file edits **and** allow-listed test commands (unittest, pytest, npm test…) in the connected folder run without asking, with the network off. Computer control still asks every single time. Approval cards offer "Always allow in this chat" (not for computer actions).
- **Photos and videos.** Attach with the paperclip, drag-and-drop or paste. Photos shrink to 1600 px JPEG; a video becomes one timestamped contact sheet of up to 6 frames (the video file never leaves your Mac).
- **Coordinator-led image reading.** You hand the image to JARVIS; it reads it directly (Gemini, via a temporary file that is deleted after the turn) or passes it to the one agent that can read it. That agent starts with a `Visual note:` so teammates who cannot see images can work from it. A bundled self-test image checks once per version who can really see.
- **Working-agents bubble.** Above the input you see who is working, what they are doing (thinking, writing, working in the project, researching, using the computer), a short summary and the elapsed seconds.
- **Mac permission status** in the permission menu (Screen Recording, Accessibility) with a request button. macOS still asks *you*; JARVIS cannot grant permissions itself.
- **Honest quota cards** for each agent; unknown stays unknown, with no invented percentages.

## 🚀 Getting started

**Requirements:** macOS 14+, Xcode Command Line Tools, Python 3, and at least one signed-in provider CLI (Claude Code, Codex and/or Antigravity). JARVIS never asks for passwords or tokens.

```bash
git clone https://github.com/berkesecicii/free-multi-agent-ai-council.git
cd free-multi-agent-ai-council
mkdir -p TAKIM           # build.sh writes a few logs here (git-ignored folder)
zsh native/build.sh      # builds ../JARVIS.app
zsh Start.command        # opens it
```

`Guncelle.command` is the one-click updater (tests → quit → rebuild if needed → relaunch).

Tests: `python3 -m unittest discover -s tests -v` (118 tests).

## 🔒 Privacy

No keys, tokens, accounts or personal data are in this repository or needed to build it. The server listens on `127.0.0.1` only; chats and settings live in `~/Library/Application Support/BerkeJARVIS/`, outside the project.

## 🗺️ Versions

This is the **v0.7.4** snapshot. See the [main branch](https://github.com/berkesecicii/free-multi-agent-ai-council) for the latest version and screenshots. Earlier: v0.7.0 · v0.7.1 · v0.7.2 · v0.7.3 (changes are listed in [`CHANGELOG.md`](CHANGELOG.md), written in Turkish).

## 📄 License

[MIT](LICENSE) © 2026 Berke Secici. Third-party notices: `VOICE-NOTICES.md`, `OLLAMA-LICENSE.txt`.
