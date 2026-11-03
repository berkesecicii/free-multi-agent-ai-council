import AppKit
import WebKit
import AVFoundation
import Speech
import ScreenCaptureKit
import CryptoKit
import Security
import ApplicationServices

let nativeEnglish: [String:String] = {
    guard let url=Bundle.main.url(forResource:"ui-en",withExtension:"json"),let data=try? Data(contentsOf:url),let value=try? JSONSerialization.jsonObject(with:data) as? [String:String] else{return [:]}
    return value
}()
func J(_ text:String)->String {
    guard UserDefaults.standard.string(forKey:"jarvisLanguage")=="en" else{return text}
    if let value=nativeEnglish[text] {return value}
    var value=text
    for (a,b) in [("Dosya açılamadı: ","Could not open file: "),("Kaydedilemedi: ","Could not save: "),("Başlatma başarısız: ","Could not start: "),("Mikrofon başlatılamadı: ","Could not start microphone: ")] {value=value.replacingOccurrences(of:a,with:b)}
    value=value.replacingOccurrences(of:"Eski: ",with:"Old: ").replacingOccurrences(of:"Yeni: ",with:"New: ").replacingOccurrences(of:" bayt",with:" bytes").replacingOccurrences(of:"Editördeki içerik bu dosyanın üzerine yazılacak. Önceki sürüm JARVIS yedek klasörüne kaydedilecek. Komut çalıştırılmaz.",with:"The editor content will replace this file. The previous version will be backed up. No command will run.")
    return value
}

final class JarvisApp: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate, AVSpeechSynthesizerDelegate, AVAudioPlayerDelegate, NSWindowDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var backend: Process?
    var port = 0
    let speaker = AVSpeechSynthesizer()
    var currentUtterance: AVSpeechUtterance?
    var voiceProcess: Process?
    var voicePlayer: AVAudioPlayer?
    var voiceFile: URL?
    var voiceGeneration=UUID()
    let engine = AVAudioEngine()
    var recognition: SFSpeechRecognitionTask?
    var request: SFSpeechAudioBufferRecognitionRequest?
    var silenceTimer: Timer?
    var listenTimer: Timer?
    var listening = false
    var listenWanted = false
    var tapInstalled = false
    var transcript = ""
    var project: URL?
    var screenTimer: Timer?
    var hostTimer: Timer?
    var hostWindow: SCWindow?
    var hostBusy = false
    var uiLanguage: String {UserDefaults.standard.string(forKey:"jarvisLanguage") ?? "tr"}
    func L(_ tr:String,_ en:String)->String {uiLanguage == "en" ? en : tr}
    var captureBusy = false
    var captureEnabled = false
    var cloudSpeechAllowed = false
    var didGreet = false
    var generation = UUID()
    let exclusions: Set<String> = [".git", "node_modules", ".venv", "venv", "__pycache__", ".build", "build", "dist", ".DS_Store"]

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        configureMenus()
        let controller=WKUserContentController()
        controller.add(self,name:"native")
        let config=WKWebViewConfiguration();config.userContentController=controller
        web=WKWebView(frame:.zero,configuration:config);web.navigationDelegate=self
        web.setValue(false,forKey:"drawsBackground")
        window=NSWindow(contentRect:NSRect(x:0,y:0,width:1400,height:940),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        window.title=L(J("JARVIS — Berke’nin Çalışma Alanı"),"JARVIS — Berke’s Workspace");window.minSize=NSSize(width:1000,height:700);window.center();window.contentView=web;window.delegate=self
        window.backgroundColor=NSColor(calibratedRed:0.043,green:0.063,blue:0.082,alpha:1)
        window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
        speaker.delegate=self
        startBackend()
    }
    func configureMenus() {
        let menu = NSMenu()
        let appItem = NSMenuItem();menu.addItem(appItem)
        let sub = NSMenu();sub.addItem(withTitle: L(J("JARVIS Hakkında"),"About JARVIS"), action: #selector(about), keyEquivalent: "")
        sub.addItem(.separator());sub.addItem(withTitle: L(J("JARVIS’ten Çık"),"Quit JARVIS"), action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q");appItem.submenu = sub
        let editItem = NSMenuItem();menu.addItem(editItem)
        let edit = NSMenu(title:L(J("Düzenle"),"Edit"))
        for (title, action, key) in [("Geri Al", "undo:", "z"), (J("Kes"), "cut:", "x"), (J("Kopyala"), "copy:", "c"), (J("Yapıştır"), "paste:", "v"), (J("Tümünü Seç"), "selectAll:", "a")] { edit.addItem(withTitle:menuTitle(title),action:Selector(action),keyEquivalent:key) }
        editItem.submenu=edit;NSApp.mainMenu=menu
    }
    func menuTitle(_ text:String)->String {
        if uiLanguage != "en" {return text}
        return ["Geri Al":"Undo",J("Kes"):"Cut",J("Kopyala"):"Copy",J("Yapıştır"):"Paste",J("Tümünü Seç"):"Select All"][text] ?? text
    }
    func isAssistantVoice(_ voice: AVSpeechSynthesisVoice) -> Bool {
        let names=["Yelda","Samantha","Karen","Moira","Serena","Siri"]
        return voice.gender == .female && names.contains(where:{voice.name.contains($0)})
    }
    func emitVoices() {
        let voices=AVSpeechSynthesisVoice.speechVoices().filter{isAssistantVoice($0) && ($0.language.hasPrefix("tr") || $0.language.hasPrefix("en"))}.map{["id":$0.identifier,"name":$0.name,"language":$0.language]}
        let saved=UserDefaults.standard.string(forKey:"voice."+uiLanguage) ?? ""
        let selected=voices.contains(where:{$0["id"]==saved}) ? saved : ""
        emit("voices",["voices":voices,"selected":selected])
    }
    @objc func about() { let alert=NSAlert();alert.messageText="JARVIS / MARK VI · 0.7.0";alert.informativeText=L("Berke için yerel Mac çalışma alanı. JARVIS sohbeti Gemini Flash ile, kod işleri seçilen geliştirici modeliyle çalışır. Codex ve Claude gündelik sohbet için otomatik çağrılmaz. Yerel sohbet ve yalnızca kadın sesleri seçilebilir. Aktif bilgisayar görevleri ChatGPT uygulamasına devredilebilir.","A local Mac workspace for Berke. JARVIS chat uses Gemini Flash; development uses the selected coding model. Everyday chat does not automatically call Codex or Claude. Local chat and female voices are available. Computer tasks can be handed off to the official ChatGPT app.");alert.runModal() }
    func alert(_ text: String) { let a=NSAlert();a.messageText="JARVIS";a.informativeText=text;a.runModal() }
    func startBackend(attempt:Int=0) {
        guard let resources=Bundle.main.resourceURL else {return}
        let data=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("BerkeJARVIS",isDirectory:true)
        do { try FileManager.default.createDirectory(at:data,withIntermediateDirectories:true)
            let runtimeFile=resources.appendingPathComponent("PythonRuntime.txt")
            let python=(try String(contentsOf:runtimeFile,encoding:.utf8)).trimmingCharacters(in:.whitespacesAndNewlines)
            guard FileManager.default.isExecutableFile(atPath:python) else { throw NSError(domain:J("Python 3 bulunamadı. README kurulum bölümüne bak."),code:1) }
            let process=Process();process.executableURL=URL(fileURLWithPath:python)
            process.arguments=[resources.appendingPathComponent("server/app.py").path,"--port","0","--data-dir",data.path,"--connect-codex"]
            var env=ProcessInfo.processInfo.environment
            for key in Array(env.keys) where key.contains("API_KEY") || key.hasPrefix("GOOGLE_") || key.hasPrefix("ANTHROPIC_") {env.removeValue(forKey:key)}
            env["PYTHONDONTWRITEBYTECODE"]="1";process.environment=env
            let pipe=Pipe();process.standardOutput=pipe;process.standardError=FileHandle.standardError
            backend=process;try process.run()
            DispatchQueue.global().async { [weak self] in
                let bytes=pipe.fileHandleForReading.availableData
                let line=String(data:bytes,encoding:.utf8) ?? ""
                guard let start=line.range(of:"http://127.0.0.1:") else {
                    DispatchQueue.main.asyncAfter(deadline:.now()+0.8){if attempt<6 {self?.startBackend(attempt:attempt+1)}else{self?.alert(J("Yerel koordinatör başlatılamadı."))}};return
                }
                let number=line[start.upperBound...].prefix(while:{$0.isNumber})
                guard let port=Int(number) else {return}
                DispatchQueue.main.async { self?.port=port;self?.web.load(URLRequest(url:URL(string:"http://127.0.0.1:\(port)")!)) }
            }
        } catch { alert(J("Başlatma başarısız: \(error.localizedDescription)")) }
    }
    func emit(_ type:String,_ data:[String:Any]=[:]) {
        guard let bytes=try? JSONSerialization.data(withJSONObject:["type":type,"data":data]),let json=String(data:bytes,encoding:.utf8) else{return}
        web.evaluateJavaScript("window.dispatchEvent(new CustomEvent('jarvis-native',{detail:\(json)}))",completionHandler:nil)
    }
    func userContentController(_ userContentController:WKUserContentController,didReceive message:WKScriptMessage) {
        guard message.frameInfo.isMainFrame,let url=message.frameInfo.request.url,url.host=="127.0.0.1",url.port==port,let body=message.body as? [String:Any],let action=body["action"] as? String else{return}
        switch action {
        case "preferences":
            if let language=body["language"] as? String,["tr","en"].contains(language) {UserDefaults.standard.set(language,forKey:"jarvisLanguage");configureMenus();window.title=L(J("JARVIS — Berke’nin Çalışma Alanı"),"JARVIS — Berke’s Workspace")}
            if let locale=body["speechLanguage"] as? String,["auto","tr-TR","en-GB"].contains(locale) {UserDefaults.standard.set(locale,forKey:"speechLanguage")}
            if let voice=body["voice"] as? String {if voice.isEmpty || AVSpeechSynthesisVoice(identifier:voice) != nil {UserDefaults.standard.set(voice,forKey:"voice."+uiLanguage)}}

            if let style=body["voiceStyle"] as? String,["calm","formal"].contains(style) {UserDefaults.standard.set(style,forKey:"voiceStyle")}
            if let engine=body["voiceEngine"] as? String,["natural","system"].contains(engine) {UserDefaults.standard.set(engine,forKey:"voiceEngine")}
            emitVoices()
        case "save-openrouter-key":
            if let value=body["key"] as? String,value.count<500,value.hasPrefix("sk-or-") {
                let query:[String:Any]=[kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:"BerkeJARVIS.OpenRouter",kSecAttrAccount as String:"api-key"]
                let status=SecItemUpdate(query as CFDictionary,[kSecValueData as String:Data(value.utf8)] as CFDictionary)
                var result=status
                if status == errSecItemNotFound {var entry=query;entry[kSecValueData as String]=Data(value.utf8);result=SecItemAdd(entry as CFDictionary,nil)}
                emit("key-saved",["ok":result == errSecSuccess])
            } else {emit("key-saved",["ok":false])}
        case "delete-openrouter-key":
            let status=SecItemDelete([kSecClass as String:kSecClassGenericPassword,kSecAttrService as String:"BerkeJARVIS.OpenRouter",kSecAttrAccount as String:"api-key"] as CFDictionary)
            emit("key-saved",["ok":status == errSecSuccess || status == errSecItemNotFound])
        case "copy-text":
            if let text=body["text"] as? String,text.count<=60000 {NSPasteboard.general.clearContents();NSPasteboard.general.setString(text,forType:.string)}
        case "desktop-status":emit("desktop-status",["screen":CGPreflightScreenCaptureAccess(),"accessibility":AXIsProcessTrusted()])
        case "desktop-permissions":
            _=CGRequestScreenCaptureAccess()
            _=AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String:true] as CFDictionary)
            emit("desktop-status",["screen":CGPreflightScreenCaptureAccess(),"accessibility":AXIsProcessTrusted()])
        case "desktop-action":performDesktopAction(body)
        case "claude-login":
            let executable=FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/BerkeJARVIS/cli/claude")
            guard FileManager.default.isExecutableFile(atPath:executable.path) else {emit("host-error",["message":L("Claude Code kurulu değil.","Claude Code is not installed.")]);return}
            let script=executable.deletingLastPathComponent().appendingPathComponent("Claude-Login.command")
            let quoted="'"+executable.path.replacingOccurrences(of:"'",with:"'\\''")+"'"
            do {try ("#!/bin/zsh\n"+quoted+" auth login\n").write(to:script,atomically:true,encoding:.utf8);try FileManager.default.setAttributes([.posixPermissions:0o700],ofItemAtPath:script.path);NSWorkspace.shared.open(script)} catch {emit("host-error",["message":error.localizedDescription])}
        case "handoff-chatgpt", "handoff-claude":
            if let text=body["text"] as? String,text.count<40000 {
                NSPasteboard.general.clearContents();NSPasteboard.general.setString(text,forType:.string)
                let destination=action == "handoff-claude" ? "/Applications/Claude.app" : "/Applications/ChatGPT.app"
                NSWorkspace.shared.openApplication(at:URL(fileURLWithPath:destination),configuration:NSWorkspace.OpenConfiguration()){[weak self] _,error in DispatchQueue.main.async {if error == nil {self?.emit("handoff-ready",["app":action == "handoff-claude" ? "Claude" : "ChatGPT"])}else{self?.emit("host-error",["message":error!.localizedDescription])}}}
            }
        case "watch-chatgpt": watchChatGPT()
        case "stop-host-watch": stopHostWatch()
        case "open-task-site":
            if let raw=body["url"] as? String,let url=URL(string:raw),["https","http"].contains(url.scheme ?? "") {NSWorkspace.shared.open(url)}
        case "speak": if let text=body["text"] as? String {speak(String(text.prefix(4000)))}
        case "stop-speech": stopSpeech()
        case "listen": listenWanted=true;authorizeSpeech()
        case "stop-listening": listenWanted=false;stopListening(deliver:false)
        case "restore-project":
            if let path=body["path"] as? String,(UserDefaults.standard.stringArray(forKey:"approvedProjectPaths") ?? []).contains(path),FileManager.default.fileExists(atPath:path) {project=URL(fileURLWithPath:path);listProject()}
        case "reveal-project": if let root=project {NSWorkspace.shared.activateFileViewerSelecting([root])}
        case "close-project": project=nil;emit("project-closed")
        case "choose-project": chooseProject()
        case "read-file": if let path=body["path"] as? String {readFile(path)}
        case "save-file": if let path=body["path"] as? String,let text=body["text"] as? String,let hash=body["hash"] as? String {saveFile(path,text,hash)}
        case "start-screen": startScreen()
        case "stop-screen": stopScreen()
        case "approve-live-screen":
            let a=NSAlert();a.messageText=L(J("Ekranla sesli konuşmayı başlat"),"Start screen conversation");a.informativeText=J("Bu oturumda her yeni yazılı veya sesli mesajında ana ekranının en güncel karesi, mevcut ChatGPT aboneliğini kullanan resmi Codex’e gönderilecek. Görüntü hassas uygulamaları içerebilir. Her önizleme karesi gönderilmez; yalnızca mesaj gönderirken bir kare kullanılır. Ekran paylaşımını veya konuşmayı bitirerek durdurabilirsin. Model fare veya klavye kullanamaz.");a.addButton(withTitle:L(J("Bu oturumda ekranla konuş"),"Share the screen for this session"));a.addButton(withTitle:L(J("Vazgeç"),"Cancel"))
            if a.runModal() == .alertFirstButtonReturn {
                emit("live-screen-approved")
                if !captureEnabled {captureEnabled=true;captureScreen();screenTimer=Timer.scheduledTimer(withTimeInterval:3,repeats:true){[weak self]_ in self?.captureScreen()}}
            }
        case "approve-screen-attachment":
            let a=NSAlert();a.messageText=L("Bu ekran karesini sohbete ekle","Attach this screen frame");a.informativeText=J("Seçtiğin tek kare, sonraki mesajını gönderdiğinde mevcut ChatGPT aboneliğini kullanan resmi Codex’e aktarılacak. Görseli gönderimden önce taslaktan kaldırabilirsin. Yerel önizleme kendiliğinden paylaşılmaz.");a.addButton(withTitle:L("Bu kareyi mesaja ekle","Attach this frame"));a.addButton(withTitle:L(J("Vazgeç"),"Cancel"))
            if a.runModal() == .alertFirstButtonReturn {emit("screen-attachment-approved")}
        case "open-antigravity":
            let app=URL(fileURLWithPath:"/Applications/Antigravity.app")
            if FileManager.default.fileExists(atPath:app.path) {
                if let project=project {NSWorkspace.shared.open([project],withApplicationAt:app,configuration:NSWorkspace.OpenConfiguration(),completionHandler:nil)} else {NSWorkspace.shared.openApplication(at:app,configuration:NSWorkspace.OpenConfiguration(),completionHandler:nil)}
            } else {emit("file-error",["message":J("Antigravity uygulaması bulunamadı.")])}
        case "open-memory": NSWorkspace.shared.open(FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("BerkeJARVIS"))
        case "ready": if !didGreet {didGreet=true;speak(L(J("Merhaba Berke. Buradayım. Bugün ne üzerinde çalışalım?"),"Hello, Berke. I am here. What shall we work on today?"));emitVoices()}
        default: break
        }
    }
    func webView(_ webView:WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void) {
        if let url=navigationAction.request.url,url.host=="127.0.0.1",url.port==port {decisionHandler(.allow)} else {decisionHandler(.cancel)}
    }
    func stopSpeech(notify:Bool=true) {
        voiceGeneration=UUID();voiceProcess?.terminate();voiceProcess=nil;voicePlayer?.stop();voicePlayer=nil
        if let file=voiceFile {try? FileManager.default.removeItem(at:file);voiceFile=nil}
        currentUtterance=nil;speaker.stopSpeaking(at:.immediate)
        if notify {emit("speaking",["active":false])}
    }
    func speak(_ text:String) {
        listenWanted=false;stopListening(deliver:false);stopSpeech(notify:false)
        let lower=text.lowercased()
        let turkishWords=["merhaba"," için "," bir "," değil"," nasıl","ş","ğ","ı","ü","ö","ç"]
        let englishWords=["hello"," the "," you "," this ","please","what ","i am","yes,","let us"]
        let locale=turkishWords.contains(where:{lower.contains($0)}) ? "tr-TR" : englishWords.contains(where:{lower.contains($0)}) ? "en-US" : (uiLanguage == "en" ? "en-US" : "tr-TR")
        if UserDefaults.standard.string(forKey:"voiceEngine") != "system",speakNatural(text,locale) {return}
        speakSystem(text,locale)
    }
    func speakNatural(_ text:String,_ locale:String)->Bool {
        guard let resources=Bundle.main.resourceURL else{return false}
        let runtime=resources.appendingPathComponent("voice-runtime"),python=runtime.appendingPathComponent("python/bin/python3")
        guard FileManager.default.isExecutableFile(atPath:python.path) else{return false}
        let token=UUID();voiceGeneration=token
        let output=FileManager.default.temporaryDirectory.appendingPathComponent("jarvis-voice-"+token.uuidString+".wav")
        voiceFile=output
        let process=Process();process.executableURL=python;process.arguments=["-B",runtime.appendingPathComponent("voice_worker.py").path];process.qualityOfService = .userInitiated
        var env=ProcessInfo.processInfo.environment;env["PYTHONPATH"]=runtime.appendingPathComponent("packages").path;env["PYTHONDONTWRITEBYTECODE"]="1";process.environment=env
        let input=Pipe();process.standardInput=input;process.standardOutput=FileHandle.nullDevice;process.standardError=FileHandle.nullDevice
        process.terminationHandler={[weak self] p in DispatchQueue.main.async {
            guard let self=self,self.voiceGeneration==token else {try? FileManager.default.removeItem(at:output);return}
            self.voiceProcess=nil
            if p.terminationStatus==0,let player=try? AVAudioPlayer(contentsOf:output) {self.voicePlayer=player;player.delegate=self;player.prepareToPlay();player.play()}
            else {try? FileManager.default.removeItem(at:output);self.voiceFile=nil;self.emit("voice-fallback",["message":self.L("Doğal ses açılamadı; macOS kadın sesi kullanılıyor.","Natural voice unavailable; using the macOS female voice.")]);self.speakSystem(text,locale)}
        }}
        do {try process.run();voiceProcess=process;emit("speaking",["active":true]);let data=try JSONSerialization.data(withJSONObject:["text":text,"lang":locale.hasPrefix("tr") ? "tr":"en","style":UserDefaults.standard.string(forKey:"voiceStyle") ?? "formal","output":output.path]);input.fileHandleForWriting.write(data);try? input.fileHandleForWriting.close()
            DispatchQueue.main.asyncAfter(deadline:.now()+10){[weak self] in if self?.voiceGeneration==token,self?.voiceProcess?.isRunning==true {self?.voiceProcess?.terminate()}}
            return true
        } catch {voiceProcess=nil;return false}
    }
    func audioPlayerDidFinishPlaying(_ player:AVAudioPlayer,successfully flag:Bool) {if player === voicePlayer {voicePlayer=nil;if let file=voiceFile {try? FileManager.default.removeItem(at:file);voiceFile=nil};emit("speaking",["active":false])}}

    func speakSystem(_ text:String,_ locale:String) {
        let key=locale.hasPrefix("tr") ? "tr" : "en"
        let preferred=UserDefaults.standard.string(forKey:"voice."+key) ?? ""
        let speech=AVSpeechUtterance(string:text)
        if !preferred.isEmpty, let chosen=AVSpeechSynthesisVoice(identifier:preferred), isAssistantVoice(chosen),chosen.language.hasPrefix(key) {speech.voice=chosen}
        if speech.voice == nil {speech.voice=AVSpeechSynthesisVoice.speechVoices().filter{isAssistantVoice($0) && $0.language.hasPrefix(key)}.sorted{a,b in
            if a.quality != b.quality {return a.quality.rawValue > b.quality.rawValue}
            let preferredName=key == "tr" ? "Yelda" : "Samantha"
            return a.name.contains(preferredName) && !b.name.contains(preferredName)
        }.first}
        guard speech.voice != nil else {emit("voice-error",["message":L("Bu dilde kadın asistan sesi yüklü değil.","No female assistant voice is installed for this language.")]);return}
        speech.rate=0.44;speech.pitchMultiplier=1.0;speech.preUtteranceDelay=0.08;speech.postUtteranceDelay=0.12
        currentUtterance=speech;speaker.speak(speech);emit("speaking",["active":true])
    }
    func speechSynthesizer(_ synthesizer:AVSpeechSynthesizer,didFinish utterance:AVSpeechUtterance) {if utterance === currentUtterance {currentUtterance=nil;emit("speaking",["active":false])}}
    func speechSynthesizer(_ synthesizer:AVSpeechSynthesizer,didCancel utterance:AVSpeechUtterance) {if utterance === currentUtterance {currentUtterance=nil;emit("speaking",["active":false])}}
    func authorizeSpeech() {
        stopSpeech(notify:false)
        SFSpeechRecognizer.requestAuthorization { [weak self] status in
            DispatchQueue.main.async {
                guard let self=self,self.listenWanted else{return}
                guard status == .authorized else {self.emit("voice-error",["message":J("Konuşma tanıma izni verilmedi. Sistem Ayarları → Gizlilik ve Güvenlik → Konuşma Tanıma bölümünü kontrol et.")]);return}
                AVCaptureDevice.requestAccess(for:.audio) { allowed in DispatchQueue.main.async {
                    if allowed {if self.listenWanted {self.beginListening()}} else {self.emit("voice-error",["message":J("Mikrofon izni gerekli. Sistem Ayarları → Gizlilik ve Güvenlik → Mikrofon.")])}
                }}
            }
        }
    }
    func beginListening() {
        guard !listening,listenWanted else {return}
        let selected=UserDefaults.standard.string(forKey:"speechLanguage") ?? "auto"
        let locale=selected == "auto" ? (uiLanguage == "en" ? "en-GB" : "tr-TR") : selected
        guard let recognizer=SFSpeechRecognizer(locale:Locale(identifier:locale)),recognizer.isAvailable else {emit("voice-error",["message":J("Türkçe konuşma tanıma şu anda kullanılamıyor. Yazılı sohbet veya macOS Dikte kullanabilirsin.")]);return}
        if !recognizer.supportsOnDeviceRecognition && !cloudSpeechAllowed {
            let a=NSAlert();a.messageText=J("Türkçe ses tanıma için Apple hizmeti gerekiyor");a.informativeText=J("Bu Mac’te Türkçe cihaz içi tanıma bulunamadı. Devam edersen mikrofon sesi Apple’ın konuşma tanıma hizmetine gönderilebilir. AI sağlayıcılarına gönderilmez. İstersen yazılı sohbeti kullanabilirsin.");a.addButton(withTitle:L("Bu oturumda Apple ile devam et","Use Apple recognition for this session"));a.addButton(withTitle:L(J("Vazgeç"),"Cancel"))
            guard a.runModal() == .alertFirstButtonReturn else {emit("voice-error",["message":J("Ses tanıma açılmadı. Yazılı sohbet hazır.")]);return};cloudSpeechAllowed=true
        }
        do {
            stopListening(deliver:false);transcript="";let gen=UUID();generation=gen
            let request=SFSpeechAudioBufferRecognitionRequest();request.shouldReportPartialResults=true
            request.requiresOnDeviceRecognition=recognizer.supportsOnDeviceRecognition
            self.request=request
            let input=engine.inputNode;let format=input.outputFormat(forBus:0)
            guard format.sampleRate > 0 && format.channelCount > 0 else {throw NSError(domain:J("Geçerli mikrofon bulunamadı"),code:1)}
            input.installTap(onBus:0,bufferSize:1024,format:format){buffer,_ in request.append(buffer)};tapInstalled=true
            engine.prepare();try engine.start();listening=true
            emit("listening",["active":true,"local":recognizer.supportsOnDeviceRecognition])
            recognition=recognizer.recognitionTask(with:request){[weak self] result,error in
                DispatchQueue.main.async {
                    guard let self=self,self.generation==gen,self.listening else{return}
                    if let result=result {
                        let text=result.bestTranscription.formattedString
                        if text != self.transcript {
                            self.transcript=text;self.emit("transcript",["text":text,"final":false])
                            self.silenceTimer?.invalidate();self.silenceTimer=Timer.scheduledTimer(withTimeInterval:1.6,repeats:false){[weak self]_ in self?.stopListening(deliver:true)}
                        }
                        if result.isFinal {self.stopListening(deliver:true)}
                    } else if let error=error {self.stopListening(deliver:false);self.emit("voice-error",["message":error.localizedDescription])}
                }
            }
            listenTimer=Timer.scheduledTimer(withTimeInterval:45,repeats:false){[weak self]_ in self?.stopListening(deliver:true)}
        } catch {stopListening(deliver:false);emit("voice-error",["message":J("Mikrofon başlatılamadı: \(error.localizedDescription)")])}
    }
    func stopListening(deliver:Bool) {
        let wasListening=listening;listening=false;generation=UUID();silenceTimer?.invalidate();listenTimer?.invalidate()
        if engine.isRunning {engine.stop()};if tapInstalled {engine.inputNode.removeTap(onBus:0);tapInstalled=false}
        request?.endAudio();recognition?.cancel();recognition=nil;request=nil
        if wasListening {emit("listening",["active":false]);if deliver && !transcript.isEmpty {emit("transcript",["text":transcript,"final":true])}else if deliver {emit("voice-error",["message":J("Ses algılanmadı. Mikrofonu kontrol edip tekrar dene.")])}}
    }
    func chooseProject() {
        let panel=NSOpenPanel();panel.canChooseDirectories=true;panel.canChooseFiles=false;panel.allowsMultipleSelection=false;panel.prompt=L(J("Projeyi aç"),"Open project");panel.message=L(J("JARVIS yalnızca seçtiğin klasördeki metin dosyalarını gösterecek. Kaydetme ayrıca onay ister."),"JARVIS shows text files only from your selected folder. Saving requires separate approval.")
        if panel.runModal() == .OK,let url=panel.url {project=url.resolvingSymlinksInPath();if let path=project?.path {var paths=UserDefaults.standard.stringArray(forKey:"approvedProjectPaths") ?? [];if !paths.contains(path){paths.append(path);UserDefaults.standard.set(paths,forKey:"approvedProjectPaths")}};listProject()}
    }
    func safeFile(_ relative:String)->URL? {
        guard let root=project,!relative.hasPrefix("/"),!relative.split(separator:"/").contains("..") else{return nil}
        let candidate=root.appendingPathComponent(relative).resolvingSymlinksInPath().standardizedFileURL
        guard candidate.path.hasPrefix(root.path+"/") else{return nil}
        return candidate
    }
    func listProject() {
        guard let root=project else{return};var files=[String]()
        if let enumerator=FileManager.default.enumerator(at:root,includingPropertiesForKeys:[.isRegularFileKey,.isSymbolicLinkKey],options:[.skipsHiddenFiles]) {
            for case let url as URL in enumerator {
                if exclusions.contains(url.lastPathComponent) {enumerator.skipDescendants();continue}
                if let values=try? url.resourceValues(forKeys:[.isRegularFileKey,.isSymbolicLinkKey]),values.isRegularFile==true,values.isSymbolicLink != true {files.append(String(url.path.dropFirst(root.path.count+1)))}
                if files.count>=1500 {break}
            }
        }
        emit("project",["name":root.lastPathComponent,"path":root.path,"files":files.sorted()])
    }
    func hash(_ data:Data)->String {SHA256.hash(data:data).map{String(format:"%02x",$0)}.joined()}
    func readFile(_ path:String) {
        guard let url=safeFile(path) else{emit("file-error",["message":J("Dosya seçili projenin dışında.")]);return}
        do {let attrs=try FileManager.default.attributesOfItem(atPath:url.path);guard (attrs[.size] as? Int ?? 0)<=500000 else{throw NSError(domain:J("Dosya 500 KB sınırını aşıyor"),code:1)}
            let data=try Data(contentsOf:url);guard let text=String(data:data,encoding:.utf8),!text.contains("\0") else{throw NSError(domain:J("Bu dosya UTF-8 metin değil"),code:1)}
            emit("file",["path":path,"text":text,"hash":hash(data)])
        }catch{emit("file-error",["message":J("Dosya açılamadı: \(error.localizedDescription)")])}
    }
    func saveFile(_ path:String,_ text:String,_ originalHash:String) {
        guard let url=safeFile(path),let before=try? Data(contentsOf:url),hash(before)==originalHash else{emit("file-error",["message":J("Dosya dışarıda değişti veya erişim geçersiz. Yeniden açıp karşılaştır.")]);return}
        guard text.utf8.count<=500000 else{emit("file-error",["message":J("500 KB sınırı aşıldı.")]);return}
        let a=NSAlert();a.messageText=L(J("Dosya değişikliğini onayla"),"Approve file change");a.informativeText=J("\(url.path)\n\nEski: \(before.count) bayt · Yeni: \(text.utf8.count) bayt\nEditördeki içerik bu dosyanın üzerine yazılacak. Önceki sürüm JARVIS yedek klasörüne kaydedilecek. Komut çalıştırılmaz.");a.addButton(withTitle:L("Yedekle ve kaydet","Back up and save"));a.addButton(withTitle:L(J("Vazgeç"),"Cancel"))
        guard a.runModal() == .alertFirstButtonReturn else{return}
        do {
            // Revalidate after the review dialog to detect concurrent external edits.
            guard let target=safeFile(path),target==url,let current=try? Data(contentsOf:target),hash(current)==originalHash else{throw NSError(domain:J("Dosya onay sırasında değişti"),code:1)}
            let backups=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("BerkeJARVIS/backups",isDirectory:true)
            try FileManager.default.createDirectory(at:backups,withIntermediateDirectories:true)
            try before.write(to:backups.appendingPathComponent(UUID().uuidString+"-"+url.lastPathComponent))
            try text.write(to:target,atomically:true,encoding:.utf8);readFile(path);emit("file-saved",["message":J("Yedek alındı ve dosya kaydedildi.")])
        }catch{emit("file-error",["message":"Kaydedilemedi: \(error.localizedDescription)"])}
    }
    func desktopResult(_ id:String,_ value:[String:Any]) {emit("desktop-result",["id":id,"result":value])}
    func performDesktopAction(_ body:[String:Any]) {
        guard let id=body["id"] as? String,let tool=body["tool"] as? String,let args=body["arguments"] as? [String:Any],let expires=body["expires"] as? Double,Date().timeIntervalSince1970<expires else{return}
        if tool=="desktop_observe" {captureDesktopForAgent(id);return}
        guard AXIsProcessTrusted() else {desktopResult(id,["error":"macOS Erişilebilirlik izni gerekli. Kontrol gerçekleştirilmedi."]);return}
        let blocked=["com.apple.Terminal","com.googlecode.iterm2","com.apple.systempreferences","com.apple.SecurityAgent","com.apple.loginwindow","com.apple.keychainaccess","com.microsoft.VSCode","com.google.antigravity"]
        let front=NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? ""
        guard !blocked.contains(front) else {desktopResult(id,["error":"Bu sistem/terminal penceresinde otomatik eylem kapalı."]);return}
        if tool=="desktop_open_url" {
            guard let raw=args["url"] as? String,let url=URL(string:raw),["http","https"].contains(url.scheme ?? ""),url.user==nil,url.password==nil else {desktopResult(id,["error":"Web adresi izinli değil."]);return}
            let ok=NSWorkspace.shared.open(url);desktopResult(id,["acted":ok]);return
        }
        guard let screen=NSScreen.screens.first else {desktopResult(id,["error":"Ekran bulunamadı."]);return}
        if tool=="desktop_click" {
            guard let x=args["x"] as? Double,let y=args["y"] as? Double,x.isFinite,y.isFinite,x>=0,y>=0,x<Double(screen.frame.width),y<Double(screen.frame.height) else {desktopResult(id,["error":"Koordinat ekran sınırının dışında."]);return}
            let point=CGPoint(x:x,y:y)
            CGEvent(mouseEventSource:nil,mouseType:.leftMouseDown,mouseCursorPosition:point,mouseButton:.left)?.post(tap:.cghidEventTap)
            CGEvent(mouseEventSource:nil,mouseType:.leftMouseUp,mouseCursorPosition:point,mouseButton:.left)?.post(tap:.cghidEventTap)
        } else if tool=="desktop_type" {
            guard let text=args["text"] as? String,text.count<=2000 else {desktopResult(id,["error":"Metin sınırı aşıldı."]);return}
            var focused:CFTypeRef?
            if AXUIElementCopyAttributeValue(AXUIElementCreateSystemWide(),kAXFocusedUIElementAttribute as CFString,&focused) == .success,let focused=focused,CFGetTypeID(focused)==AXUIElementGetTypeID() {
                var subrole:CFTypeRef?;AXUIElementCopyAttributeValue(focused as! AXUIElement,kAXSubroleAttribute as CFString,&subrole)
                if (subrole as? String)=="AXSecureTextField" {desktopResult(id,["error":"Parola/güvenli alana yazma engellendi."]);return}
            }
            let chars=Array(text.utf16)
            for down in [true,false] {if let event=CGEvent(keyboardEventSource:nil,virtualKey:0,keyDown:down){chars.withUnsafeBufferPointer {event.keyboardSetUnicodeString(stringLength:chars.count,unicodeString:$0.baseAddress!)};event.post(tap:.cghidEventTap)}}
        } else if tool=="desktop_key" {
            guard let key=args["key"] as? String else{return}
            let keys:[String:CGKeyCode]=["enter":36,"escape":53,"tab":48,"backspace":51,"left":123,"right":124,"up":126,"down":125,"cmd+a":0,"cmd+l":37,"cmd+s":1,"cmd+z":6]
            guard let code=keys[key] else {desktopResult(id,["error":"Kısayol izinli değil."]);return}
            for down in [true,false] {let event=CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:down);if key.hasPrefix("cmd+"){event?.flags = .maskCommand};event?.post(tap:.cghidEventTap)}
        } else if tool=="desktop_scroll" {
            guard let steps=args["steps"] as? Int,abs(steps)<=8 else {desktopResult(id,["error":"Kaydırma sınırı aşıldı."]);return}
            CGEvent(scrollWheelEvent2Source:nil,units:.line,wheelCount:1,wheel1:Int32(steps),wheel2:0,wheel3:0)?.post(tap:.cghidEventTap)
        } else {desktopResult(id,["error":"Masaüstü aracı tanınmadı."]);return}
        desktopResult(id,["acted":true,"application":front])
    }
    func captureDesktopForAgent(_ id:String) {
        guard CGPreflightScreenCaptureAccess(),let screen=NSScreen.screens.first else {desktopResult(id,["error":"macOS Ekran Kaydı izni gerekli. Görüntü gönderilmedi."]);return}
        let width=Int(screen.frame.width),height=Int(screen.frame.height)
        SCShareableContent.getExcludingDesktopWindows(false,onScreenWindowsOnly:true){[weak self] content,error in
            guard let self=self,let display=content?.displays.first(where:{$0.displayID==CGMainDisplayID()}) else {DispatchQueue.main.async{self?.desktopResult(id,["error":"Ekran içeriğine erişilemedi."])};return}
            let filter=SCContentFilter(display:display,excludingWindows:[]),config=SCStreamConfiguration();config.width=width;config.height=height;config.showsCursor=true
            SCScreenshotManager.captureImage(contentFilter:filter,configuration:config){image,error in
                DispatchQueue.main.async {
                    guard let image=image,let data=NSBitmapImageRep(cgImage:image).representation(using:.jpeg,properties:[.compressionFactor:0.65]) else {self.desktopResult(id,["error":"Ekran görüntüsü alınamadı."]);return}
                    self.desktopResult(id,["image":"data:image/jpeg;base64,"+data.base64EncodedString(),"width":width,"height":height,"application":NSWorkspace.shared.frontmostApplication?.localizedName ?? "unknown"])
                }
            }
        }
    }
    func startScreen() {
        guard !captureEnabled else{return}
        let a=NSAlert();a.messageText=J("Ekran önizlemesini başlat");a.informativeText=J("Ana ekranın 3 saniyede bir bu uygulamada gösterilir. Görseller diske kaydedilmez, AI sağlayıcılarına gönderilmez. Hassas pencereleri kapatabilirsin. Bu sürüm ekranı modelle yorumlamaz. Durdur düğmesi izlemeyi kapatır.");a.addButton(withTitle:J("Yerel önizlemeyi başlat"));a.addButton(withTitle:L(J("Vazgeç"),"Cancel"))
        guard a.runModal() == .alertFirstButtonReturn else{return}
        captureEnabled=true;captureScreen();screenTimer=Timer.scheduledTimer(withTimeInterval:3,repeats:true){[weak self]_ in self?.captureScreen()}
    }
    func stopScreen() {captureEnabled=false;screenTimer?.invalidate();screenTimer=nil;emit("screen-stopped")}
    func captureScreen() {
        guard !captureBusy,captureEnabled else{return};captureBusy=true
        SCShareableContent.getExcludingDesktopWindows(false,onScreenWindowsOnly:true){[weak self] content,error in
            guard let self=self else{return}
            guard let content=content,let display=content.displays.first(where:{$0.displayID==CGMainDisplayID()}) ?? content.displays.first else{
                DispatchQueue.main.async{self.captureBusy=false;self.stopScreen();self.emit("screen-error",["message":J("Ekran izni gerekli. Sistem Ayarları → Gizlilik ve Güvenlik → Ekran ve Sistem Sesi Kaydı. İzin sonrası uygulamayı yeniden açman gerekebilir.")])};return
            }
            let own=content.windows.filter{$0.owningApplication?.processID==ProcessInfo.processInfo.processIdentifier}
            let filter=SCContentFilter(display:display,excludingWindows:own)
            let config=SCStreamConfiguration();config.width=1280;config.height=max(1,Int(1280.0*Double(display.height)/Double(display.width)));config.showsCursor=true
            SCScreenshotManager.captureImage(contentFilter:filter,configuration:config){image,error in
                DispatchQueue.main.async {
                    self.captureBusy=false;guard self.captureEnabled else{return}
                    guard let image=image else{self.stopScreen();self.emit("screen-error",["message":error?.localizedDescription ?? J("Ekran alınamadı.")]);return}
                    let rep=NSBitmapImageRep(cgImage:image)
                    if let data=rep.representation(using:.jpeg,properties:[.compressionFactor:0.65]) {self.emit("screen",["image":"data:image/jpeg;base64,"+data.base64EncodedString(),"time":DateFormatter.localizedString(from:Date(),dateStyle:.none,timeStyle:.medium)])}
                }
            }
        }
    }
    func watchChatGPT() {
        SCShareableContent.getExcludingDesktopWindows(true,onScreenWindowsOnly:false){[weak self] content,error in
            DispatchQueue.main.async {
                guard let self=self else{return}
                let choices=(content?.windows ?? []).filter {($0.owningApplication?.bundleIdentifier ?? "").contains("openai") && $0.frame.width>300 && $0.frame.height>200}
                guard !choices.isEmpty else {self.emit("host-error",["message":self.L(J("ChatGPT penceresi bulunamadı veya ekran kaydı izni yok. ChatGPT’yi açıp tekrar dene."),"No ChatGPT window found, or screen recording permission is missing. Open ChatGPT and try again.")]);return}
                let popup=NSPopUpButton(frame:NSRect(x:0,y:0,width:440,height:28));choices.forEach{popup.addItem(withTitle:$0.title ?? "ChatGPT")}
                let alert=NSAlert();alert.messageText=self.L("ChatGPT penceresini JARVIS’te izle","Watch a ChatGPT window in JARVIS");alert.informativeText=self.L(J("Seçtiğin pencerenin canlı görüntüsü yalnızca bu Mac’te gösterilir. Modele gönderilmez veya diske kaydedilmez. İşin başlaması için görevini ChatGPT’nin kendi sohbetinde göndermelisin. Burada ChatGPT’nin izinlerini değiştirmeyiz."),"A live view of your selected window is shown only on this Mac. It is not sent to a model or saved. Start the task in ChatGPT’s own conversation. This does not change ChatGPT’s permissions.");alert.accessoryView=popup;alert.addButton(withTitle:self.L("Bu pencereyi izle","Watch this window"));alert.addButton(withTitle:self.L(J("Vazgeç"),"Cancel"))
                guard alert.runModal() == .alertFirstButtonReturn else{return}
                self.stopHostWatch();self.hostWindow=choices[popup.indexOfSelectedItem];self.captureHostWindow();self.hostTimer=Timer.scheduledTimer(withTimeInterval:1.5,repeats:true){[weak self]_ in self?.captureHostWindow()}
            }
        }
    }
    func stopHostWatch() {hostTimer?.invalidate();hostTimer=nil;hostWindow=nil;emit("host-stopped")}
    func captureHostWindow() {
        guard !hostBusy,let target=hostWindow else{return};hostBusy=true
        let filter=SCContentFilter(desktopIndependentWindow:target),config=SCStreamConfiguration()
        config.width=1280;config.height=max(1,Int(1280*target.frame.height/max(1,target.frame.width)));config.showsCursor=true
        SCScreenshotManager.captureImage(contentFilter:filter,configuration:config){[weak self] image,error in
            DispatchQueue.main.async {
                guard let self=self else{return};self.hostBusy=false
                guard self.hostWindow?.windowID==target.windowID else{return}
                guard let image=image else{self.stopHostWatch();self.emit("host-error",["message":error?.localizedDescription ?? self.L(J("Pencere görüntüsü alınamadı."),"Could not capture the window.")]);return}
                if let data=NSBitmapImageRep(cgImage:image).representation(using:.jpeg,properties:[.compressionFactor:0.6]) {self.emit("host-frame",["image":"data:image/jpeg;base64,"+data.base64EncodedString(),"title":target.title ?? "ChatGPT","time":DateFormatter.localizedString(from:Date(),dateStyle:.none,timeStyle:.medium)])}
            }
        }
    }
    func windowWillClose(_ notification:Notification) {NSApp.terminate(nil)}
    func applicationWillTerminate(_ notification:Notification) {stopListening(deliver:false);screenTimer?.invalidate();hostTimer?.invalidate();stopSpeech(notify:false);if backend?.isRunning==true {backend?.terminate()}}
}
let app=NSApplication.shared
let delegate=JarvisApp();app.delegate=delegate;app.run()
