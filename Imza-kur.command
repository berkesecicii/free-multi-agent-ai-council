#!/bin/zsh
# JARVIS için sabit (kendi imzalı) bir imza sertifikası kurar. Bir kez çalıştır; Finder'da çift tıklayabilirsin.
# Neden: uygulama her derlemede "ad-hoc" imzalanıyor. macOS bunu her seferinde yeni bir uygulama sayıp
# Ekran Kaydı ve Erişilebilirlik izinlerini sıfırlıyor. Sabit sertifikayla imzalanınca izinler yeniden derlemelerde kalır.
# macOS senden parolanı (veya Touch ID) isteyecek; parola bu betiğe gelmez, saklanmaz. Sertifika yalnız bu Mac'te, yalnız sana ait.
# Sonuç: imza-kur.log
HERE="${0:A:h}"
LOG="$HERE/imza-kur.log"
exec > >(tee "$LOG") 2>&1
NAME="JARVIS Local Signing"
OSSL=/usr/bin/openssl   # the system LibreSSL: a Homebrew OpenSSL 3 writes .p12 files the Keychain refuses (MAC verification failed)
KEYCHAIN="$HOME/Library/Keychains/login.keychain-db"
print "başladı: $(date +%H:%M:%S)"
if security find-identity -v -p codesigning | grep -q "\"$NAME\""; then
  print "Sertifika zaten kurulu ve güvenilir: $NAME"
  print "bitti: kod 0"
  exit 0
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cat > "$TMP/openssl.cnf" <<'CNF'
[req]
distinguished_name=dn
x509_extensions=ext
prompt=no
[dn]
CN=JARVIS Local Signing
[ext]
basicConstraints=critical,CA:false
keyUsage=critical,digitalSignature
extendedKeyUsage=critical,codeSigning
subjectKeyIdentifier=hash
CNF
print "1/3  Sertifika üretiliyor"
if ! $OSSL req -x509 -newkey rsa:2048 -nodes -days 3650 -config "$TMP/openssl.cnf" -keyout "$TMP/key.pem" -out "$TMP/cert.pem"; then
  print "bitti: kod 1 (sertifika üretilemedi)"; exit 1
fi
PASS="$($OSSL rand -hex 12)"
if ! $OSSL pkcs12 -export -inkey "$TMP/key.pem" -in "$TMP/cert.pem" -name "$NAME" -out "$TMP/id.p12" -passout "pass:$PASS"; then
  print "bitti: kod 2 (paket oluşturulamadı)"; exit 2
fi
print "2/3  Anahtar zincirine ekleniyor"
if ! security import "$TMP/id.p12" -k "$KEYCHAIN" -P "$PASS" -T /usr/bin/codesign; then
  print "bitti: kod 3 (anahtar zincirine eklenemedi)"; exit 3
fi
print "3/3  Güvenilir yapılıyor: macOS şimdi parolanı soracak (yalnız kod imzalama için)"
if ! security add-trusted-cert -r trustRoot -p codeSign -k "$KEYCHAIN" "$TMP/cert.pem"; then
  print "bitti: kod 4 (güven ayarı verilmedi; parolayı onaylamadıysan betiği yeniden çalıştır)"; exit 4
fi
if security find-identity -v -p codesigning | grep -q "\"$NAME\""; then
  print "Tamam: $NAME kuruldu. Sonraki derlemede uygulama bununla imzalanır; macOS 'codesign anahtarı kullanmak istiyor' derse 'Her Zaman İzin Ver' de."
  print "bitti: kod 0"
  exit 0
fi
print "bitti: kod 5 (sertifika kuruldu ama imzalama kimliği olarak görünmüyor)"
exit 5
