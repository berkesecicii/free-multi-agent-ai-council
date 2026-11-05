#!/bin/zsh
# JARVIS güncelleme (tek tık): test → kapat → (gerekirse derle) → yeniden aç.
# Finder'da çift tıkla veya: zsh Guncelle.command
# Not: Bu betik yalnızca proje klasöründeki kodu uygulamaya kurar; parola/ödeme/sistem ayarı istemez.
#
# İki yol:
#  • HIZLI  (yalnız Python/web dosyaları değiştiyse): kod ~/Library/Application Support/BerkeJARVIS/server-live içine kopyalanır,
#    imzalı uygulamaya dokunulmaz → macOS Ekran Kaydı/Erişilebilirlik izinleri KORUNUR.
#  • TAM    (Swift, simge, ses dosyaları, build.sh değiştiyse veya ilk kurulumda): uygulama yeniden derlenir ve imzalanır;
#    imza değiştiği için macOS izinleri bir kez yeniden verilmelidir (Ayarlar'da JARVIS'i − ile çıkarıp + ile ekle).
set -eu
HERE="${0:A:h}"
cd "$HERE"
# Çıktı ayrıca guncelle.log dosyasına yazılır (Terminal kapansa da sonuç okunabilir).
exec > >(tee "$HERE/guncelle.log") 2>&1
print "başladı: $(date +%H:%M:%S)"
APP="$HERE/../JARVIS.app"
SWIFT_CACHE="${HERE}/../../work/swift-cache-v2"
SWIFT_CACHE="${SWIFT_CACHE:A}"
DATA="$HOME/Library/Application Support/BerkeJARVIS"
LIVE="$DATA/server-live"
STAMP_FILE="$HERE/.native-stamp"
NATIVE_FILES=(native/Jarvis.swift native/build.sh native/ui-en.json native/Jarvis.icns native/voice_worker.py native/pdftext.swift VOICE-NOTICES.md OLLAMA-LICENSE.txt)
NEW_STAMP="$(cat "${NATIVE_FILES[@]}" | shasum -a 256 | cut -d' ' -f1)"
OLD_STAMP="$(cat "$STAMP_FILE" 2>/dev/null || true)"
MODE="TAM"
if [ "$NEW_STAMP" = "$OLD_STAMP" ] && [ -x "$APP/Contents/MacOS/JARVIS" ]; then MODE="HIZLI"; fi
if [ "${1:-}" = "--tam" ]; then MODE="TAM"; fi
print "Kurulum yolu: $MODE"

print "1/4  Testler"
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests

if [ "$MODE" = "TAM" ]; then
  print "1b   Swift sözdizimi kontrolü (hata varsa uygulama kapatılmaz)"
  mkdir -p "$SWIFT_CACHE"
  xcrun swiftc -typecheck -swift-version 5 -module-cache-path "$SWIFT_CACHE" -target arm64-apple-macos14.0 native/Jarvis.swift
fi

print "2/4  JARVIS açıksa kapatılıyor"
if pgrep -f "JARVIS.app/Contents/MacOS/JARVIS" >/dev/null 2>&1; then
  osascript -e 'tell application id "local.berke.jarvis" to quit' >/dev/null 2>&1 || true
  sleep 3
  pkill -f "JARVIS.app/Contents/Resources/server/app.py" >/dev/null 2>&1 || true
  pkill -f "BerkeJARVIS/server-live/app.py" >/dev/null 2>&1 || true
  pkill -f "JARVIS.app/Contents/MacOS/JARVIS" >/dev/null 2>&1 || true
  sleep 1
fi

if [ "$MODE" = "TAM" ]; then
  print "3/4  Derleme ve imza"
  zsh native/build.sh
else
  print "3/4  Derleme atlandı (uygulama değişmedi, izinler korunur)"
fi

print "3b   Python ve web dosyaları server-live klasörüne kopyalanıyor"
mkdir -p "$DATA"
rm -rf "$LIVE.new"
mkdir -p "$LIVE.new/static"
cp ./*.py model-catalog.json "$LIVE.new/"
cp static/* "$LIVE.new/static/"
rm -rf "$LIVE"
mv "$LIVE.new" "$LIVE"

print "4/4  Doğrulama"
grep -q "0.7.6" "$APP/Contents/Info.plist"
for f in app.py chat_workflow.py scheduler.py documents.py claude_usage.py google_chat.py model_catalog.py free_chat.py team_runner.py local_chat.py static/focus.js static/i18n.js static/clarity.js static/attach.js static/pulse.js static/polish.js static/rail.js static/sidebar.js static/native.js static/index.html static/focus.css; do
  cmp -s "$f" "$LIVE/$f" || { print "HATA: $f server-live içine kopyalanmamış"; exit 1; }
done
if [ "$MODE" = "TAM" ]; then
  for f in app.py chat_workflow.py scheduler.py documents.py claude_usage.py google_chat.py model_catalog.py free_chat.py team_runner.py static/focus.js static/i18n.js static/clarity.js static/attach.js static/pulse.js static/polish.js static/rail.js static/sidebar.js static/native.js; do
    cmp -s "$f" "$APP/Contents/Resources/server/$f" || { print "HATA: $f uygulamaya kopyalanmamış"; exit 1; }
  done
  if [ -d "$APP/Contents/Resources/voice-runtime" ]; then
    cmp -s native/voice_worker.py "$APP/Contents/Resources/voice-runtime/voice_worker.py" || { print "HATA: ses motoru dosyası kopyalanmamış"; exit 1; }
  fi
  print "$NEW_STAMP" > "$STAMP_FILE"
fi
print "Tamam ($MODE): JARVIS 0.7.6 hazır. Açılıyor..."
open "$APP"
