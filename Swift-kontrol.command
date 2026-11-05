#!/bin/zsh
# Yalnız Swift sözdizimi kontrolü (kurulum yapmaz, uygulamayı kapatmaz). Çıktı: swift-kontrol.log
HERE="${0:A:h}"
cd "$HERE"
SWIFT_CACHE="${HERE}/../../work/swift-cache-v2"
SWIFT_CACHE="${SWIFT_CACHE:A}"
mkdir -p "$SWIFT_CACHE"
xcrun swiftc -typecheck -swift-version 5 -module-cache-path "$SWIFT_CACHE" -target arm64-apple-macos14.0 native/Jarvis.swift > "$HERE/swift-kontrol.log" 2>&1
print -- "bitti: kod $?" >> "$HERE/swift-kontrol.log"
print -- "bitti"
