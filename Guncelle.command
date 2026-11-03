#!/bin/zsh
# JARVIS güncelleme (tek tık): test → kapat → derle → doğrula → yeniden aç.
# Finder'da çift tıkla veya: zsh Guncelle.command
# Not: Bu betik yalnızca proje klasöründeki kodu uygulamaya kurar; parola/ödeme/sistem ayarı istemez.
set -eu
HERE="${0:A:h}"
cd "$HERE"
APP="$HERE/../JARVIS.app"

print "1/4  Testler"
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests

print "2/4  JARVIS açıksa kapatılıyor"
if pgrep -f "JARVIS.app/Contents/MacOS/JARVIS" >/dev/null 2>&1; then
  osascript -e 'tell application id "local.berke.jarvis" to quit' >/dev/null 2>&1 || true
  sleep 3
  pkill -f "JARVIS.app/Contents/Resources/server/app.py" >/dev/null 2>&1 || true
  pkill -f "JARVIS.app/Contents/MacOS/JARVIS" >/dev/null 2>&1 || true
  sleep 1
fi

print "3/4  Derleme ve imza"
zsh native/build.sh

print "4/4  Doğrulama"
grep -q "0.7.4" "$APP/Contents/Info.plist"
for f in app.py google_chat.py model_catalog.py free_chat.py team_runner.py static/focus.js static/i18n.js static/clarity.js static/attach.js static/pulse.js static/native.js; do
  cmp -s "$f" "$APP/Contents/Resources/server/$f" || { print "HATA: $f uygulamaya kopyalanmamış"; exit 1; }
done
print "Tamam: JARVIS 0.7.4 kuruldu. Açılıyor..."
open "$APP"
