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
