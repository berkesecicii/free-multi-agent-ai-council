#!/bin/zsh
# Tarayıcı aracını bir kez kurar: Playwright + Chromium (yaklaşık 200 MB, internet gerekir).
# Ajanlar bundan sonra yazdıkları web sayfasını gerçek tarayıcıda dener (project_browser). Çıktı: tarayici-kur.log
HERE="${0:A:h}"
TOOLS="$HOME/Library/Application Support/BerkeJARVIS/tools"
LOG="$HERE/tarayici-kur.log"
{
  print "başladı: $(date +%H:%M:%S)"
  mkdir -p "$TOOLS" || exit 1
  if [[ ! -x "$TOOLS/venv/bin/python" ]]; then /usr/bin/python3 -m venv "$TOOLS/venv" || { print "HATA: venv kurulamadı"; exit 1; }; fi
  print "1/3  Playwright paketi"
  "$TOOLS/venv/bin/python" -m pip install --quiet --disable-pip-version-check playwright || { print "HATA: playwright kurulamadı"; exit 1; }
  print "2/3  Chromium indiriliyor"
  "$TOOLS/venv/bin/python" -m playwright install chromium || { print "HATA: Chromium indirilemedi"; exit 1; }
  print "3/3  Deneme"
  "$TOOLS/venv/bin/python" - <<'PY' || { print "HATA: tarayıcı açılmadı"; exit 1; }
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(headless=True);pg=b.new_page();pg.set_content('<title>JARVIS</title><b id=x>tamam</b>')
    print('tarayıcı çalışıyor:',pg.title(),pg.inner_text('#x'));b.close()
PY
  print "Tamam: tarayıcı aracı hazır."
} > "$LOG" 2>&1
print -- "bitti: $(tail -n 1 "$LOG")"
