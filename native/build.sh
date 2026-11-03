#!/bin/zsh
set -eu
PROJECT_DIR="${0:A:h:h}"
OUTPUT_APP="$PROJECT_DIR/../JARVIS.app"
mkdir -p "$OUTPUT_APP/Contents/MacOS" "$OUTPUT_APP/Contents/Resources/server/static" "$PROJECT_DIR/../../work/swift-cache"
cp "$PROJECT_DIR/app.py" "$PROJECT_DIR/adapters.py" "$PROJECT_DIR/providers.py" "$PROJECT_DIR/codex_chat.py" "$PROJECT_DIR/local_chat.py" "$PROJECT_DIR/google_chat.py" "$PROJECT_DIR/memory_guard.py" "$PROJECT_DIR/free_chat.py" "$PROJECT_DIR/model_catalog.py" "$PROJECT_DIR/project_bridge.py" "$PROJECT_DIR/team_runner.py" "$PROJECT_DIR/claude_chat.py" "$PROJECT_DIR/claude_project_mcp.py" "$PROJECT_DIR/desktop_bridge.py" "$PROJECT_DIR/model-catalog.json" "$OUTPUT_APP/Contents/Resources/server/"
cp "$PROJECT_DIR/static/"* "$OUTPUT_APP/Contents/Resources/server/static/"
cp "$PROJECT_DIR/native/ui-en.json" "$OUTPUT_APP/Contents/Resources/ui-en.json"
cp "$PROJECT_DIR/native/Jarvis.icns" "$OUTPUT_APP/Contents/Resources/Jarvis.icns"
if [ -d "$PROJECT_DIR/../../work/ollama-runtime/bin" ]; then
  mkdir -p "$OUTPUT_APP/Contents/Resources/ollama"
  cp -R "$PROJECT_DIR/../../work/ollama-runtime/bin/" "$OUTPUT_APP/Contents/Resources/ollama/"
fi
cp "$PROJECT_DIR/VOICE-NOTICES.md" "$OUTPUT_APP/Contents/Resources/VOICE-NOTICES.md"
cp "$PROJECT_DIR/OLLAMA-LICENSE.txt" "$OUTPUT_APP/Contents/Resources/ollama/LICENSE"
if [ -d "$OUTPUT_APP/Contents/Resources/server/__pycache__" ]; then
  rm -r "$OUTPUT_APP/Contents/Resources/server/__pycache__"
fi
python3 - "$OUTPUT_APP" <<'CLEAN'
from pathlib import Path
import sys
for file in (Path(sys.argv[1])/'Contents/Resources/ollama').rglob('._*'):
    if file.is_file():file.unlink()
CLEAN
if [ -d "$PROJECT_DIR/../../work/v0.5/voice-runtime" ]; then
  mkdir -p "$OUTPUT_APP/Contents/Resources/voice-runtime"
  cp -R "$PROJECT_DIR/../../work/v0.5/voice-runtime/" "$OUTPUT_APP/Contents/Resources/voice-runtime/"
  cp -R "$PROJECT_DIR/../../work/v0.5/supertonic/onnx" "$PROJECT_DIR/../../work/v0.5/supertonic/voice_styles" "$OUTPUT_APP/Contents/Resources/voice-runtime/"
  cp "$PROJECT_DIR/../../work/v0.5/supertonic/helper.py" "$PROJECT_DIR/native/voice_worker.py" "$OUTPUT_APP/Contents/Resources/voice-runtime/"
  cp "$PROJECT_DIR/../../work/v0.5/supertonic/LICENSE" "$OUTPUT_APP/Contents/Resources/voice-runtime/MODEL-LICENSE"
  cp "$PROJECT_DIR/../../work/v0.5/supertonic/CODE-LICENSE" "$OUTPUT_APP/Contents/Resources/voice-runtime/CODE-LICENSE"
  find "$OUTPUT_APP/Contents/Resources/voice-runtime" -type d -name __pycache__ -prune -exec rm -r {} +
fi
command -v python3 > "$OUTPUT_APP/Contents/Resources/PythonRuntime.txt"
cat > "$OUTPUT_APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIconFile</key><string>Jarvis</string>
<key>CFBundleExecutable</key><string>JARVIS</string>
<key>CFBundleIdentifier</key><string>local.berke.jarvis</string>
<key>CFBundleName</key><string>JARVIS</string>
<key>CFBundleDisplayName</key><string>JARVIS</string>
<key>CFBundleVersion</key><string>70</string>
<key>CFBundleShortVersionString</key><string>0.7.0</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSMicrophoneUsageDescription</key><string>Berke’nin JARVIS ile sesli konuşabilmesi için mikrofon kullanılır. Yalnızca mikrofonu açtığında dinler.</string>
<key>NSSpeechRecognitionUsageDescription</key><string>Berke’nin söylediklerini yazıya çevirmek için konuşma tanıma kullanılır. Cihaz içi destek yoksa Apple hizmeti ayrıca onayla kullanılabilir.</string>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
PLIST
xcrun swiftc -swift-version 5 -module-cache-path "$PROJECT_DIR/../../work/swift-cache" -framework AppKit -framework WebKit -framework AVFoundation -framework Speech -framework ScreenCaptureKit -framework CryptoKit -target arm64-apple-macos14.0 "$PROJECT_DIR/native/Jarvis.swift" -o "$OUTPUT_APP/Contents/MacOS/JARVIS"
# Sign outside the file-provider-backed Documents folder; its Finder metadata
# can be reattached during codesign, making an otherwise valid build fail.
python3 - "$OUTPUT_APP" <<'SIGN'
from pathlib import Path
import shutil,subprocess,sys,tempfile
app=Path(sys.argv[1]);stage=Path(tempfile.mkdtemp(prefix='jarvis-sign-'))/'JARVIS.app'
shutil.copytree(app,stage,symlinks=True)
for attr in ('com.apple.ResourceFork','com.apple.FinderInfo'):
    subprocess.run(['xattr','-dr',attr,str(stage)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
subprocess.run(['codesign','--force','--sign','-',str(stage)],check=True)
subprocess.run(['codesign','--verify','--deep',str(stage)],check=True)
shutil.rmtree(app);shutil.move(str(stage),str(app));stage.parent.rmdir()
SIGN
print "Hazır: $OUTPUT_APP"
