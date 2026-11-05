## 2026-11-04 · Komut ortamı (sandbox) sertleştirildi
- `project_command` kum havuzu artık ajanların kendi giriş klasörlerini (`~/.claude`, `~/.codex`, `~/.gemini`), tarayıcı ve mesaj verisini (Chrome, Safari, Cookies, Messages, Mail), kabuk geçmişini ve (git komutları dışında) Keychain ile token dosyalarını okutmaz. Gerçek Mac'te `sandbox-exec` ile denendi: bu yollar `Operation not permitted` verdi; proje dosyası okuma, python3 ve geçici klasöre yazma çalıştı; ev klasörüne yazma yine engelli. 294 test.

## 2026-11-04 · Arka plan kontrol modu (öne getirmeden çalışma) ve kalıcı imza
- Berke başka uygulamada çalışırken ajan onun ekranına dokunmaz. Ajan bir uygulamayı `desktop_open_app` (artık `open -g -a`: öne getirmez) ya da `desktop_observe(app=…)` ile seçer; bundan sonra yakalama, tık, yazı, tuş ve kaydırma yalnız o uygulamanın penceresine gider. Seçilmiş uygulama yokken tık/yazı/tuş/kaydırma reddedilir (ön plandaki uygulama, JARVIS dahil, hedef olmaz); seçim yoksa `desktop_observe` yalnız tüm ekranı salt-okunur gösterir.
- Mac uygulaması (Swift): hedef uygulamanın penceresi ScreenCaptureKit ile tek pencere olarak yakalanır (örtülü olsa da); tıklama erişilebilirlikle yapılır (düğmeye AXPress, satır seçimi, metin alanına odak + imleç yeri), erişilebilirlikte karşılığı yoksa yalnız o sürece pencere numaralı fare olayı gönderilir. Yazma `AXSelectedText` ile araya eklenir; olmazsa o sürece tuş olayı. Cmd+S/A/Z/N/L menü çubuğundaki kısayol karşılığına basılarak yapılır; Enter/Esc/Backspace/ok tuşları mümkünse erişilebilirlikle. Berke'nin gerçek fare ve klavyesine dokunulmaz; `desktop_open_url` tarayıcıyı öne getirmez.
- "Ajan ekranı": hedef uygulama ön planda değilse sağ altta küçük, taşınabilir, odak almayan bir panel o pencerenin son görüntüsünü ve ajanın imlecini (tıklamada halka) gösterir; hedef ön plandaysa imleç gerçek pencerede gezer. Ajan çalışırken uygulama App Nap'e girmez (sayfa yoklaması yavaşlamasın).
- Chromium/Electron (VS Code, Antigravity, Chrome) için `AXManualAccessibility` açılır. Sınır: bazı uygulamalar arka planda gelen tuş olaylarını yok sayar; sonuç `needs_visual_verification`/`note` taşır, ajan görüntüyle doğrular ve olmadıysa öne almak yerine Berke'ye söyler. VS Code'da gerçek deneme henüz yapılmadı.
- Kalıcı imza: `Imza-kur.command` bir kez "JARVIS Local Signing" kod imzalama sertifikasını oluşturup anahtarlığa güvenilir olarak ekledi; `native/build.sh` onunla imzalar (yoksa ad-hoc'a düşer) ve izinler sonraki derlemelerde sıfırlanmamalı (henüz doğrulanmadı). Parola okunmaz/saklanmaz.
- Swift değişti: TAM kurulum yapıldı (0.7.6, yeni imzayla); Ekran Kaydı ve Erişilebilirlik bir kez yeniden verilmeli. 288 test.
- Gerçek denemede bulunup düzeltilenler: (1) Araç hataları ajana yalnız "HTTP Error 400" olarak gidiyordu; `claude_project_mcp.py` artık sunucunun gerçek hata metnini ajana verir. (2) Kilitlenme: uygulamayı açmak için önce gözlem, gözlemek için de uygulamanın açık olması isteniyordu; arka planda açma artık önceden gözlem istemez. (3) Yeni başlayan belge uygulamalarında (TextEdit) arka planda pencere olmuyor (Aç paneli gizli kalır); pencere yokken de gözlem geçerli (`no_window`), ajan Cmd+N ile belge açıp yeniden gözlüyor. (4) Açılışta ilk 1-2 sn eski ham sayfa görünüyordu (sayfa katman katman kuruluyor); ilk veri gelene kadar koyu zeminde sade "JARVIS" yazısı gösterilir, en geç 5 sn.
- Gerçek sonuçlar: TextEdit uçtan uca çalıştı (VISION arka planda açtı, Cmd+N ile belge oluşturdu, "merhaba arka plan" yazdı; ben pencerede doğruladım). Kalıcı imza çalıştı: tam yeniden derlemeden sonra Ekran Kaydı/Erişilebilirlik sıfırlanmadı. VS Code (Electron): ilk denemede "başarısız" göründü, asıl sebep pencere seçimiydi (aşağıdaki VS Code bulguları); ayrıca VS Code erişilebilirlik açıldığını görüp "Screen reader usage detected" bildirimi gösteriyor. Dosya işleri için `project_edit` tercih edilir.
- VS Code bulguları (gerçek deneme): (1) Pencere seçimi: Cmd+N aslında yeni "Untitled-1" penceresini açmıştı ama gözlem uygulamanın en büyük eski penceresini yakalıyordu; artık uygulamanın kendi odaklı/ana penceresi (AXFocusedWindow/AXMainWindow) seçilir, sonuçta `window_title` ve `other_windows` var. (2) Yazma: Chromium arka planda uygulama düzeyinde odak bildirmiyor ve editörün gerçek girdi kutusu tıklanan satırın altında değil (Monaco: `monaco-editor` kapsayıcısında kardeş öğe). Tık artık metin öğesini (gerekirse `monaco-editor` sınıfından bularak) odaklar ve hatırlar (`bgText`); `desktop_type` önce hatırlanan öğeye yazar (AXSelectedText, olmazsa AXValue birleştirme, en son pid tuşları); tık sonucunda `hit_path` (rol.sınıf zinciri) tanı için döner. Sonuç: tık `ax-focus`, yazma `accessibility-insert` başarılı döndü, ama ekran görüntüsünde yazı görünmedi. Şüphe: kapalı/başka Space'teki Chromium penceresi yeniden çizilmiyor, görüntü bayat; Berke'nin gözle doğrulaması bekleniyor. 293 test, TAM kurulum x3.

## 2026-11-04 · Ekran işleri için adım sınırı 8 → 24
- Gerçek denemede VISION (Claude Code) bilgisayar işinde birkaç adım sonra "işlem adım sınırında durdu" diyerek yarıda kaldı: ekran işi çok küçük adımdan oluşuyor (bak, uygulamayı aç, bak, tuşa bas, bak, yaz, bak, cevapla) ve sınır 8'di. `turn_budget`: ekran araçlı oturumda en az 24, proje bütçesi daha büyükse o kalır. HIZLI kurulum, izinler korunur.

## 2026-11-04 · Kota uyarısı: tek, kapatılabilir bildirim, yalnız %25 kalınca
- Eskiden 5 saatlik kota her %25 adımında (25/50/75/100) sohbete kalıcı bir SYSTEM mesajı olarak yazılıyor ve her sohbette ayrıca bir çip çıkıyordu; Berke bunu kalabalık buldu. Artık sohbetin üstünde tek bir bildirim şeridi çıkıyor ("VISION · Claude · 5 saatlik kota: %25 kaldı", varsa sıfırlanma saati, "Kota ayrıntıları" ve × düğmeleri). Yalnız doğrulanmış 5 saatlik pencerede ve %75 kullanıldı (%25 kaldı) ya da daha fazlasında, pencere başına bir kez; × ile kapatınca `quota_milestones` içine yazılır ve o pencere için hiçbir sohbette ya da yeniden açılışta geri gelmez. Sohbete mesaj yazılmaz; eski makbuz satırları geçmişte kalır ama gizlenir.
- `quota-note` eylemi artık yalnız "görüldü/kapatıldı"yı kaydeder (`recorded`); eşik altı, doğrulanmamış sağlayıcı ve haftalık pencere reddedilir. HIZLI kurulum, izinler korunur. 286 test.

## 2026-11-04 · Sohbet başına tek izin, JARVIS kendi penceresine dokunmaz, ince ışık ve ajan imleci
- İzin artık gerçekten "bir sohbette bir kere": kontrol kartında "Bu sohbette izin ver" denince sohbete kaydedilir (`computer_granted`), uygulama yeniden açılsa bile tekrar sorulmaz. İzinli sohbette kod editörüne (VS Code, Xcode, Antigravity) yazarken de ayrıca onay kartı çıkmaz; her eylem için kart yalnız elle başlatılan (auto_actions kapalı) oturumlarda sürer. Durdur düğmesi yalnız o sohbetin iznini geri alır (eskiden tüm sohbetlerinkini siliyordu).
- Odak hatası: kartta "onayla"ya basmak JARVIS'i öne getiriyordu ve ajanın Cmd+N'si JARVIS'e gidip yeni sohbet açıyordu. Artık ön plandaki uygulama JARVIS ise tık/yazma/tuş/kaydırma reddedilir (Python ve Swift'te); ajan bir uygulama açtıysa o uygulama `open -a` ile yeniden öne alınır ve ajandan yeni gözlem istenir. Gözlem sonucu `bundle` (uygulama kimliği) de döner.
- Editörde terminal koruması: izinli oturumda editöre yazılırken odaktaki öğenin erişilebilirlik adı/açıklaması "terminal" ya da "xterm" içeriyorsa yazma ve tuş basma reddedilir (en iyi çaba; editörün tümleşik terminali bu adı taşımazsa yakalanmaz).
- Işık: tam ekran çizim yerine her ekranda 4 ince, yumuşak kenar şeridi (gradyan penceresi); derinlik yarıya indi (~44 px, `GLOW_DEPTH`), çekirdek çizgi kalktı, tepe saydamlığı düşürüldü ("hissedilsin, görünmesin"). Bellek ve çizim yükü de azalır.
- Ajan imleci: ajan tıklarken/fare taşırken ajanın renginde, adı yazılı bir ok imleç hedefe kayar ve tıklamada halka yayılır; gerçek fare imleç vardıktan sonra oynar. Ekran görüntüsüne girmez.
- Swift değişti: TAM kurulum; Ekran Kaydı ve Erişilebilirlik bir kez yeniden verilmeli. 285 test.

## 2026-11-04 · Uygulama açma arka plandan da çalışır, ışık ayarı sayfadan
- `desktop_open_app` artık Mac uygulamasına gitmeden sistemin `/usr/bin/open -a` komutuyla yapılır. Sebep (gerçek denemede görüldü): macOS ön plandaki olmayan uygulamanın başka uygulamayı öne getirmesine izin vermiyor; Berke başka bir uygulamada yazarken VISION VS Code'u öne getiremedi ve "yapamadım" dedi. Uygulama listesi ve onaylar aynı; açtıktan sonra yeni gözlem şart.
- Bilinen sınır: JARVIS gerçek fareyi ve klavyeyi ön plandaki uygulamada sürüyor; Berke aynı anda başka uygulamada yazarsa yazdıkları ajanın açtığı uygulamaya gidebilir. Gerçek arka plan modu (uygulamaya özel görüntü ve tuş/tık gönderme) ayrı bir iş, yapılmadı.
- Işık yoğunluğu: Berke "biraz kıs, havalı kalsın" dedi. Güç artık sayfadan gelir (`GLOW_LEVEL` = 0,62 in static/clarity.js, aralık 0,2-1; Swift halka sayısını ve parlaklığı ona göre çizer). Sonraki ayarlar kurulumsuz (HIZLI).
- Swift değişti: TAM kurulum yapıldı (0.7.6); izinler yeniden verilmeli. 280 test.

## 2026-11-04 · İzin tuşları gerekirse Sistem Ayarları sayfasını açar
- Sohbetteki "Allow screen access", "This Mac" penceresindeki "Open" ve kontrol kartındaki "Allow" bağlantısı önce macOS'tan izin ister; 1,2 sn sonra izin hâlâ kapalıysa doğrudan ilgili Sistem Ayarları sayfasını (Ekran Kaydı ya da Erişilebilirlik) açar. Sebep: macOS Ekran Kaydı penceresini yalnız ilk seferde gösteriyor; yeniden imzalanan uygulamada tuş sessiz kalıyordu. Görünüm ve düzen değişmedi, yalnız tuşun davranışı (web tarafı; Swift'teki `open-mac-permission` eylemi zaten vardı). HIZLI kurulum, izinler korunur.
- Test: Mac'te geçici klasör temizliği yarışı (arka planda geç yazan kayıt) bir testi rastgele düşürüyordu; yardımcı artık klasörü hata saymadan siliyor. 280 test.

## 2026-11-04 · Ekran isteğini ajan anlar (kalıp listesi yok) ve daha güçlü ışık
- Bilgisayar isteği artık yalnız sabit kalıplarla ("bilgisayarımı kullan" gibi) tanınmaz: kodlayan/konuşan her ajanın istemine kısa bir `SCREEN REQUESTS` notu girer (NOVA, planlama, iş akışı ve yerel model hariç; kontrol edebilecek ajan yoksa girmez). Mesaj hangi sözlerle yazılırsa yazılsın, işin Mac ekranında yapılması gerektiğini anlayan ajan cevabını tek "COMPUTER: görev" satırıyla bitirir; uygulama satırı siler ve izin kartını o mesajın altına koyar (kart kime: sorulan ajan kontrol edebiliyorsa o, yoksa adı geçen / kanalın / önce VISION). Bu sohbette izin zaten verilmişse kart çıkmadan başlar. Ek model çağrısı yok; eski hızlı kalıp denetimi duruyor ve "bilgisayarını kullan / ekranını kontrol et" kalıpları da eklendi.
- Sebep: gerçek denemede "bilgisayarını kullanarak VS Code'u aç…" kalıba uymadı, FRIDAY işi VISION'a paslayıp araçsız cevap verdi. Paslama metninden "ekran işi -> VISION" ifadesi kaldırıldı.
- Işık çerçevesi: 46 halkalı daha geniş ve parlak hale + kenarda ince açık çizgi, daha belirgin nefes. Açılışta ışık ve yazı yumuşakça belirir (0,5-0,9 sn); 6 sn sonra yazı silinip kısa hap boyutuna süzülür; oturum bitince ya da Durdur'da ad yazısı ve ışık 1,6 sn'de yavaşça silinir (ani kaybolma yok).
- Swift değişti: TAM kurulum yapıldı (0.7.6); macOS Ekran Kaydı ve Erişilebilirlik izinleri yeniden verilmeli. 278 test.

## 2026-11-04 · Bilgisayar kontrolünde ışık çerçevesi, Durdur hapı, daha az token
- Bir ajan bilgisayarı kontrol ederken her ekranın kenarında ajanın renginde yumuşak, nefes alan bir ışık çizilir (tıklamayı engellemez). Tepede ilk 6 saniye "FRIDAY bilgisayarını kullanıyor" yazısı, sonra küçük bir "● FRIDAY · Durdur" hapı kalır; Durdur oturumu kapatır (Cmd+Shift+Esc ve JARVIS içindeki düğme de çalışır). Oturum bitince ya da süresi dolunca ışık kapanır.
- Ekranı çizen bu pencereler ajanın ekran görüntüsüne girmez (ScreenCaptureKit'ten dışlanır). Tamamı yerel çizim: model token'ı harcamaz.
- Ekran görüntüsü en çok 1.200 piksel genişliğe küçültülür (~%30-40 daha az görüntü token'ı); ajanın x/y koordinatları küçük görüntüye göredir, tıklarken Mac uygulaması gerçek ekrana geri ölçekler. Gözlem sonucundaki genişlik/yükseklik artık küçük görüntünün boyutudur.
- Ara durum mesajı tasarrufu: araç açıklaması kısaltıldı, satır en çok 200 karakter, iş başına en çok 6 (istem: en çok 5, 15 kelimeden kısa, kısa işte hiç); araç sonucu tek kelimelik.
- Swift değişti: TAM kurulum yapıldı (0.7.6); macOS Ekran Kaydı ve Erişilebilirlik izinleri yeniden verilmeli. 273 test.

## 2026-11-04 · Ajanlar uzun işte ara durum mesajı yazar
- Yeni araç `project_progress` (VISION ve FRIDAY, proje araçlarıyla birlikte): ajan uzun ve çok parçalı işte her gerçek aşama bitince sohbete tek kısa cümle yazar (ne bitti, sıradaki ne). Onay istemez; iş başına en çok 8, aynı cümle iki kez gitmez, 5-280 karakter. Mesaj ajanın kendi akan yanıtından önce araya girer; asıl yanıt hep en altta kalır ve nihai cevabı taşır.
- İstem: kodlayan ajanlara "uzun işte her aşamada project_progress çağır, küçük adımlar için değil, kapanış cevabı gerçek cevap kalsın" eklendi.
- Arayüz: ara mesajlar hafif ve küçük yazıyla, ajanın renginde sol çizgiyle gösterilir; "Yeni yanıt" düğmesi ve sesli okuma/ses bildirimi yok. 272 test.

## 2026-11-04 · git push, internetli tarayıcı, editörde yazma
- `git push`, `pull`, `fetch`, `clone`, `ls-remote` ağı kendileri açar (`sh -c` içinde olsa da yakalanır; `-C`/`-c` seçenekleri atlanmaz). Her seferinde onay kartı çıkar, turbo modda bile; `push` ayrıca "Riskli" sayılır. Düz `git ...` çağrısında sandbox Anahtarlık klasörünü okumaya bırakır (kayıtlı GitHub girişi için); `.ssh`, `.aws`, `.gnupg` ve JARVIS verisi yine kapalı. Parola ya da token girmek ajanın işi değil: Berke'nin GitHub'a bir kez giriş yapmış olması gerekir. Komutlar `GIT_TERMINAL_PROMPT=0` ile çalışır; giriş yoksa sormadan hata verir.
- `project_browser` internet modu: `url` (http/https) ve `goto` adımı. Her oturum için zorunlu onay kartı ("İnternet erişimli tarayıcı"; adres ve adımlar kartta görünür), turbo modda bile. Tarayıcı her seferinde temiz açılır (kayıtlı giriş yok), yalnız okur (GET/HEAD/OPTIONS; POST, PUT, PATCH, DELETE engellenir), localhost, ev ağı, `.local`/`.internal` adlarına ve özel IP'lere gitmez (adres çözülünce de bakılır), indirme ve WebSocket kapalı, parola ve kart alanlarına yazmaz. İnternet modunda `eval` yok; `text` ile `body` okunur. Proje dosyası modu eskisi gibi.
- Kod editörlerinde (VS Code, Xcode, Antigravity, Cursor...) yazma ve kısayol artık açık, ama her eylem için ayrı onay kartı çıkar ("Kod düzenleyiciye yazma"; yazılacak metin kartta), otomatik kontrol oturumunda bile. Önceki gözlemde öndeki uygulama editörse JARVIS kartı açar ve onaydan sonra isteğe `editor_ok` ekler; Mac uygulaması bu bayrak olmadan editörde yazmaz (gözlem eskiyse bile). Terminal, Sistem Ayarları, parola ve Anahtarlık pencereleri hâlâ kapalı.
- Swift değişti: TAM kurulum yapıldı (0.7.6); macOS Ekran Kaydı ve Erişilebilirlik izinleri yeniden verilmeli. 270 test.

## 2026-11-04 · Tam teçhizat: kabuk, ağ, skills, hafıza, paralel ekip, tarayıcı
- Sabit görev dağılımı: kod yazma VISION (varsayılan) ya da FRIDAY (zor iş, ikinci uygulayıcı, test, inceleme); araştırma yalnız EDITH (EDITH kapalıysa FRIDAY yedek). FRIDAY'nin rolü "Yardımcı yazılımcı · zor işler, ikinci uygulama, test, inceleme" oldu (kayıtlı durum bir kez taşınır). Varsayılan ekip akışı EDITH tasarlar, VISION yazar, FRIDAY inceler. JARVIS yönlendirme ve planlama istemleri bu kurala göre yeniden yazıldı.
- `project_command` genişledi: sh/bash/zsh (boru, yönlendirme, döngü), curl, pip/pip3, rm, find, sed, awk, tar, unzip, diff, chmod ve önceki araçlar. Sandbox aynı: yalnız proje klasörüne yazar, gizli klasörleri okuyamaz, Apple Events servisi kapalı. `osascript`, `open`, `launchctl`, `security`, `defaults` gibi sistemi/başka uygulamayı yöneten komutlar reddedilir (masaüstü araçları yolu).
- Ağ: `network=true` yalnız kurulum/indirme için; her seferinde Berke'ye onay kartı çıkar, turbo modda bile. Riskli komutlar (rm, sudo, git push/reset --hard/clean, chmod -R, kabuğa boru) da her zaman sorar; kartta "İnternet erişimli" ya da "Riskli" başlığı çıkar ve "bu sohbette hep izin ver" düğmesi gizlenir. Gerçek Mac'te doğrulandı: ağ kapalıyken curl çözemez, açıkken 200; proje dışına yazma "Operation not permitted".
- `project_skill`: ekip rehberleri (web-oyun, proje-kurulum, dogrula, hata-ayikla, git-akisi) ve `Application Support/BerkeJARVIS/skills/*.md` içine konan kendi rehberlerin. Kodcu ajanlara "tanıdık işte rehbere bak, bitirmeden gerçekten dene, denemediğini söyle" talimatı eklendi.
- Ortak ekip hafızası: `project_note scope=team` tüm projeler için kalıcı bilgi saklar; her ajanın istemine en çok 1.200 karakter `<team_memory>` olarak girer (NOVA ve planlama hariç).
- Paralel ekip: planın bağımsız adımı `parallel: true` ile önceki adımla aynı anda çalışır; en çok iki adım, aynı bağlayıcıdan ikisi asla (8 GB Mac).
- `project_browser`: ajan yazdığı .html sayfasını gerçek başsız Chromium'da dener (tuş bas, tıkla, metin/sayı/JS ifadesi oku); yalnız proje dosyaları yüklenir, internet kapalı. Önce `Tarayici-kur.command` ile bir kez kurulur (Playwright + Chromium). Kurulu değilse ajan "kurulu değil" der, denendi diye yazmaz.
- Tarayıcı aracı Mac'e kuruldu (Tarayici-kur.command; Playwright paketi BerkeJARVIS/tools/venv içinde, Chromium Library/Caches/ms-playwright içinde). Araç klasörü hem durum klasörünün yanında hem sabit uygulama klasöründe aranır. Gerçek denemede VISION adsız istekle `project_skill` + `project_browser` kullanıp yılan oyununu tarayıcıda oynadı, denemediği kısmı (kendine çarpma) söyledi.
- Doğrulanmadı: sandbox'taki Apple Events engelinin gerçekten işlediği (macOS izin penceresi çıkarmamak için denenmedi); kural geçerli ve komutlar çalışıyor. `osascript`/`open` gibi komutlar ayrıca metin düzeyinde reddedilir.
- Gerçek denemeler (ajan adı verilmeden): yılan oyunu isteği VISION'a gitti, 3 dosya + `node --check`; sonra P tuşu duraklatma da VISION'da; araştırma sorusu EDITH'e gitti, MDN kaynaklarıyla. Yılan oyununu ayrıca gerçek tarayıcıda oynatıp doğruladım. 263 test.

## 2026-11-03 · Ajanlar daha çok uygulama açar, daha çok komut çalıştırır
- `desktop_open_app` listesi: Notes, TextEdit, Safari, Finder + Chrome, Preview, Calendar, Reminders, Calculator, Pages, Numbers, Keynote, Xcode, VS Code, Antigravity. Mail, Messages, Terminal ve Sistem Ayarları bilerek yok. Kontrol isteği algısı Xcode ve Antigravity'yi de tanır.
- VS Code, Xcode ve Antigravity'de ajan açar, bakar ve tıklar; `desktop_type` ve `desktop_key` bu üç uygulamada native tarafta reddedilir (entegre terminal sandbox dışında komut çalıştırırdı). Terminal, Sistem Ayarları, parola ve Anahtarlık pencereleri hâlâ kapalı. Kod yazmak ve komut çalıştırmak için yol: `project_edit`/`project_patch` + `project_command` (sandbox, ağ yok, çıktı ajana döner).
- `project_command` izinli programlar: python3, python, node, npm, npx, swift, xcodebuild, git, rg, ls, cat, pwd + yeni mkdir, cp, mv, touch, grep, head, tail, wc, sort, make. `rm` ve `sh` hâlâ yok.
- Swift değişti: TAM kurulum yapıldı (0.7.6); macOS Ekran Kaydı ve Erişilebilirlik izinleri yeniden verilmeli. 249 test.

## 2026-11-03 · Ödev ve VS Code denemeleri: bulunan hatalar
- Ödev paketi (ODEV.md 31K, CSV 29K, PDF 3 sayfa, 2 JPEG) dört ajana uygulamanın gerçek ek yoluyla verildi. PDF ve görseller doğru okundu; uzun metin/CSV 8.000 karakterle kesilince her ajan "kesik, göremiyorum" dedi, uydurma yok.
- Kesik dosya artık sohbette "Not: … 24.000 / 30.923 karakter" uyarısı gösterir; istemdeki `<document>` etiketi `shown_characters` ve `total_characters` taşır. Tamamı için dosyanın klasörü proje seçilir (VISION/FRIDAY eksiksiz okur).
- Hata: kontrol isteğinde "(Allow / Don't Allow)" yazısı olumsuzluk sayılıp izin kartı açılmıyordu; düzeltildi.
- Yeni araç `project_open_editor`: seçili proje klasörünü Visual Studio Code'da (app=vscode) ya da projedeki bir .html dosyasını varsayılan tarayıcıda (app=browser) açar; onaya tabi, yalnız açar. Codex, Claude Code ve yerel uç nokta aynı listeyi kullanır. Gerçek denemede VISION XOX oyununu yazıp VS Code'da açtı; oyun tarayıcıda denendi.\n- Proje sohbetinde veya VS Code anılan istek ("…ile aç") artık ekran kontrolü isteği sayılmaz.
- Kararsız ekip testi (sunum çağrısı yama dışına taşıyordu) düzeltildi. 248 test.
- Bulgu: masaüstü araçları VS Code, Terminal ve Antigravity penceresinde bilerek çalışmaz (native engel); Cmd+Space de izinli tuşlarda yok. Bekleyen macOS "Terminal wants to control Codex Computer Use" penceresi tıklamaları kilitler; Berke'nin kararı.

## 2026-11-03 · JARVIS brif yazar, uzmanlar yalnız bağlamı kadar görür
- Paslanan iş artık tüm sohbetle değil brifle gider: uzman JARVIS’in brifini (tek satır, ~700 karakter: hedef, gerekli bilgi/dosya adı/sınır, beklenen sonuç), Berke’nin son isteğini ve aynı turda ekibin verdiği çıktıları görür; eski sohbeti görmez. Daha az token. Berke bir ajanı doğrudan çağırırsa (“FRIDAY, …”) eskisi gibi son sohbeti de görür.
- Paslama satırı sınırı 600 → 900 karakter; planlama adım talimatı “uzmanın tüm brifi” olarak yazılır (önceki adımın sonucu dışında başka bağlam yok). Plan isteği projeye bağlıysa JARVIS ekip defterinin son satırlarını da görür.
- Ekip çalışması bitince JARVIS sonucu birkaç satırda sunar (tek koordinatör çağrısı); tam çıktılar birleşik raporda yukarıda kalır. Sohbet değiştiyse veya JARVIS meşgulse sunum atlanır, rapor yine gelir.
- Hata düzeltildi: “Tarayıcıda açılan bir oyun yap” gibi yapım istekleri “bilgisayarı kontrol et” sanılıp izin istiyordu (is_control_request “ac…/yaz…” ile başlayan her kelimeyi sayıyordu: açılan, açıklama, yazılım). Artık yalnız gerçek fiiller (aç, yaz, open, click…) sayılır; “aç” demeyen yapım isteği ekibe gider.
- Gerçek deneme: yılan oyunu isteği → JARVIS brifi → VISION 4 dosyayı yazdı (49 sn) → JARVIS sunumu; proje mini-oyun, VS Code’da açıldı. Ayrıca tarayıcıda denendi: hareket, çarpınca “Oyun bitti!”, yeniden başlat çalışıyor; konsol hatası yok. VISION’a verilen bağlam: görev 207 + ortak sohbet 791 karakter.
- Ekip raporundaki uzman çıktılarından sondaki başıboş HANDOFF satırı temizlenir.
- Karar: JARVIS ve EDITH (Gemini) projeye araçla bağlanmaz; projeyi brif yoluyla bilirler. Dosya/komut araçları VISION ve FRIDAY’de. 241 test.

## 2026-11-03 · Claude Code ile proje araçları, ortak defter, bağlam görünürlüğü
- VISION, resmî Claude Code girişi varsa uygulama açılışında bir kez Claude Code bağlantısına geçer (sonradan elle seçtiğin korunur). Gerçek denemede: Claude Code dosyayı okudu, yamayı attı, testi sandbox’ta koştu, hatayı düzeltti (17-18 sn).
- Claude ajanına yeni araçlar: `project_patch` (tam dosya yerine tek parça yama, onay/yedek aynı), `project_search` (projede metin arama), `project_note` (ortak defter), `project_command` (onaylı test/komut; macOS sandbox: ağ yok, yazma yalnız proje + geçici klasör, anahtar/uygulama verisi klasörleri okunamaz, 5-120 sn). Tur sınırı 8 → 16/28/40 (efora göre).
- Proje başına ortak defter (en çok 40 satır / 4000 karakter): iş bitince ajan adıyla otomatik satır, ajanlar `project_note` ile karar ekler; her ajanın isteğine eklenir. “proje defteri” yazınca gösterilir.
- “ajan bağlamlarını göster”: her ajanın son çağrıda aldığı bağlamın karakter dökümü (görev, ortak sohbet, defter, belge). Model çağrısı yok.
- Proje işi bitiş kapsülü gerçek sayı verir: “VISION proje çalışmasını bitirdi · 1 dosya düzenlendi · 2 komut, 1 başarılı”.
- Planlama ve paslama metinleri güncellendi (Claude Code artık test koşabilir; web yok). 236 test.

## 2026-11-03 · Her türlü araştırma EDITH’te
- JARVIS artık araştırma yapmaz: konusu olan her araştırma isteği (“iPhone fiyatlarını araştır”, “Tesla haberleri”, site site tarama, karşılaştırma) sunucuda doğrudan EDITH’e gider; JARVIS araya yalnız tek satır koyar, EDITH bitirince kapsül + JARVIS sunumu gelir. EDITH’in kotası doluysa FRIDAY araştırır.
- Konu yoksa (“araştır”), kodla karışıksa veya ekip/uygulama hakkındaysa JARVIS ele alır (tek kısa soru / işi böler). Kısa sorular da dahil, aramayla bakılması gereken her şeyi JARVIS EDITH’e paslar; basit günlük sorular için NOVA var.
- Ortak ekip kuralı: JARVIS ve EDITH iki ayrı ajandır; JARVIS araştırmaz, EDITH araştırır, NOVA ayrı hızlı sohbettir, kimse başkasının adına konuşmaz. EDITH’e verilen her araştırma işinde canlı web araması açık (JARVIS işi başka sözlerle paslasa da).
- 219 test.

## 2026-11-03 · Kısa cevaplar, soru kutusu, “gel” çağrıları
- Gemini 5 saatlik kapandı: Antigravity Ayarlar → Models & Usage bu hesapta yalnız haftalık çubuk var (Gemini %65, Claude/GPT %90); 5 saatlik yenileme Google’a göre yalnız AI Pro/Ultra’da. Kartlar uygulamayla aynı rakamı gösteriyor.
- “kanka şimdi bir Vision gelsin / gelebilir mi / çağır” artık açık çağrı: JARVIS araya girmez, ajan tek kısa cümleyle yanıt verir (“Buradayım, söyle.”); kendini tanıtmaz, neler yapabileceğini saymaz, soru listesi çıkarmaz.
- Araştırma + kod karışık veya çok adımlı istek (“araştırın, sonda kodda hata bulun düzeltin”) hızlı kod kısayoluna girmez; JARVIS koordine eder. Eksik bilgi varsa (konu, hangi kod) JARVIS tek kısa soru sorar (“Konu ne kanka?”), uzmanlar Berke’ye soru sormaz, devredilen uzman eksiği tek satırda söyler ve kendi rolünün dışına paslamaz. “yazı” (makale) artık “yaz” sayılmaz. Kısayol satırı da Berke’nin yazdığı dilde.
- Bütün ajanlara ortak kısa cevap kuralı (cevabı öne koy, giriş/özet/menü/kapanış teklifi yok, tek kısa soru); ses, araç, izin konuları yalnız sorulursa anılır; ajanlar ~80 kelimeyi geçmez.
- Ajan Berke’ye soru sorarsa (yanıtın son satırı “?” ile biter) sorunun hemen altında o ajanın renginde cevap kutusu açılır; cevap ana “JARVIS’e yaz” kutusuna değil, sorana gider (`reply_to`), konunun devamı olarak. Soru bekleyen işte bitiş kapsülü ve JARVIS sunumu çıkmaz.
- Sunum ve bitiş kapsülü yalnız gerçek iş (araştırma, kod, proje, uzun yanıt) olduğunda; sohbet düzeyi cevaplara eklenmez.
- 216 test.

## 2026-11-03 · Doğru ajana paslama, bitiş kapsülleri, JARVIS sunumu
- Paslama iş türüne göre düzeltilir (`fit_handoff`): araştırma, haber, fiyat, karşılaştırma, belge okuma → EDITH (yoksa FRIDAY); kod yazma/düzenleme → VISION. Model yanlış ajanı seçse bile sunucu düzeltir; karma işte seçilen ajan kalır. Berke bir ajanı adıyla çağırırsa o ajan cevap verir, yönlendirme karışmaz. JARVIS’e verilen talimat da netleşti (VISION araştırmaz, EDITH kod yazmaz).
- “X çıktısını hazırladı. Sonuç yukarıda” makbuzu kalktı. Uzman iş bitirince kendi renginde kapsül: “EDITH araştırmayı N kaynaktan tamamladı”, “VISION kodu yazdı · N satır”, “… kod düzenlemesini bitirdi”, “… proje çalışmasını bitirdi”. Sayılar yalnız gerçek (yanıttaki farklı site sayısı, kod bloğu satırı), yoksa sayı yazılmaz. Katılım kapsülü içi boş yanıp sönen halka, bitiş kapsülü dolu daire + ✓; ikisi de içeriğe göre genişler ve ortalanır.
- Bitişten sonra JARVIS sunum yapar: iş küçükse 1-2 cümle, büyükse 4-8 kısa satır (kodu/linkleri tekrarlamaz, yalnız uzmanların gerçekten bildirdiğini söyler). Tek model çağrısı (orta düşünme); kota doluysa dürüst yerel satır. Berke adıyla çağırdığı ajanda sunum olmaz; yalnız sohbet edildiyse kapsül de çıkmaz. Görsel okuma yönlendirmesinde sunum yok.
- Sesli yanıt: “Gerisini sana yazılı olarak aktarıyorum” gibi kapanış kalıpları kaldırıldı (kod varsa kısa “Kodu sohbete gönderiyorum” kalır). JARVIS’in devrettiği işte uzman susar, sesli olarak JARVIS’in sunumu okunur.
- Düzenle artık yerinde düzenleme (`edit-message`): mesaj aynı yerde düzenlenir, o noktadan sonrası silinip yeniden yanıtlanır; “Yeni yanıt” aynı mesajı yeniden üretir.
- Sesli oda: Kes / Şimdi konuş düğmesine basmadan konuşmayı sürekli bekler (“Ses duyulmadı” sessizce yeniden başlar); büyük ekran konuşulan dilde yazar, tanıma sürerken “dil algılanıyor” gösterir.
- Ajan kartları sürüklenirken yazı seçilmez; kapalı kartlarda 5 saatlik yüzde varsa o, yoksa “(haftalık)” yüzdesi görünür.
- Gemini 5 saatlik: Antigravity’nin hem `agy /usage` çıktısı hem açık uygulamanın yerel kota servisi bu hesapta yalnız haftalık pencere bildiriyor (Gemini grubu %65 kaldı, Claude/GPT grubu %90 kaldı, 9 Kasım’da sıfırlanır). Google resmî sayfalarında AI Pro/Ultra için “5 saatte bir yenilenir, haftalık üst limite kadar” yazıyor ve başka araçlar `gemini-5h` / `3p-5h` kovalarını okuyor; ancak bu hesabın yerel kaynakları bu kovaları döndürmüyor. Veri gelmeden yüzde uydurulmaz.
- 209 test. HIZLI kurulum (izinler korunur).

## 2026-11-03 · Sohbete özel ses, ajan adıyla çağırma, mesaj altı zaman/işlemler
- Sesli yanıt artık sohbete özel: her sohbet kendi açık/kapalı durumunu hatırlar (`voice_replies`, eylem `chat-voice`); “sesli yanıt verme / düz yaz / konuşma / sustur” o sohbette sesi kapatır. Hoparlör düğmesi o sohbeti değiştirir.
- Ajan adı Türkçe ekle (“visiona dedim”, “Vision’a söyledim”, “Vision gel”, “Edith, orada mısın”) o ajanı çağırır; “çağırma” hâlâ engeller.
- Mesaj altı: SYSTEM mesajlarında saat her zaman görünür, diğerlerinde üzerine gelince; kendi mesajında Düzenle / Kopyala / Yeni yanıt, ajan yanıtında Yeni yanıt.
- Kapalı ajan şeridi artık kartların yüksekliğini izler; “JARVIS Chat” kapsülüne değmez.
- Mikrofon “Otomatik”: Türkçe cihaz içi model yoksa Apple servisi için açık onay penceresi (bu oturum / her zaman / vazgeç). TAM derleme gerekir.
- Modeller: her bağlantı yalnız kendi modellerini gösterir (Gemini ajanlarında GPT-OSS yok).
- Gemini 5 saatlik: resmî `agy /usage` (1.4.12) bu hesapta yalnız haftalık pencere döndürüyor; kart “Bildirilmiyor” der, yüzde uydurulmaz.
- 203 test.

## 2026-11-03 · Eksik iş denetimi ve kontrol doğrulaması
- Gerçek VISION oturumunda ayrı yeni Notlar notuna `selam berke` yazma doğrulandı; not sayısı, oluşturulma tarihi ve editör içeriği kontrol edildi.
- Kısa kod paslaması ve ortak Mac kontrol oturumu sonunda JARVIS yerel teslim kaydı bırakır; ek model çağrısı yok. Özel sohbetler etkilenmez.
- Kontrol onayından sonra kullanıcı mesajının ikinci kez eklenmesi kaldırıldı. Tek kontrol sahibi korunur.
- 199 test. Hızlı güncelleme Mac izinlerini değiştirmez.

## 2026-11-03 · Kısa ve doğrudan izin akışı
Mac menüsündeki kapalı izinler doğrudan açma düğmesiyle gösterilir. Sohbet içinde ihtiyaç olduğunda ekran/kontrol izni istenir; mevcut macOS istemi açılır. Uzun rehber ve kaldır/ekle açıklaması normal akıştan çıkarıldı. Yalnız hızlı güncelleme; native imza değiştirilmedi.

## 2026-11-03 · Daha seyrek kota uyarıları ve açık Google etiketleri
Sohbet uyarıları yalnız 5 saatlik pencerede %25 kullanım eşiklerinde gelir; haftalık değerler kartlarda kalır. Eşikler sohbetler ve açılışlar arasında tekrar üretilmez. Google kartları Gemini · Antigravity olarak ayrıştırıldı; resmî kaynak 5 saatlik yüzde vermediğinde açıkça okunamıyor gösterilir. NOVA’nın aynı bağlantıda bağımsız bir sohbet rolü olduğu açıklanır.

## 2026-11-03 · İzin sorununda uygulama içi rehber
Kontrol izni eksikse görev model çağrısından önce durur, sohbet kaydı ve eylemli zil bildirimi bırakır. Rehberden ilgili Mac ayarları, çalışan JARVIS’in Finder konumu ve izin yenileme açılır. Mac bildirimine tıklama da rehbere dönebilir. İzin anahtarları kullanıcıya aittir; imzalama kimliği değiştirilmedi.

## 2026-11-03 · Görünür fare hareketi
Codex ve Claude Code için desktop_move eklendi; imleç gerçek ekranda taşınır, tıklama aracı da imleci hedefe götürür. Mevcut onay, tek ajan, süre ve güncel ekran gözlemi kontrolleri korunur. Sürekli ekran toplama veya ek model çağrısı yapılmaz.

## 2026-11-03 · Mac metin girişi
Metin gönderilmeden önce gerçek editör odağı doğrulanır. Seçime erişilebilirlik üzerinden ekleme, ardından temiz tuş bayraklarıyla Unicode gönderimi kullanılır; parola alanı engeli korunur. Boş editör odakta değilse açık hata verilir. Swift kontrolü ve 195 test geçti; Notlar’da canlı yazma doğrulaması bekliyor.

## 2026-11-03 · Ortak sohbet Mac kontrol düzeltmesi
JARVIS’in VISION’a verdiği kontrol izninde ajan sahibi sohbet kanalıyla karıştırılıyordu. Gerçek kontrol sahibi doğrulanır; çalışma ve sonuç JARVIS sohbetinde kalır. 195 test geçti, yanlış sahip ve süresi dolmuş izin reddi korunur.

## 2026-11-03 · Yerel interaktivite ve çalışma özeti
- Ajan kartlarında 15 ağırlıklı TR/EN yerel karşılama; uzun aradan sonra mesaj gönderince dönüş selamı. Model kotası yok.
- Büyüyen sohbet çizgileri, geniş önizleme, renkli ve gerçek işlerden oluşan çalışma özeti; SYSTEM artık ajan sayılmaz.
- Kontrol izin süresi 10–120 dakika seçilebilir. Yeni Notlar görevinde boş not açma yönlendirmesi; başarısız adımları tekrarlamama ve anlaşılır tur sınırı hatası.
- 194 test. İmzayı değiştirmeyen hızlı kurulum.

## 2026-11-03 · Claude — server-live, izin ipucu, HIZLI/TAM güncelleme
192 test. Sunucu/web dosyaları Application Support/server-live’dan çalışır → kod güncellemesi uygulamayı yeniden imzalamaz, macOS Ekran Kaydı/Erişilebilirlik izni bozulmaz. Guncelle.command HIZLI/TAM kipleri. Kontrol kartında izin “—” ise − / + ipucu. Kota notuna saat.

## 2026-11-03 · Claude — ajan başına sohbet, ses yönlendirmesi, ekran küçük resimleri
191 test. Üst ajan kartı = o ajanın bağımsız sohbeti (`agent-chat`, `home_agent`). Kısa “sesli konuş” istekleri yerelde yanıtlanıp sesli yanıtı açar. Çalışma satırında gerçek ekran karelerinin küçük resimleri (hafıza, tıkla-büyüt). Takım şartnamesine ses bilgisi. Guncelle.command günlük dosyası. Yeniden açılışta ajan kanalı korunur; chat’ten zamanlama yalnız net isteklerde.

## 2026-11-03 · Claude’a devir hazırlığı (kurulmadı)
Kaynak 183 test ve Swift typecheck geçti. Doğal Mac isteği/desktop araçları, NOVA bağımsız istemi, kalıcı kota kaydı, görev kartları ve chatten zamanlama yazıldı; son kaynak kurulu değil. Canlı QA, ses yetenekleri ve ayrı ajan sohbetleri açık kaldı.


## 2026-11-03 · Codex — referans görsellere göre çalışma özeti
- Sohbet içi çalışma satırları sade: renkli ajan adı, gerçek eylem, geçen süre ve açılır işlem kaydı. 650 ms’de eski adımları döndüren animasyon kaldırıldı; yalnız güncel işlem gösterilir. Yinelenen ayrı faaliyet kutuları gizlenir; kayıtlar korunur.
- Sağ özet paneli yeniden tasarlandı: ferah zaman çizelgesi, açılır komut/arama/dosya kayıtları, sade simgeler, kontrollü mavi tonlar. Mevcut gerçek bilgisayar karesi yalnız mevcut oturumda gösterilir; sahte ekran önizlemesi üretilmez.
- Google ACTIVE/RUNNING/DONE aynı işlem için tek sayılır; gerçekten tekrarlanan çağrılar ayrı kalır. Yeni test bu ayrımı doğruluyor. Seçilen ajan kanalı dışındaki konuşmalar özet/araç listesine karışmaz; süzülmüş mesajlar tur başına önbelleğe alınır.
- Bildirim menüsü değişmedikçe yeniden çizilmez; buton tıklarken kaybolma sorunu azaltıldı. Mac’e geri dönünce bildirim izni tekrar okunur. Zil içinden gerçek macOS bildirim izni istenebilir.
- Berke Mac’e geldiğini söyledi; Sistem Ayarları > Bildirimler > JARVIS açıldı. Anahtara Codex basmadı (son gözlem Off). Ücretli API, telefon kodu, Keychain veya imza yöntemi değişikliği yok.
- 179 test geçti; native kurulum doğrulaması yapıldı. Gerçek eski araştırma kaydında tek arama sayımı, özet paneli ve ham işlem ayrıntısı açılması Mac UI’da doğrulandı. Yeni model çağrısı yapılmadı. Kanıt: ../JARVIS-calisma-ozeti.png.

## 2026-11-03 04:38 PT · Codex — son doğrulama
- 178 test ve son Guncelle.command geçti; uygulama açık. VISION Kota sekmesi açıkken Yenile: okuma zamanı 04:34:52’den 04:36:22’ye geçti, sekme ve gerçek yüzdeler korundu. Ayrıntılar QA tamamlandı.
- JARVIS-Mac.zip üretildi ve CRC/imza kontrolü geçti; son belgelerle yeniden paketleniyor. Kaynak/kurulu app.py, chat_workflow.py, scheduler.py, statik dosyalar md5 eşleşti. Kanıtlar: ../JARVIS-kota-dogrulama.png ve ../JARVIS-buyuk-gorsel-qa.png.
- Önceki kullanıcı sohbetine dönüldü; taslak boş; deneme zamanlamaları kaldırıldı. Mac bildirimi izin durumu pending, gerçek banner/Dock dış görünümü açık. İmza yöntemi, Keychain, telefon kodu veya ücretli API değişmedi.

## 2026-11-03 · Son QA güncellemesi (Codex)
- Ayrıntılar düğmeleri kartlar GENİŞKEN görünür; önceki 04:25 notundaki “gizli” ifadesi yalnız dar kart içindi. VISION Genel ve Kota sekmeleri Mac’te açıldı; 5 saatlik %100 kalan ve haftalık %73 kalan, resmî /usage kaynağıyla görüldü. Açık kota penceresi resmî okuyucu bitince artık kendini güncelliyor.
- Görsel önizlemesi taslakta ve kalıcı ekte geçti; sonrasında model ayarları normal boyutta açıldı. Deneme eki ve taslak silindi, hiçbir görsel yeni modele gönderilmedi.
- 04:29 arka plan denemesi de bir kez çalıştı. Test zamanlamaları kaldırıldı; geleceğe dönük deneme görevi bırakılmadı. Mac bildirim izni hâlâ “pending”; banner teslimi/Dock dış görünümü onay gerektiren açık QA olarak korunuyor.
- Kurulum 178 test ile geçiyor. Devir yapılmadı; Claude’a mesaj gönderilmedi. Telefon uygulamasına dokunulmadı.

## 2026-11-03 04:25 PT · Codex devam durumu (devir değil)
- Berke’nin son talimatı geçerli: Claude’a otomatik devir YAPILMADI. Eski %4/00:20 devir notu tarihsel.
- 178 test geçti; Swift typecheck ve Guncelle.command ile yeniden açılma başarılı. Sorun Swift sözdizimi değil, yinelenen modül önbelleğiydi; cache normalize edildi.
- Limit çipi gerçek veriyle çalışıyor; sayfa açılışındaki state-undefined hatası giderildi. Sistem bildirim izni okunuyor ve zil ipucunda gösteriliyor. Mac uygulamasının ön/arka odağı AppKit olaylarından da okunuyor.
- Zamanlanmış görev ekleme/çalıştırma/silme; 04:10 tek sefer otomatik başlatma ve zil bildirimleri canlı doğrulandı. Başarısız sonuç başarı bildirimi üretmiyor; geçmiş tek seferlik görev yanlışlıkla yeniden etkinleşmiyor (2 yeni test).
- Orkestra ilk adım kurulu: açık orkestra isteği + VISION; adı verilen uzmanlar temiz bağlamla, özetleri VISION’a, son sunum JARVIS’e. Alt görev durum kartı. Ek ücretli API yok; gerçek Claude kota çağrısını tüketmemek için yeni akış sahte istemcilerle test edildi (2 test).
- 220 mesajlık ayrı, entegrasyonu kapalı QA sohbeti: değişiklikte 219 eski DOM satırı korunuyor; örnek tam katman güncellemesi ~30 ms. QA sunucusu/penceresi kapatıldı.
- Büyük görsel QA tamam: gönderilmiş resim ve taslak foto tam pencereye sığdı; Kapat ve normal ayar boyutuna dönüş geçti. Deneme taslağı gönderilmeden temizlendi. Kanıt: ../JARVIS-buyuk-gorsel-qa.png.
- İzin menüsü salt okunur/onay/dosya/Turbo + “klasör bağlı değil” + Mac kontrolü ayrı açıklamaları canlı görüldü; izin seçimi değiştirilmedi. Eski Genel/Kota Ayrıntılar düğmeleri yeni kart tasarımında gizli; güncel görünür ayarlar ve profil kotası kullanılıyor, eski modal QA’sı bunlarla aynı şey değildir.
- AÇIK: macOS sistem bildirimi izni henüz seçilmemiş (zil: permission pending). Banner’ın gerçekten ekranda görünmesi ve Dock rozetinin dış görünümü henüz kanıtlanmadı; Berke’nin izin seçimi gerekebilir. Sistem anahtarına basılmadı. Yeni bağımsız orkestra akışının gerçek Claude testi kota sonrası yapılabilir.


## 2026-11-03 · Codex — zamanlama / limit / orkestra
- 174 taban test ve 2 yeni orkestra testi geçti (176). Zamanlanmış paneli, görev ekleme/şimdi çalıştır/silme, gerçek 04:10 tek sefer otomatik çalıştırma ve zil rozeti Mac uygulamasında doğrulandı. Limit çipini engelleyen state henüz yüklenmedi başlangıç hatası düzeltildi; gerçek Claude %98 kullanım uyarısı göründü.
- Orkestra ilk adım: açık orkestra + VISION isteğinde yalnız adı geçen uzmanlar, temiz atanmış bağlam, VISION’a sınırlı özet, son sunum JARVIS. Görev/durum kartı var. Gerçek Claude kotası %2 olduğundan model çağıran orkestra testi yapılmadı; sahte istemciyle çağrı sırası ve eski sohbetin gönderilmemesi doğrulandı.
- app.js değişmeyen mesaj DOM’larını korur; 220 mesajlık ayrı QA fixture’de her değişimde 219 satır yeniden kullanıldı, örnek güncelleme ~31 ms. Bu ölçüm gerçek sohbet veya model benchmarkı değildir. Büyük görsel/ayrıntılar QA ve Mac banner görünürlüğü kontrolü sürüyor.
- Dosyalar: Guncelle.command, native/build.sh, native/Jarvis.swift (salt okunur bildirim izin durumu), static/{app.js,sidebar.js,polish.js,focus.css}, chat_workflow.py, app.py, tests/test_quota_workflow.py. İmza yöntemi/Keychain değişmedi; ücretli API yok.

## 2026-11-03 · Kurulum kurtarma
- Swift önbellek yolu normalize edildi; yinelenen Darwin modülü kaynaklı derleyici çökmesi önlendi. Temiz cache typecheck başarılı; kurulum doğrulaması sürüyor.

# 0.7.6 (devam) — Ajan sesleri, sabit modeller, kontrolü sohbetten verme

- Zamanlanmış görevler + bildirim zili (YENİ, scheduler.py): sol menüde "Zamanlanmış" (bir kez/her gün/hafta içi/saatlik, şimdi çalıştır, aç-kapat; görev yeni sohbette başlar). Zil: ekip işi/görev bitti, onay/izin gerekti, kota %10 altı, zamanlanmış görev çalıştı/bitti/kaçırıldı. Arka plandayken Mac bildirimi + Dock rozeti (Jarvis.swift postBanner). Mesaj kutusunun üstünde "limit %91 kullanıldı" çipi. JARVIS açıkken çalışır. Testler: 174.
- Etkinlik paneli: pill artık ileriye dönük toplamı gösterir ("Adım 9 / 20"). Toplam; çalışan ekip sırasının kalan aşamaları + JARVIS'in sunumu + sıradaki görevlerden gelir, bunlar soluk/kesik çizgili satırlar olarak zaman çizelgesinde görünür. Plan yoksa toplam = şu ana kadarki adım (tahmin uydurulmaz). Testler: 160.
- Etkinlik panelinde İlerleme artık araç günlüğü değil görev listesi gibi: "Görev: <ne istedin>", sonra ajan başına kısa adımlar ("EDITH · webde araştırdı · 6 adım", "VISION · komut çalıştırdı", "JARVIS · yanıtladı"). "Adım N / M" bu görev adımlarını sayar. Tek tek arama, komut ve dosyalar "Bu oturumda kullanılanlar" listesinde kalır.
- Mesajlar geldikçe sohbet kendiliğinden aşağı iniyor ve sen yukarı kaydırana kadar en yeni mesajı takip ediyor. Yukarıdaysan yerin korunur, altta "Son mesaja in" düğmesi çıkar. Kendi mesajını gönderince ve sohbet değişince yine en alta iner.
- Kaldırıldı: sohbet altındaki "EDITH › VISION › JARVIS" aşama şeridi (ilerleme Etkinlik panelinde) ve Arşiv düğmesi / menü maddesi / ⇧⌘A. Eski arşivli sohbetler bir kez geri getirilir, bütün sohbetler günlere göre listede kalır.
- Sol üstteki J logosu artık sayfayı yenilemiyor; ana sohbete döner ve yazı alanına odaklanır (eski bir kopya açılmasının sebebi logonun gerçek bir bağlantı olmasıydı).
- Ajan kartlarında kota satırının altına rol ve model eklendi: "Araştırma · 3.8 Flash · Medium", "Ana programcı · Claude Sonnet 4.6".
- Sohbetin adı en üstte, yanında küçük bir ok (Claude ve ChatGPT uygulamaları gibi). Ok sohbet menüsünü açar (adını değiştir, sabitle, arşivle, kopyala, paneli göster/gizle, sil); eski "…" düğmesi kalktı.
- Etkinlik paneli üst çubuğu Cowork gibi: globe (kaynaklar, varsa), "Adım N / M" hapı, Paylaş (sohbeti kopyalar), "…". M sohbetin gerçek toplam adım sayısı, N seçtiğin adım (varsayılan en son); zaman çizelgesindeki bir adıma tıklayınca N değişir, çizelge tüm sohbetin adımlarını gösterir ve fare tekerleğiyle kayar (yukarı kaydırınca yeni adım seni aşağı çekmez).
- Sohbette çalışma satırı ChatGPT gibi canlı: "Web'de arama yapıyor · 3/7 · python reverse list…" hızlıca dönen sayaç ve aranan/okunan kaynak.
- Dil: arayüz dili yalnızca Ayarlar → Dil & ses'ten değişir (Türkçe / English), yazdığın dil onu değiştirmez. Ajanlar ise her mesajda yazdığın dilde yanıt verir; arayüz dilinden bağımsız (çok kısa mesajda sohbetteki son mesajlarının dili sürer). Araştırma varsayılan global ve İngilizce kaynaklarla yapılır, yalnızca Türkiye'ye özel konuda Türkçe aranır; yanıt senin dilinde gelir.
- Etkinlik paneli Cowork'taki gibi: üstte "Adım N / M" hapı (M yalnızca gerçek görev listesi varsa; plansız işte "Adım N"), İlerleme zaman çizelgesi (dikey çizgi, eski adımlar soluk, son adım parlak), Bilgisayar kullanımı bölümü (kontrol sırasında gelen son ekran karesi, "Canlı · Arka planda · ajan" rozeti, Durdur), Kaynaklar ve "Bu oturumda kullanılanlar" (Yüklenen, Ajan çağrıldı, Web araması, Komut, Dosya okuma/düzenleme; ikon + ad + sağda gri ayrıntı). Hap ve panel yalnızca o sohbette adım, plan veya bilgisayar karesi oluşunca belirir; boş sohbette gizli. ⇧⌘E açar/kapatır.

- Her ajanın kendi sesi var (Supertonic F1–F5, M1–M5): JARVIS F4, VISION M3, FRIDAY M5, EDITH F3, NOVA F2, KAREN M2. Ayarlar → Dil & ses → Ajan sesleri (Dinle düğmeli). Konuşma ×1.28 hızlı. Sesli yanıt kısa özet + doğal devir cümlesi söyler ("Gerisini sana yazılı aktarıyorum", "Sonuçları sohbete gönderiyorum" gibi); "Ayrıntılar sohbette" kalıbı kalktı. Eksik ses ön ayarları build sırasında resmî depodan indirilir, F1 ile şekil kontrolünden geçer (TAKIM/ses-indirme.txt). Eksik ses olursa macOS sesine düşer.
- Ajan renkleri sohbette de görünür (satır, avatar, ad, sol çizgi). Mesaj çubuğu Codex tarzı ince/sık çizgiler, geniş önizleme kartı (yer imi simgesi) ve kendi şeridi; avatarın üstüne binmez.
- "+" araç menüsü yazı alanının üstünde açılan menü.
- Modeller: otomatik low/medium/high geçişi varsayılan kapalı ("Derinliği kendiliğinden ayarla" ile açılır). Model seçici model ve derinliği ayrı satırlarda sunar (Gemini uygulaması gibi). Seçilen ayar JARVIS ajanı çağırdığında aynen uygulanır (agent.pinned, jarvis_model_pinned; "Paslama → X (low)" ipucu artık modeli değiştirmez). Antigravity listesinde yalnızca 3.8 Flash var; Pro/Flash-Lite çıkınca seçilebilir. NOVA hızlı küçük sorular (Flash Low), OpenRouter ajanı KAREN. Kartlarda Antigravity yerine Gemini yazar.
- Codex tarzı çalışma satırı: "Komut çalıştırıyor 6 dk 47 sn ▸" / "Web'de arama yaptı, 7 komut çalıştırdı ▸". Açılınca adım satırları (üçgenle ham komut); uzun işlerde "Çalıştı 35 dk 46 sn" ayracı.
- Sağ Etkinlik paneli (⇧⌘E): İlerleme (adım/görev), kaynaklar, dosyalar, sohbette çalışanlar, kullanılan araçlar, bilgisayar kontrolü Durdur. Başlıktaki "…" sohbet menüsü: ad değiştir, sabitle, arşivle (⇧⌘A), sohbeti kopyala, paneli göster/gizle.
- Sohbetten kontrol: "tamam kontrolü al" deyince seçilen ajan (Claude Code veya Codex) bu sohbet için tek seferlik izin kartı gönderir. İzinden sonra aynı sohbette tekrar sormaz. Rutin eylemler tek tek sorulmaz; parola alanı, Terminal, sistem izin pencereleri, mesaj gönderme/ödeme/silme sınırları aynen sürer. Durdur izni geri alır. macOS Ekran Kaydı ve Erişilebilirlik yalnızca JARVIS için açık olmalı.
- Guncelle.command başına Swift sözdizimi kontrolü eklendi; hata varsa uygulama kapatılmaz.

# 0.7.6 — Kota, önizleme ve ekip sohbeti

- Claude Pro kotası artık resmî CLI'nın JSON `/usage` komutundan okunur. Yanıtta `local_command=usage`, `num_turns=0`, `duration_api_ms=0`, sıfır token ve sıfır maliyet doğrulanır. Anahtar/özel OAuth uç noktası veya ücretli API fallback yok. 5 saatlik ve haftalık havuz, kaynağı ve yenilenme zamanı gösterilir. Rutin okuma saatte bir; Kotaları yenile düğmesi elle yeniler.
- JARVIS/EDITH aynı Google havuzunu, Claude Code kendi Claude Pro havuzunu gösterir. Ek roller de seçili bağlayıcının mevcut havuzunu kullanır; yeni kota yaratmaz. OpenRouter anahtarı yoksa kota bilinmez; sahte yüzde eklenmez.
- Görselin hem gönderilmeden önceki küçük resmine hem mesajdaki resmine basınca pencereyi kaplayan önizleme açılır. Escape/Kapat ile dönülür; büyütme model çağırmaz.
- Kartlarda kısa rol ve bağlantı adları; Genel/Kota sekmeli Ayrıntılar ile metinler tam okunur. Provider default yerine Otomatik model kullanılır. Yanıtlardaki model etiketi o istekte CLI'ya gönderilen seçimdir; AI'ın kendi söylediği isim değildir. Efor etiketi gerçek uygulanan eforu gösterir.
- Seçili ajan başlığı ajan renginde canlı rozet olur. Model çalışırken çekirdeği hareketlenir; azaltılmış hareket tercihi korunur.
- İzin ekranı desteklenen araçları, bağlı klasörü ve bu sohbetin açık/kapalı proje modunu ayırır. Claude Code dosya okuma/düzenleme, Codex dosya/test destekler. Free yerine İzinli yazılır. Proje modu açıkken çağrılan geliştiriciye aynı sınırlı/onaylı proje araçları aktarılır; Gemini proje düzenleyici yapılmaz. Mac kontrolü ayrı süreli oturumdur.
- Açıkça birden fazla ajanla iş istendiğinde araştırma → kod → istenen test/inceleme → JARVIS sunumu sırası kullanılır. Küçük sorular veya tek ajan soruları bütün ekibi çalıştırmaz. Başlangıç yönlendirmesi Python'dadır; yalnızca istenen uzmanlar ve bir son JARVIS yanıtı çağrılır.
- Ara cevaplar silinmez; tamamlanan uzman adımları açılır kayıt olarak tutulur. Son sunumu JARVIS yapar. Hata/iptalde zincir durur; sohbet değişince sıradaki adım duraklar, kendiliğinden başka sohbet bağlamı alınmaz.
- Gerçek Google araç olayları canlı işlenir; araştırma konusu/gerçek URL'ler sohbet içinde hareketli simgelerle gösterilir. Sahte web gezintisi yok; üçüncü taraf favicon izleme servisi kullanılmaz.
- Sohbet sütunu 820 → 1100 px; kenar boşlukları azaldı, yazı alanı ve ekip şeridi aynı genişlikte. Kod blokları global `pre{min-height:220px}` yüzünden boş yer bırakmaz (`.chat-code{min-height:0}`).
- Sağ kenarda mesajlara atlayan çizgi şeridi (`static/rail.js`): her mesaj bir çizgi (70'ten fazlaysa yalnız kullanıcı mesajları), tıkla → o mesaja kayar, aktif konum parlar; 900 px altında gizlenir.
- Ekip rolleri ayrıldı (`chat_workflow.py`): EDITH yalnız araştırma verisi + gerçek URL, VISION yalnız kod + en çok 3 satır not, FRIDAY yalnız test/inceleme kararı; JARVIS yalnız 3-5 satırlık sunum (kodu/tabloyu tekrar etmez). Uzman adım kartları varsayılan açık ve "EDITH · araştırma", "VISION · kod" gibi etiketli.
- Ekip ilerleme şeridi yalnız ekip işinin yapıldığı sohbet kanalında görünür; diğer ajanların sohbetinde artık çıkmaz. VISION kota ipucu canlı veriyle güncellenir.
- Sol panel ChatGPT tarzı: gün gruplu sohbet listesi, daraltılabilir kenar çubuğu (durum hatırlanır), profil menüsü (kalan kota, geçmiş, arşiv, ayarlar ⌘,) ve “Bu Mac” bağlantı/izin durumu. Mesaj çizgi şeridi sola alındı; üzerine gelince Claude gibi tek turluk kart açılır.
- Yeni sohbet kuralı: boş sohbet varsa ona gidilir, yenisi açılmaz; listede tek boş satır. İzinler tek yerde: sohbetteki kalkan düğmesi ChatGPT tarzı seçici açar ve seçimi hemen uygular. Bu Mac penceresinde bağlantı durumları (yeşil/kırmızı) ve “Hepsini test et”. Ajan sırası JARVIS, VISION, FRIDAY, EDITH.
- `Guncelle.command` son adım olarak `native/package.py` ile `../JARVIS-Mac.zip` dosyasını günceller (hata verirse kurulum yine geçerlidir).

Doğrulama: 136 otomatik test geçti. JSON Claude kotası gerçek CLI ile alındı. Kurulum sonrası Mac'te görüldü: geniş sohbet sütunu, çizgi şeridi, açık uzman kartları; gerçek EDITH → VISION → JARVIS akışı rolleri ayrı çıktı verdi. ZIP 0.7.6 olarak yeniden üretildi. Canlı QA açık kaldı.

Resmî kaynaklar: https://code.claude.com/docs/en/cli-reference ve https://code.claude.com/docs/en/costs


## Onceki surum notlari

# v0.7.5

- Kalıcı görsel küçük resmi/büyütme; güvenli, sohbet kapsamlı belge yükleme ve metin çıkarma; yerel PDFKit/OCR.
- Üç temel araç ve katlanır gelişmiş bölüm.
- JARVIS Google kotası; Claude Pro saatlik resmî /usage okuyucu (resmî ekran elle açıldı; otomatik okuyucu doğrulanamadı, sahte yüzde yok).
- Claude 0.7.5 hazırlıkları korundu: kısa görsel yanıtı, motor etiketleri ve sade izin açıklamaları.
- 129 test geçti; PDF metni yerel Swift okuyucuyla doğrulandı.

# v0.7.4

- **İzin düzeyleri:** izin menüsüne **"Tam erişim · Turbo"** eklendi: seçili proje klasöründe dosya düzenleme **ve** izin verilen test komutları (unittest/pytest/npm test…; internet kapalı, klasör dışına çıkmaz) sormadan çalışır. Bilgisayar kontrolü Turbo'da bile her seferinde senden onay ister. Her seçenek için açıklama metni var.
- **Onay kartlarında "Bu sohbette hep izin ver"** (Claude'daki gibi): dosya/test onayında tek tıkla o sohbeti Turbo'ya alır; bilgisayar eylemleri için bu düğme yoktur. Salt-okunur sohbet yükseltilmez.
- **Mac izinleri** izin menüsünde: Ekran kaydı ve Erişilebilirlik durumu (açık/kapalı) + "Mac izinlerini iste" düğmesi. macOS penceresini yine sen onaylarsın; JARVIS kendi başına izin veremez.
- **Fotoğraf ve video ekleme (📎):** yazı alanının üstündeki ataç düğmesi, sürükle-bırak veya yapıştırma. Fotoğraf 1600 px JPEG'e küçülür; video, zaman damgalı en çok 6 karelik tek bir JPEG "kontak sayfasına" dönüşür (video dosyası hiçbir yere gönderilmez).
- **Görsel akışı koordinatör odaklı:** görseli JARVIS'e verirsin; JARVIS görseli okuyabilen tek ajana (şu an FRIDAY/Codex) devreder ve sohbete kısa not düşer. Okuyan ajan cevabına "Visual note:" (görünenler, yazılar, hatalar, sayılar) ile başlar; böylece görseli göremeyen ekip arkadaşları (VISION, EDITH, JARVIS) aynı sohbetteki nottan çalışır, gerekirse `HANDOFF` ile ilgili ajana paslanır. Aynı sohbette "FRIDAY'e sor, fotoğraftaki hatayı açıklasın" denirse son görsel (45 dk, yalnızca bellekte, diske yazılmaz) Codex ajanına yeniden verilir.
- CSP'ye yalnızca `media-src 'self' blob:` ve `img-src … blob:` eklendi (videoyu kareye çevirmek için).
- **Gemini (JARVIS) görseli doğrudan okur:** JPEG, JARVIS'in özel `google-chat-workspace` klasörüne yazılır, `agy` yalnızca o dosya için `read_file` ile açar, tur bitince dosya silinir. Basit sorulara JARVIS kendisi yanıtlar; gerekirse `HANDOFF:` ile ilgili ajana paslar (baş yazılımcı/araştırma). Bu yol **kendi kendini sınar**: bundled `static/vision-selftest.jpg` ile `state.vision` (`unknown|testing|ok|no|error`, `variant`) tutulur; ancak sınav geçince JARVIS'e görsel verilir, geçmezse görsel eskisi gibi FRIDAY'e gider. İzin varyantları sırayla denenir: `review` → `strict` → `open`. Açılıştan ≈25 sn sonra bir kez (sürüm başına) otomatik sınanır; JARVIS ayarlarında "Image reading (Gemini)" kutusu + "Test image reading" düğmesi.
- **Çalışan ajanlar balonu (`static/pulse.js`):** yazı alanının üstünde kimin çalıştığı görünür: ajan adı, ne yaptığı (düşünüyor/yazıyor/projede çalışıyor/araştırıyor/bilgisayarı kullanıyor), kısa özet ve geçen saniye. Aynı anda çalışanlar birlikte, başka sohbet/projedeki işler "sohbet · proje" etiketiyle listelenir; satıra tıklayınca o sohbete geçilir. Sunucu tarafı `active_work()` (`state.active_work`).
- Testler 98 → 118.

# v0.7.3

- **Basit kod isteği JARVIS tarafından kendiliğinden bir kod ajanına gider** ("Python'da hello world komutu ver"): önce Claude (VISION, saf kod), sonra ChatGPT/Codex, sonra Antigravity Claude; kotası dolu/kapalı ajan atlanır. JARVIS sohbette kısa bir bildirim yazar, Gemini çağrısı harcanmaz. Zor/uzun kod istekleri JARVIS'e (Gemini) gider ve o paslar; "efor" derecelendirmesi aşağıda.
- **Zorluğa göre efor:** JARVIS paslarken işi derecelendirir (`HANDOFF: AD/low|medium|high: görev`). Çağrılan ajan o kadar düşünür: Codex ve Claude Code için `effort`, Gemini ajanı için aynı Flash ailesinin low/medium/high modeli. Ajan ayarlarında elle seçilmiş efor varsa o geçerli. Takım planı adımları da `effort` taşır; mesajın model etiketinde `effort …` görünür.
- Koordinatör istemi: kod isteğini kendisi yazmak yerine kod ajanına paslar.
- **Takım şeması her ajana öğretildi:** her istemin başına aynı kısa "TEAM CHARTER" eklenir (JARVIS koordinatör; VISION ana/baş yazılımcı; FRIDAY yardımcı yazılımcı + araştırmacı; EDITH araştırmacı/tasarımcı; Berke hedef ve onay sahibi). Berke'nin ayrıca kendi ChatGPT'sini açıp öğretmesi gerekmez. Eski varsayılan roller tek seferlik migrasyonla yenilenir (elle yazılmış roller korunur). Aynı şema proje yönerge dosyalarında da var.
- Testler 88 → 98.

# v0.7.2

- **Ajanlar aynı sohbette çalışır.** "EDITH’i çağır", "@FRIDAY", "FRIDAY ve EDITH’i çağır, birlikte bakın" yazınca çağrılan ajan ortak sohbette kendi adıyla yanıt verir ve son konuşmaları görür; birden çok ajan sırayla konuşur, sonraki öncekinin yanıtını görür. Düz anma ("EDITH nedir?") veya olumsuz ("çağırma") çağrı sayılmaz.
- **JARVIS kendisi paslayabilir.** JARVIS (ve çağrılan ajan) gerekirse yanıtını `HANDOFF: AD: görev` satırıyla bitirir; uygulama satırı gizler, ilgili ajanı aynı sohbette çağırır. En fazla 2 paslama, aynı ajan iki kez konuşmaz, kotası dolu/kapalı ajan seçilmez, sohbet değişirse durur ve "Paslama yapılmadı" notu düşer. Ayarlardan kapatılabilir (`auto_handoff`). Roller: araştırma → EDITH/FRIDAY, saf kod → VISION, terminal testi → FRIDAY.
- **Koordinatör için güçlü Gemini.** JARVIS'in tavanı `gemini-3.8-flash-high`; her mesajda otomatik seçilir: kısa sohbet `low`, orta `medium`, plan/paslama/uzun istek `high`. JARVIS ayarlarında "Otomatik" seçeneği; belirli bir model seçersen sabitlenir (`jarvis_model_pinned`).
- JARVIS ayar penceresi: "Otomatik" model seçeneği ve "ajanları kendisi çağırsın" anahtarı; metinler yeni davranışı anlatıyor.
- Plan istemine rol bilgisi eklendi (FRIDAY araştırma+kod+test, VISION saf kod, EDITH araştırma+tasarım).
- Testler 78 → 88. Gerçek denemeyle doğrulandı: "EDITH’i çağır" → EDITH aynı sohbette yanıtladı; JARVIS işi kendiliğinden VISION’a paslayıp kodu aynı sohbette getirdi.

# v0.7.1

- Kota tasarrufu: tek seferlik migrasyonla koordinatör/Gemini ajanları `gemini-3.8-flash-low`; yalnızca canlı web araştırmasında otomatik `medium`, `auto_effort` ile kapatılabilir.
- Arayüz metinleri düzeltildi: VISION kendi Claude Pro girişi veya Antigravity; FRIDAY onaylı dosya/komut ve süreli bilgisayar kontrolü.
- Dayanıklılık: Keychain okunamazsa çökme yok; `server-errors.log` hata günlüğü.
- Ses: sesli yanıt artık tüm metni değil kısa özeti (≈1-2 cümle, en çok ~200 karakter) okur; kod/link/liste okunmaz, "Ayrıntılar sohbette." eklenir. Doğal ses hızı 0.97 → 1.18.
- Düzeltme: yeniden açılışta VISION "Sign-in required" görünüyordu; Claude oturumu artık arka planda salt-okunur denetleniyor (`claude auth status`).
- Testler 69 → 78. Derleme `native/build.sh` ile Mac'te yapılmalı.

# v0.7.0

- Geçmiş normal sohbet listesidir: dosya/editör düğmeleri kaldırıldı; kapat, yeniden adlandır, sabitle, arşivle ve onaylı sil menüsü eklendi.
- Gemini gerçek web araştırması; bağımsız Claude Pro geliştirici; Codex test/inceleme. İlgisiz konuşmaları taşımayan dar bağlam.
- Tek yönetici planı, açık başlatma ve hata/yarım sonuç için kullanıcı seçimiyle ajan devri. Otomatik ücretli fallback yok.
- Süreli Claude/Codex ekran-fare araçları ve durdurma; gerçek Mac kontrol testi macOS izinlerini bekliyor.
- JARVIS sağlayıcı/modeli bağımsız; düşünme ayarları gerçek model seçeneklerine iletilir.

# v0.6.1

- Bağımsız Claude Pro / resmî Claude Code bağlantısı; gerçek yanıt ve onaylı proje dosya değişikliği doğrulandı.
- Claude için oturuma bağlı yerel MCP dosya araçları; API anahtarı fallback yok, komut/fare aracı yok.
- Claude/ChatGPT görev devri ve sağlayıcının bildirdiği tokenleri kullanan kullanım özeti.

- Sohbet temiz sayfa açar; Projeler geçmiş çalışmaları toplar. Fazladan Yeni sohbet/Sohbetler düğmeleri kaldırıldı.
- JARVIS’in bağımsız yönetici bağlantısı; EDITH model ayarından ayrıldı.
- Tek yönetici çağrısıyla 0–3 uzmanlık işi planlama; somut planı sohbetten başlatma, otomatik herkesi çağırmama.
- Ajan rafında görünür kaydırma çubuğu kaldırıldı; tutup yatay sürükleme korundu.
- Geçmiş/öğrenme açıklaması, isteğe bağlı gerçek yerel yardımcı ekleme.
- Muse, DeepSeek ve Claude Pro önerileri resmî güncel kaynaklarla araştırıldı.

# v0.6.0

- JARVIS: Gemini Flash ana sohbet; sıradan mesajlar otomatik Codex/Claude tüketmez.
- Tek üst ajan seçimi, doğru yazı alanı adı, dört kartlık kaydırılabilir raf, yuvarlak ortak ok.
- Ajan başına gerçek model/düşünme ayarları, resmi katalog yenileme ve gerçek yanıt testi.
- OpenRouter ücretsiz alternatif kartı; anahtar/bağlantı durumu ve ücretli geçiş engeli.
- Özel ajan geçmişleri, sohbet/ajan kapsamlı notlar ve dar görev paketleri.
- Onaylı gerçek proje araçları, komut sonuçları ve sohbet içi çalışma durumu.
- Açık başlatılan EDITH → FRIDAY → VISION ekip akışı; Python sonuç raporu.
- Otomatik konu başlığı, sabitleme/arşiv düğmeleri, yeniden boyutlanan kenar çubuğu.
- Ücretsiz yerel kadın sesinde resmi F3 / sakin F1 profili.

# v0.5.0

- Sohbet menüsü: arşivle/geri aç, silme onayı ve güvenlik yedeği.
- Tek ortak ajan açma oku, renkli kartlar, gri çekirdek bekleme modu ve kapanış sesi.
- Proje dosya ağacı oku, editör sekmesini kapatma, ⌘B yan çubuk.
- Kadın Supertonic 3 F1 doğal TR/EN ses; soğuk kısa TR üretimi yaklaşık 2,3 sn.
- İlk sesli gönderimde sohbet görünümü; konuşma akışı ve yazılı yanıtlar birlikte.
- Ajan renk/etkinlik/ortak yönlendirme ayarları, kaldırma ve gerçek bağlayıcı seçimi.
- İsteğe bağlı OpenRouter free-only adaptörü ve macOS Keychain anahtarı; anahtarsız canlı servis denemesi yapılmadı.
- 43 otomatik test.

# 0.4.0 · Mark IV

- Sohbet merkezli tam pencere; kompakt açılan ajanlar, üst çekirdek ve isteğe bağlı çekmeceler.
- Ayrı konuşmalar ve sohbet kapsamlı model bağlamı; eski geçmiş korunur.
- Resmi Antigravity bağlantısıyla Gemini Flash ve Claude Sonnet.
- Resmi Codex ve Antigravity kullanım pencereleri; otomatik AI kredi geçişi kapalı.
- Farklı sağlayıcılarla paralel sohbet; sohbet bazlı durdurma.
- Tek sorumlu görevler, ayrı görev sohbetleri ve kullanıcı onaylı çıktı inceleme.
- Kadın sistem sesleri; ücretsiz yerel doğal ses denemeleri ve ses örnekleri.
- Reddetme, yinelenen komut kartı, geç gelen mesajın yanlış sohbete düşmesi ve çift sunucu sorunları düzeltildi.
- 39 otomatik test; native Mac uygulaması ve dağıtım arşivi.
