<div align="center">

# 🤖 Free Multi-Agent AI Council for macOS

### JARVIS: one chat, a whole AI team

**A free, open-source multi-agent AI app for your Mac.**
One chat orchestrates Claude Code, Codex and Gemini agents as a council.

![Platform](https://img.shields.io/badge/platform-macOS%2014%2B-black?logo=apple)
![Version](https://img.shields.io/badge/version-0.7.0-4cc9f0)
![Tests](https://img.shields.io/badge/tests-69%20passing-2ea44f)
![Python](https://img.shields.io/badge/python-stdlib%20only-3776ab?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)
![Price](https://img.shields.io/badge/price-free-2ea44f)

</div>

---

## ✨ What is this?

A **free, open-source** native Mac app (Swift shell around a Python standard-library server on `127.0.0.1` and a plain JS front end) that puts an AI council behind **one chat**. The app itself costs nothing (MIT), has no paid API fallback, and uses the official CLIs of the subscriptions or free tiers you already have. Model calls go through the official CLIs of the providers you sign in with (Claude Code, Codex, Antigravity/Gemini).

## 🧑‍🤝‍🧑 The team

| Agent | Engine | Role |
|---|---|---|
| **JARVIS** | Gemini | Independent coordinator (its provider and model are set separately from the others) |
| **VISION** | Claude Code (your own Claude Pro sign-in) | Independent developer |
| **FRIDAY** | Codex (ChatGPT) | Tests and review |
| **EDITH** | Gemini | Real web research |

## 🧠 What it can do in v0.7.0

- **Chat history is a normal chat list.** Close, rename, pin, archive, and delete (with confirmation).
- **Real Gemini web research.** No simulated browsing.
- **An independent Claude Pro developer** through the official Claude Code sign-in; no API-key fallback.
- **Codex for tests and review.**
- **Narrow context.** Unrelated conversations are not carried into an agent's prompt.
- **One manager plan.** A single coordinator call produces the plan, you start it explicitly, and on an error or a half result **you** choose which agent takes over. There is no automatic paid fallback.
- **Timed screen and mouse tools** for Claude and Codex, with a Stop button (real Mac-control testing was still waiting on macOS permissions at this version).
- **Thinking settings** are passed through to the models' real options.

## 🚀 Getting started

**Requirements:** macOS 14+, Xcode Command Line Tools, Python 3, and at least one signed-in provider CLI. JARVIS never asks for passwords or tokens.

```bash
git clone https://github.com/berkesecicii/free-multi-agent-ai-council.git
cd free-multi-agent-ai-council
mkdir -p TAKIM           # build.sh writes a few logs here (git-ignored folder)
zsh native/build.sh      # builds ../JARVIS.app
zsh Start.command        # opens it
```

Tests: `python3 -m unittest discover -s tests -v` (69 tests).

## 🔒 Privacy

No keys, tokens, accounts or personal data are in this repository or needed to build it. The server listens on `127.0.0.1` only.

## 🗺️ Versions

This is the first tagged snapshot, **v0.7.0**. See the [main branch](https://github.com/berkesecicii/free-multi-agent-ai-council) for the latest version. Earlier history is summarised in [`CHANGELOG.md`](CHANGELOG.md) (written in Turkish).

## 📄 License

[MIT](LICENSE) © 2026 Berke Secici. Third-party notices: `VOICE-NOTICES.md`, `OLLAMA-LICENSE.txt`.
