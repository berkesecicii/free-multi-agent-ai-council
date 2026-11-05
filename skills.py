"""Reusable how-to guides (skills) for the coding agents: built-in ones plus Markdown files Berke or the team saved in the skills folder of the app data."""
import re
from pathlib import Path

NAME=re.compile(r'^[a-z0-9][a-z0-9-]{1,40}$')
MAX_CHARS=8000
BUILTIN={
'web-oyun':('Small browser game (canvas, keyboard, score, restart) that works the first time.','''# web-oyun
Use for any small browser game (snake, tic-tac-toe, pong, memory cards).
1. Files: index.html, script.js, style.css (+ short README.md). One <canvas> or a CSS grid; no libraries, no network.
2. Game loop: requestAnimationFrame with a fixed time step (accumulate delta time); never setInterval for rendering.
3. State in one object; reset() rebuilds it, so the restart button and the first start share one code path.
4. Keyboard: preventDefault on arrow keys, ignore a reverse direction, start on the first key.
5. Show score and best score (localStorage inside try/catch), a clear "game over" message, a restart button.
6. Verify: `node --check script.js`; if Playwright or a browser is available, load index.html, press keys, read the score. Say what you did NOT test.
7. Hand over with project_open_editor: app=vscode for the folder, app=browser for index.html.'''),
'proje-kurulum':('Start a new project folder cleanly (layout, README, run/test commands, git).','''# proje-kurulum
1. Look first: project_list, read README/package.json if present. Never overwrite what exists; patch it.
2. Small layout: source files, a tests folder if there is logic worth testing, README.md with how to run and test in 3-5 lines.
3. Node: package.json with "scripts": {"start","test"}; Python: a single main file + tests/ with unittest.
4. Create dependencies only when needed. Installing needs project_command with network=true and Berke's approval; prefer zero-dependency code.
5. git: `git init`, a .gitignore (node_modules, .venv, __pycache__, .DS_Store), one first commit. Push only when Berke asked for it.
6. End by running the real test or start command and report its output honestly.'''),
'dogrula':('How to check finished work so nothing untested is called done.','''# dogrula
1. Re-read the request and list what must be true. Check each item, not just "it runs".
2. Run the project's own tests or a syntax check (`node --check`, `python3 -m py_compile`, `swift build`). Read the whole output.
3. For UI: open it (project_open_editor app=browser) and, when a browser tool exists, press the real keys or buttons.
4. Report: what you ran, what passed, what you could not test. Never write "tested" for something you did not run.
5. If something fails, fix the cause and rerun; do not hide the failure in the report.'''),
'hata-ayikla':('Debugging routine: reproduce, narrow, fix the cause, prove the fix.','''# hata-ayikla
1. Reproduce first with one exact command; keep its output.
2. Narrow: project_search for the error text, read only the files involved.
3. Change one thing at a time. Prefer project_patch with the smallest exact snippet.
4. Rerun the same command; the failure must be gone and the other tests still pass.
5. Add a short test for the bug when the project has tests. Note the cause in one line with project_note.'''),
'git-akisi':('Everyday git in the sandbox: status, diff, commit; push only when Berke asked; never rewrite history.','''# git-akisi
1. `git status` and `git diff --stat` before and after your work.
2. Commit small, in the imperative: `git commit -am "Add restart button"`. Only commit when Berke asked or the task says so.
3. `reset --hard`, `clean`, `checkout --`, `branch -D` always ask Berke and need a clear reason.
4. `git push`, `pull`, `fetch`, `clone` open the network by themselves and always ask Berke. Run `git` directly (argv ["git","push"]), not inside `sh -c`, so his saved GitHub sign-in works. Push only when he asked; say which branch and remote you push to in `reason`.
5. If the push fails on sign-in, stop and tell him: you cannot enter passwords or tokens, he has to sign in to GitHub once himself.'''),
}

def user_dir(state_dir):return Path(state_dir)/'skills'

def _describe(text):
    for line in text.splitlines():
        line=line.strip()
        if line and not line.startswith('#'):return line[:140]
    return ''

def listing(state_dir=None):
    rows={name:(desc,'built-in') for name,(desc,_) in BUILTIN.items()}
    folder=user_dir(state_dir) if state_dir else None
    if folder and folder.is_dir():
        for path in sorted(folder.glob('*.md'))[:60]:
            name=path.stem
            if NAME.match(name) and path.is_file() and not path.is_symlink() and path.stat().st_size<=60000:
                rows[name]=(_describe(path.read_text('utf-8','replace')),'saved')
    return [dict(name=name,description=value[0],source=value[1]) for name,value in sorted(rows.items())]

def read(name,state_dir=None):
    name=str(name or '').strip().lower()
    if not NAME.match(name):raise ValueError('Beceri adı a-z, 0-9 ve tireden oluşmalı.')
    folder=user_dir(state_dir) if state_dir else None
    path=folder/(name+'.md') if folder else None
    if path and path.is_file() and not path.is_symlink() and path.stat().st_size<=60000:
        return path.read_text('utf-8','replace')[:MAX_CHARS]
    if name in BUILTIN:return BUILTIN[name][1][:MAX_CHARS]
    raise ValueError('Bu adda bir beceri yok. Adsız çağırıp listeye bak.')
