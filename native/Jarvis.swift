import AppKit
import WebKit
import AVFoundation
import Speech
import NaturalLanguage
import ScreenCaptureKit
import CryptoKit
import Security
import ApplicationServices
import UserNotifications
import QuartzCore

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

final class SpeechCandidate {
    let locale:String
    let recognizer:SFSpeechRecognizer
    let request=SFSpeechAudioBufferRecognitionRequest()
    var task:SFSpeechRecognitionTask?
    var text=""
    var confidence:Float=0
    var finished=false
    init(locale:String,recognizer:SFSpeechRecognizer){self.locale=locale;self.recognizer=recognizer}
}

// One soft edge of the glow: a thin gradient window (no full-screen drawing), strongest at the screen edge and easing out to nothing.
func makeGlowStrip(frame:NSRect,from:CGPoint,to:CGPoint,tint:NSColor,peak:CGFloat) -> NSWindow {
    let w=NSWindow(contentRect:frame,styleMask:[.borderless],backing:.buffered,defer:false)
    w.isReleasedWhenClosed=false;w.isOpaque=false;w.backgroundColor = .clear;w.hasShadow=false;w.ignoresMouseEvents=true
    w.level = .screenSaver
    w.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary,.stationary,.ignoresCycle]
    w.setFrame(frame,display:false)
    let view=NSView(frame:NSRect(origin:.zero,size:frame.size));view.wantsLayer=true
    let gradient=CAGradientLayer();gradient.frame=view.bounds
    let stops=(0...12).map{CGFloat($0)/12}
    gradient.colors=stops.map{tint.withAlphaComponent(peak*pow(1-$0,2.4)).cgColor}
    gradient.locations=stops.map{NSNumber(value:Double($0))}
    gradient.startPoint=from;gradient.endPoint=to
    view.layer?.addSublayer(gradient)
    w.contentView=view
    let pulse=CABasicAnimation(keyPath:"opacity")
    pulse.fromValue=0.7;pulse.toValue=1.0;pulse.duration=2.4;pulse.autoreverses=true;pulse.repeatCount = .infinity
    pulse.timingFunction=CAMediaTimingFunction(name:.easeInEaseOut)
    gradient.add(pulse,forKey:"pulse")
    w.alphaValue=0
    w.orderFrontRegardless()
    return w
}

// A short ring that spreads from the pointer tip when the agent clicks.
func pointerRipple(_ layer:CALayer?,tint:NSColor) {
    guard let layer=layer else{return}
    let tip=CGPoint(x:24,y:60)
    let ring=CAShapeLayer();ring.frame=layer.bounds
    let small=CGPath(ellipseIn:CGRect(x:tip.x-3,y:tip.y-3,width:6,height:6),transform:nil)
    let large=CGPath(ellipseIn:CGRect(x:tip.x-20,y:tip.y-20,width:40,height:40),transform:nil)
    ring.path=small;ring.fillColor=nil;ring.strokeColor=tint.cgColor;ring.lineWidth=2;ring.opacity=0
    layer.addSublayer(ring)
    let grow=CABasicAnimation(keyPath:"path");grow.fromValue=small;grow.toValue=large
    let fade=CABasicAnimation(keyPath:"opacity");fade.fromValue=0.9;fade.toValue=0
    let group=CAAnimationGroup();group.animations=[grow,fade];group.duration=0.6;group.timingFunction=CAMediaTimingFunction(name:.easeOut)
    CATransaction.begin()
    CATransaction.setCompletionBlock{ring.removeFromSuperlayer()}
    ring.add(group,forKey:"ripple")
    CATransaction.commit()
}

// The app a background agent works in, its window as last captured, and the scale between picture pixels and screen points.
typealias BackgroundTarget=(pid:pid_t,bundle:String,name:String,windowID:CGWindowID,frame:CGRect,scale:Double)
let backgroundTextRoles=["AXTextArea","AXTextField","AXComboBox","AXSearchField"]

// The agent's own mouse pointer: a coloured arrow with its name that glides to where it is about to click.
final class PointerView: NSView {
    var tint=NSColor.systemTeal
    var name=""
    override func draw(_ dirtyRect:NSRect) {
        guard let ctx=NSGraphicsContext.current?.cgContext else{return}
        let tip=CGPoint(x:24,y:bounds.height-24)
        let path=CGMutablePath()
        path.move(to:tip)
        path.addLine(to:CGPoint(x:tip.x,y:tip.y-18))
        path.addLine(to:CGPoint(x:tip.x+4.6,y:tip.y-14))
        path.addLine(to:CGPoint(x:tip.x+8,y:tip.y-21.5))
        path.addLine(to:CGPoint(x:tip.x+11,y:tip.y-20))
        path.addLine(to:CGPoint(x:tip.x+7.6,y:tip.y-12.8))
        path.addLine(to:CGPoint(x:tip.x+13,y:tip.y-12.8))
        path.closeSubpath()
        ctx.saveGState()
        ctx.setShadow(offset:CGSize(width:0,height:-1.5),blur:4,color:NSColor.black.withAlphaComponent(0.35).cgColor)
        ctx.addPath(path);ctx.setFillColor(tint.cgColor);ctx.fillPath()
        ctx.restoreGState()
        ctx.addPath(path);ctx.setStrokeColor(NSColor.white.cgColor);ctx.setLineWidth(1.4);ctx.setLineJoin(.round);ctx.strokePath()
        let attrs:[NSAttributedString.Key:Any]=[.font:NSFont.systemFont(ofSize:11,weight:.semibold),.foregroundColor:NSColor.white]
        let label=NSAttributedString(string:name,attributes:attrs)
        let size=label.size()
        let chip=NSRect(x:tip.x+15,y:tip.y-36,width:min(170,size.width+16),height:20)
        ctx.addPath(CGPath(roundedRect:chip,cornerWidth:10,cornerHeight:10,transform:nil));ctx.setFillColor(tint.cgColor);ctx.fillPath()
        label.draw(at:NSPoint(x:chip.minX+8,y:chip.minY+(20-size.height)/2))
    }
}

// The agent's own small screen while it works in a window that stays behind Berke's apps: the window as the agent sees it, with the agent's pointer on it.
// It never takes focus, can be dragged away, and is left out of the agent's screenshots.
final class AgentScreen {
    let panel:NSPanel
    let box=NSView()
    let imageView=NSImageView()
    let badge=NSTextField(labelWithString:"")
    let pointer=PointerView(frame:NSRect(x:0,y:0,width:210,height:84))
    var tint:NSColor
    var imageSize=CGSize(width:1,height:1)
    init(tint:NSColor,name:String) {
        self.tint=tint
        panel=NSPanel(contentRect:NSRect(x:0,y:0,width:340,height:220),styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false)
        panel.isReleasedWhenClosed=false;panel.isOpaque=false;panel.backgroundColor = .clear;panel.hasShadow=true
        panel.level=NSWindow.Level(rawValue:NSWindow.Level.screenSaver.rawValue+1)
        panel.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary,.stationary,.ignoresCycle]
        panel.hidesOnDeactivate=false;panel.isFloatingPanel=true;panel.becomesKeyOnlyIfNeeded=true;panel.isMovableByWindowBackground=true
        box.wantsLayer=true
        box.layer?.cornerRadius=12;box.layer?.masksToBounds=true;box.layer?.borderWidth=1.5
        box.layer?.borderColor=tint.withAlphaComponent(0.85).cgColor
        box.layer?.backgroundColor=NSColor(calibratedWhite:0.07,alpha:1).cgColor
        imageView.imageScaling = .scaleAxesIndependently
        badge.font=NSFont.systemFont(ofSize:10.5,weight:.semibold);badge.textColor=NSColor.white;badge.isBordered=false;badge.drawsBackground=true
        badge.backgroundColor=tint.withAlphaComponent(0.88);badge.lineBreakMode = .byTruncatingTail
        pointer.tint=tint;pointer.name=name;pointer.wantsLayer=true
        box.addSubview(imageView);box.addSubview(badge)
        panel.contentView=box
    }
    func update(image:CGImage,label:String,screen:NSScreen) {
        imageSize=CGSize(width:image.width,height:image.height)
        let ratio=imageSize.width/max(1,imageSize.height)
        var w:CGFloat=360,h:CGFloat=360/max(0.2,ratio)
        if h>250 {h=250;w=250*ratio}
        let size=NSSize(width:w,height:h)
        if !panel.isVisible {
            let v=screen.visibleFrame
            panel.setFrame(NSRect(x:v.maxX-w-18,y:v.minY+18,width:w,height:h),display:true)
            panel.alphaValue=0;panel.orderFrontRegardless()
            NSAnimationContext.runAnimationGroup({ctx in ctx.duration=0.4;self.panel.animator().alphaValue=1},completionHandler:nil)
        } else {
            let old=panel.frame
            panel.setFrame(NSRect(x:old.maxX-w,y:old.minY,width:w,height:h),display:true)
        }
        box.frame=NSRect(origin:.zero,size:size);imageView.frame=box.bounds
        imageView.image=NSImage(cgImage:image,size:size)
        badge.stringValue=" "+label+" ";badge.sizeToFit()
        badge.frame=NSRect(x:8,y:size.height-badge.frame.height-8,width:min(badge.frame.width,size.width-16),height:badge.frame.height)
    }
    // point: picture pixels, origin at the top left
    func movePointer(toImage point:CGPoint,click:Bool,then done:@escaping ()->Void) {
        let size=panel.frame.size
        let fx=point.x/max(1,imageSize.width),fy=point.y/max(1,imageSize.height)
        let target=NSPoint(x:fx*size.width-24,y:size.height-fy*size.height-60)
        if pointer.superview == nil {
            pointer.frame=NSRect(origin:NSPoint(x:size.width/2-24,y:size.height/2-60),size:pointer.frame.size)
            pointer.alphaValue=0;box.addSubview(pointer)
            NSAnimationContext.runAnimationGroup({ctx in ctx.duration=0.25;self.pointer.animator().alphaValue=1},completionHandler:nil)
        }
        let from=pointer.frame.origin,distance=hypot(target.x-from.x,target.y-from.y)
        NSAnimationContext.runAnimationGroup({ctx in
            ctx.duration=0.2+min(0.45,Double(distance)/1200)
            ctx.timingFunction=CAMediaTimingFunction(name:.easeInEaseOut)
            self.pointer.animator().setFrameOrigin(target)
        },completionHandler:{[weak self] in
            if click {pointerRipple(self?.pointer.layer,tint:self?.tint ?? .systemTeal)}
            done()
        })
    }
    func close(animated:Bool) {
        let p=panel
        if !animated {p.orderOut(nil);return}
        NSAnimationContext.runAnimationGroup({ctx in ctx.duration=0.6;p.animator().alphaValue=0},completionHandler:{p.orderOut(nil)})
    }
}

// While an agent controls the Mac: a glowing edge on every screen (click-through, left out of the agent's screenshots) and a small pill with a Stop button.
// Everything fades in softly and fades out slowly when the session ends.
final class ControlOverlay: NSObject {
    var glows:[NSWindow]=[]
    var pill:NSPanel?
    var label:NSTextField?
    var stopButton:NSButton?
    var owner=""
    var tint=NSColor.systemTeal
    var pointer:NSWindow?
    var pointerView:PointerView?
    var agentScreen:AgentScreen?
    var runningText=""
    var onStop:(()->Void)?
    var shrink:Timer?
    var windowNumbers:Set<CGWindowID> {
        var all=glows
        if let pill=pill {all.append(pill)}
        if let pointer=pointer {all.append(pointer)}
        if let agent=agentScreen {all.append(agent.panel)}
        return Set(all.map{CGWindowID($0.windowNumber)})
    }
    func show(owner:String,tint:NSColor,running:String,stopTitle:String,intensity:CGFloat=0.62,depth:CGFloat=44) {
        hide(animated:false)
        self.owner=owner;self.runningText=running;self.tint=tint
        // four thin, very soft edges per screen; low contrast so the glow is felt more than seen
        let peak=0.10+0.30*intensity
        for screen in NSScreen.screens {
            let f=screen.frame
            glows.append(makeGlowStrip(frame:NSRect(x:f.minX,y:f.maxY-depth,width:f.width,height:depth),from:CGPoint(x:0.5,y:1),to:CGPoint(x:0.5,y:0),tint:tint,peak:peak))
            glows.append(makeGlowStrip(frame:NSRect(x:f.minX,y:f.minY,width:f.width,height:depth),from:CGPoint(x:0.5,y:0),to:CGPoint(x:0.5,y:1),tint:tint,peak:peak))
            glows.append(makeGlowStrip(frame:NSRect(x:f.minX,y:f.minY,width:depth,height:f.height),from:CGPoint(x:0,y:0.5),to:CGPoint(x:1,y:0.5),tint:tint,peak:peak))
            glows.append(makeGlowStrip(frame:NSRect(x:f.maxX-depth,y:f.minY,width:depth,height:f.height),from:CGPoint(x:1,y:0.5),to:CGPoint(x:0,y:0.5),tint:tint,peak:peak))
        }
        let panel=NSPanel(contentRect:NSRect(x:0,y:0,width:340,height:38),styleMask:[.borderless,.nonactivatingPanel],backing:.buffered,defer:false)
        panel.isReleasedWhenClosed=false;panel.isOpaque=false;panel.backgroundColor = .clear;panel.hasShadow=true
        panel.level=NSWindow.Level(rawValue:NSWindow.Level.screenSaver.rawValue+1)
        panel.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary,.stationary,.ignoresCycle]
        panel.becomesKeyOnlyIfNeeded=true;panel.hidesOnDeactivate=false;panel.isFloatingPanel=true
        let box=NSView(frame:NSRect(x:0,y:0,width:340,height:38))
        box.wantsLayer=true
        box.layer?.backgroundColor=NSColor(calibratedWhite:0.07,alpha:0.92).cgColor
        box.layer?.cornerRadius=19;box.layer?.borderWidth=1;box.layer?.borderColor=tint.withAlphaComponent(0.8).cgColor
        let text=NSTextField(labelWithString:"")
        text.textColor=NSColor.white;text.font=NSFont.systemFont(ofSize:13,weight:.medium);text.lineBreakMode = .byTruncatingTail
        let button=NSButton(title:stopTitle,target:self,action:#selector(stopTapped))
        button.bezelStyle = .rounded
        box.addSubview(text);box.addSubview(button)
        panel.contentView=box
        pill=panel;label=text;stopButton=button
        layout(compact:false,animated:false)
        panel.alphaValue=0
        panel.orderFrontRegardless()
        let fadingIn=glows
        NSAnimationContext.runAnimationGroup({ctx in
            ctx.duration=0.9;ctx.timingFunction=CAMediaTimingFunction(name:.easeOut)
            for w in fadingIn {w.animator().alphaValue=1}
        },completionHandler:nil)
        NSAnimationContext.runAnimationGroup({ctx in
            ctx.duration=0.5;ctx.timingFunction=CAMediaTimingFunction(name:.easeOut)
            panel.animator().alphaValue=1
        },completionHandler:nil)
        shrink=Timer.scheduledTimer(withTimeInterval:6,repeats:false){[weak self] _ in self?.layout(compact:true,animated:true)}
    }
    func layout(compact:Bool,animated:Bool) {
        guard let panel=pill,let box=panel.contentView,let text=label,let button=stopButton else{return}
        let width:CGFloat=compact ? 190 : 340
        let apply={
            text.stringValue=compact ? "● "+self.owner : self.owner+" "+self.runningText
            text.frame=NSRect(x:16,y:9,width:width-104,height:20)
            button.frame=NSRect(x:width-84,y:6,width:72,height:26)
            box.frame=NSRect(x:0,y:0,width:width,height:38)
            if let screen=NSScreen.screens.first {
                let frame=NSRect(x:screen.frame.midX-width/2,y:screen.visibleFrame.maxY-48,width:width,height:38)
                panel.setFrame(frame,display:true,animate:animated)
            }
        }
        if !animated {apply();return}
        // the sentence fades out, the pill glides to its short size, the name fades back in
        NSAnimationContext.runAnimationGroup({ctx in
            ctx.duration=0.3
            text.animator().alphaValue=0
        },completionHandler:{
            apply()
            NSAnimationContext.runAnimationGroup({ctx in
                ctx.duration=0.45
                text.animator().alphaValue=1
            },completionHandler:nil)
        })
    }
    func movePointer(to point:CGPoint,click:Bool,then done:@escaping ()->Void) {
        guard let screen=NSScreen.screens.first,!glows.isEmpty else {done();return}
        let size=NSSize(width:210,height:84)
        let target=NSPoint(x:point.x-24,y:screen.frame.height-point.y-60)
        if pointer == nil {
            let w=NSWindow(contentRect:NSRect(origin:.zero,size:size),styleMask:[.borderless],backing:.buffered,defer:false)
            w.isReleasedWhenClosed=false;w.isOpaque=false;w.backgroundColor = .clear;w.hasShadow=false;w.ignoresMouseEvents=true
            w.level=NSWindow.Level(rawValue:NSWindow.Level.screenSaver.rawValue+2)
            w.collectionBehavior=[.canJoinAllSpaces,.fullScreenAuxiliary,.stationary,.ignoresCycle]
            let view=PointerView(frame:NSRect(origin:.zero,size:size))
            view.tint=tint;view.name=owner;view.wantsLayer=true
            w.contentView=view
            let mouse=NSEvent.mouseLocation
            w.setFrameOrigin(NSPoint(x:mouse.x-24,y:mouse.y-60))
            w.alphaValue=0;w.orderFrontRegardless()
            pointer=w;pointerView=view
            NSAnimationContext.runAnimationGroup({ctx in ctx.duration=0.3;w.animator().alphaValue=1},completionHandler:nil)
        }
        guard let w=pointer else {done();return}
        let from=w.frame.origin,distance=hypot(target.x-from.x,target.y-from.y)
        NSAnimationContext.runAnimationGroup({ctx in
            ctx.duration=0.22+min(0.5,Double(distance)/2400)
            ctx.timingFunction=CAMediaTimingFunction(name:.easeInEaseOut)
            w.animator().setFrame(NSRect(origin:target,size:size),display:true)
        },completionHandler:{[weak self] in
            if click {self?.ripple()}
            done()
        })
    }
    func ripple() {pointerRipple(pointerView?.layer,tint:tint)}
    // Background work: the agent's pointer shows on the real window when that app is in front, otherwise on the agent's own small screen.
    func movePointerInTarget(screenPoint:CGPoint,imagePoint:CGPoint,onScreen:Bool,click:Bool,then done:@escaping ()->Void) {
        if onScreen || agentScreen == nil {movePointer(to:screenPoint,click:click,then:done);return}
        agentScreen?.movePointer(toImage:imagePoint,click:click,then:done)
    }
    func showAgentScreen(image:CGImage,label:String) {
        guard !glows.isEmpty,let screen=NSScreen.screens.first else{return}
        if agentScreen == nil {agentScreen=AgentScreen(tint:tint,name:owner)}
        agentScreen?.update(image:image,label:label,screen:screen)
    }
    func hideAgentScreen() {
        let old=agentScreen;agentScreen=nil
        old?.close(animated:true)
    }
    @objc func stopTapped() {onStop?()}
    func hide(animated:Bool=true) {
        shrink?.invalidate();shrink=nil
        let oldGlows=glows,oldPill=pill,oldButton=stopButton,oldPointer=pointer,oldAgent=agentScreen
        glows=[];pill=nil;label=nil;stopButton=nil;pointer=nil;pointerView=nil;agentScreen=nil
        if oldGlows.isEmpty && oldPill == nil {oldAgent?.close(animated:false);return}
        if !animated {
            for w in oldGlows {w.orderOut(nil)}
            oldPill?.orderOut(nil);oldPointer?.orderOut(nil);oldAgent?.close(animated:false)
            return
        }
        oldAgent?.close(animated:true)
        // the name banner and the glow dissolve slowly instead of vanishing
        oldButton?.isEnabled=false
        NSAnimationContext.runAnimationGroup({ctx in
            ctx.duration=0.25
            oldButton?.animator().alphaValue=0
        },completionHandler:nil)
        NSAnimationContext.runAnimationGroup({ctx in
            ctx.duration=1.6;ctx.timingFunction=CAMediaTimingFunction(name:.easeInEaseOut)
            for w in oldGlows {w.animator().alphaValue=0}
            oldPill?.animator().alphaValue=0
            oldPointer?.animator().alphaValue=0
        },completionHandler:{
            for w in oldGlows {w.orderOut(nil)}
            oldPill?.orderOut(nil);oldPointer?.orderOut(nil)
        })
    }
}

final class JarvisApp: NSObject, NSApplicationDelegate, WKScriptMessageHandler, WKNavigationDelegate, WKUIDelegate, AVSpeechSynthesizerDelegate, AVAudioPlayerDelegate, NSWindowDelegate, UNUserNotificationCenterDelegate {
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
    let overlay=ControlOverlay()
    var captureScale=1.0
    var bgTarget:BackgroundTarget?
    var bgText:(pid:pid_t,element:AXUIElement)?
    var controlActivity:NSObjectProtocol?  // keeps macOS from napping this app (and slowing its page) while an agent works behind Berke's windows
    let voiceIDs=["F1","F2","F3","F4","F5","M1","M2","M3","M4","M5"]
    let defaultAgentVoices=["JARVIS":"F4","VISION":"M3","FRIDAY":"M5","EDITH":"F3","NOVA":"F2","KAREN":"M2"]
    let engine = AVAudioEngine()
    var recognition: SFSpeechRecognitionTask?
    var request: SFSpeechAudioBufferRecognitionRequest?
    var silenceTimer: Timer?
    var listenTimer: Timer?
    var listening = false
    var listenWanted = false
    var tapInstalled = false
    var transcript = ""
    var candidates:[SpeechCandidate]=[]
    var finalizing=false
    var finalizeTimer:Timer?
    var project: URL?
    var screenTimer: Timer?
    var hostTimer: Timer?
    var hostWindow: SCWindow?
    var hostBusy = false
    var uiLanguage: String {UserDefaults.standard.string(forKey:"jarvisLanguage") ?? "tr"}
    func L(_ tr:String,_ en:String)->String {uiLanguage == "en" ? en : tr}
    var captureBusy = false
    var captureEnabled = false
    var cloudSpeechAllowed = UserDefaults.standard.bool(forKey:"cloudSpeechAlways")
    var cloudSpeechDeclined = false
    var didGreet = false
    var generation = UUID()
    let exclusions: Set<String> = [".git", "node_modules", ".venv", "venv", "__pycache__", ".build", "build", "dist", ".DS_Store"]

    func applicationDidFinishLaunching(_ notification: Notification) {
        UNUserNotificationCenter.current().delegate=self
        NSApp.setActivationPolicy(.regular)
        configureMenus()
        let controller=WKUserContentController()
        controller.add(self,name:"native")
        let config=WKWebViewConfiguration();config.userContentController=controller
        web=WKWebView(frame:.zero,configuration:config);web.navigationDelegate=self;web.uiDelegate=self
        web.setValue(false,forKey:"drawsBackground")
        window=NSWindow(contentRect:NSRect(x:0,y:0,width:1400,height:940),styleMask:[.titled,.closable,.miniaturizable,.resizable],backing:.buffered,defer:false)
        window.title=L(J("JARVIS — Berke’nin Çalışma Alanı"),"JARVIS — Berke’s Workspace");window.minSize=NSSize(width:1000,height:700);window.center();window.contentView=web;window.delegate=self
        window.backgroundColor=NSColor(calibratedRed:0.043,green:0.063,blue:0.082,alpha:1)
        window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
        speaker.delegate=self
        startBackend()
    }
    func applicationDidBecomeActive(_ notification:Notification) {
        if web != nil {emit("app-focus",["active":true])}
    }
    func applicationDidResignActive(_ notification:Notification) {
        if web != nil {emit("app-focus",["active":false])}
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
        emitAgentVoices()
    }
    func agentVoice(_ agent:String)->String {
        let saved=UserDefaults.standard.string(forKey:"agentVoice."+agent) ?? ""
        if voiceIDs.contains(saved) {return saved}
        return defaultAgentVoices[agent] ?? "F4"
    }
    func emitAgentVoices() {
        var map:[String:String]=[:]
        for name in ["JARVIS","VISION","FRIDAY","EDITH","NOVA","KAREN"] {map[name]=agentVoice(name)}
        emit("agent-voices",["voices":map])
    }
    @objc func about() { let alert=NSAlert();alert.messageText="JARVIS / MARK VI · 0.7.6";alert.informativeText=L("Berke için yerel Mac çalışma alanı. JARVIS sohbeti Gemini Flash ile, kod işleri seçilen geliştirici modeliyle çalışır. Codex ve Claude gündelik sohbet için otomatik çağrılmaz. Yerel sohbet ve yalnızca kadın sesleri seçilebilir. Aktif bilgisayar görevleri ChatGPT uygulamasına devredilebilir.","A local Mac workspace for Berke. JARVIS chat uses Gemini Flash; development uses the selected coding model. Everyday chat does not automatically call Codex or Claude. Local chat and female voices are available. Computer tasks can be handed off to the official ChatGPT app.");alert.runModal() }
    func alert(_ text: String) { let a=NSAlert();a.messageText="JARVIS";a.informativeText=text;a.runModal() }
    func startBackend(attempt:Int=0) {
        guard let resources=Bundle.main.resourceURL else {return}
        let data=FileManager.default.urls(for:.applicationSupportDirectory,in:.userDomainMask)[0].appendingPathComponent("BerkeJARVIS",isDirectory:true)
        do { try FileManager.default.createDirectory(at:data,withIntermediateDirectories:true)
            let runtimeFile=resources.appendingPathComponent("PythonRuntime.txt")
            let python=(try String(contentsOf:runtimeFile,encoding:.utf8)).trimmingCharacters(in:.whitespacesAndNewlines)
            guard FileManager.default.isExecutableFile(atPath:python) else { throw NSError(domain:J("Python 3 bulunamadı. README kurulum bölümüne bak."),code:1) }
            let process=Process();process.executableURL=URL(fileURLWithPath:python)
            // Guncelle.command keeps a copy of the project's Python and web files here, so code-only updates never touch the signed app (macOS keeps its Screen Recording/Accessibility grants). Without it, the bundled copy runs.
            let live=data.appendingPathComponent("server-live",isDirectory:true)
            var serverDir=resources.appendingPathComponent("server",isDirectory:true)
            if FileManager.default.fileExists(atPath:live.appendingPathComponent("app.py").path) && FileManager.default.fileExists(atPath:live.appendingPathComponent("static/index.html").path) {serverDir=live}
            process.arguments=[serverDir.appendingPathComponent("app.py").path,"--port","0","--data-dir",data.path,"--connect-codex"]
            var env=ProcessInfo.processInfo.environment
            for key in Array(env.keys) where key.contains("API_KEY") || key.hasPrefix("GOOGLE_") || key.hasPrefix("ANTHROPIC_") {env.removeValue(forKey:key)}
            env["PYTHONDONTWRITEBYTECODE"]="1";env["JARVIS_RESOURCES"]=resources.path;process.environment=env
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
            if let picks=body["agentVoices"] as? [String:String] {
                for (name,id) in picks where name.count<=20 && name.allSatisfy({$0.isLetter || $0.isNumber || $0=="_" || $0=="-"}) && voiceIDs.contains(id) {UserDefaults.standard.set(id,forKey:"agentVoice."+name)}
            }
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
        case "reveal-jarvis-app":
            NSWorkspace.shared.activateFileViewerSelecting([Bundle.main.bundleURL])
        case "open-mac-permission":
            let pages=["screen":"Privacy_ScreenCapture","accessibility":"Privacy_Accessibility"]
            if let page=body["page"] as? String,let target=pages[page],let url=URL(string:"x-apple.systempreferences:com.apple.preference.security?"+target) {
                if !NSWorkspace.shared.open(url) {NSWorkspace.shared.open(URL(fileURLWithPath:"/System/Applications/System Settings.app"))}
            }
        case "desktop-permissions":
            _=CGRequestScreenCaptureAccess()
            _=AXIsProcessTrustedWithOptions([kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String:true] as CFDictionary)
            emit("desktop-status",["screen":CGPreflightScreenCaptureAccess(),"accessibility":AXIsProcessTrusted()])
        case "desktop-overlay":
            if body["active"] as? Bool == true {
                let owner=String((body["owner"] as? String ?? "JARVIS").prefix(20))
                var tint=NSColor.systemTeal
                if let hex=body["color"] as? String,hex.hasPrefix("#"),hex.count==7,let value=UInt32(hex.dropFirst(),radix:16) {
                    tint=NSColor(calibratedRed:CGFloat((value>>16)&255)/255,green:CGFloat((value>>8)&255)/255,blue:CGFloat(value&255)/255,alpha:1)
                }
                overlay.onStop={[weak self] in self?.emit("desktop-stop-request")}
                let level=CGFloat(min(1.0,max(0.2,(body["intensity"] as? Double) ?? 0.62)))
                let depth=CGFloat(min(90.0,max(24.0,(body["depth"] as? Double) ?? 44)))
                overlay.show(owner:owner,tint:tint,running:L("bilgisayarını kullanıyor","is using your computer"),stopTitle:L("Durdur","Stop"),intensity:level,depth:depth)
                if controlActivity == nil {controlActivity=ProcessInfo.processInfo.beginActivity(options:[.userInitiated],reason:"Agent is working on the Mac")}
            } else {
                overlay.hide();bgTarget=nil;bgText=nil
                if let token=controlActivity {ProcessInfo.processInfo.endActivity(token);controlActivity=nil}
            }
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
        case "speak":
            if let text=body["text"] as? String {
                var chosenVoice:String?=nil
                if let wanted=body["voice"] as? String,voiceIDs.contains(wanted) {chosenVoice=wanted}
                speak(String(text.prefix(4000)),agent:(body["agent"] as? String) ?? "JARVIS",voiceOverride:chosenVoice)
            }
        case "agent-voices": emitAgentVoices()
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
        case "notify":
            let title=(body["title"] as? String) ?? "JARVIS",text=(body["body"] as? String) ?? ""
            postBanner(String(title.prefix(90)),String(text.prefix(200)),action:body["action"] as? String)
        case "open-notification-settings": NSWorkspace.shared.open(URL(fileURLWithPath:"/System/Applications/System Settings.app"))
        case "request-notifications":
            UNUserNotificationCenter.current().requestAuthorization(options:[.alert,.sound,.badge]) { granted,error in
                DispatchQueue.main.async {
                    self.emit("notification-status",["status":granted ? "allowed" : "denied"])
                    if error != nil && !granted {self.emit("notification-status",["status":"denied"])}
                }
            }
        case "notification-status":
            UNUserNotificationCenter.current().getNotificationSettings { settings in
                let status: String
                switch settings.authorizationStatus {
                case .authorized, .provisional: status="allowed"
                case .denied: status="denied"
                case .notDetermined: status="not-set"
                default: status="unknown"
                }
                DispatchQueue.main.async {self.emit("notification-status",["status":status])}
            }
        case "badge":
            let count=(body["count"] as? Int) ?? 0
            NSApp.dockTile.badgeLabel=count>0 ? String(count) : nil
        case "ready": emit("app-focus",["active":NSApp.isActive]);if !didGreet {didGreet=true;speak(L(J("Merhaba Berke. Buradayım. Bugün ne üzerinde çalışalım?"),"Hello, Berke. I am here. What shall we work on today?"));emitVoices()}
        default: break
        }
    }
    // Photo/video picker for the chat's attach button (WKWebView shows no file panel without this).
    func webView(_ webView:WKWebView,runOpenPanelWith parameters:WKOpenPanelParameters,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping([URL]?)->Void) {
        let panel=NSOpenPanel();panel.canChooseFiles=true;panel.canChooseDirectories=false;panel.allowsMultipleSelection=false
        panel.allowedFileTypes=["pdf","docx","xlsx","pptx","txt","md","csv","json","html","htm","rtf","odt","ods","odp","yaml","yml","xml","jpg","jpeg","png","gif","webp","heic","heif","mp4","mov","m4v","webm"]
        panel.message=L("Sohbete eklenecek fotoğraf, video veya belgeyi seç","Choose a photo, video or document to attach")
        panel.begin{response in completionHandler(response == .OK ? panel.urls : nil)}
    }
    func webView(_ webView:WKWebView,decidePolicyFor navigationAction:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void) {
        if let url=navigationAction.request.url,url.host=="127.0.0.1",url.port==port {decisionHandler(.allow)} else {decisionHandler(.cancel)}
    }
    // Banner for finished work, approvals and low limits. Uses the system notification centre; falls back to osascript if it is not allowed.
    func postBanner(_ title:String,_ text:String,action:String?=nil) {
        NSApp.requestUserAttention(.informationalRequest)
        let center=UNUserNotificationCenter.current()
        center.getNotificationSettings { settings in
            switch settings.authorizationStatus {
            case .authorized,.provisional:
                let content=UNMutableNotificationContent();content.title=title;content.body=text;content.sound=UNNotificationSound.default
                if action=="mac-permissions" {content.userInfo=["jarvis_action":"mac-permissions"]}
                center.add(UNNotificationRequest(identifier:UUID().uuidString,content:content,trigger:nil),withCompletionHandler:nil)
            case .notDetermined:
                center.requestAuthorization(options:[.alert,.sound]) { granted,_ in
                    DispatchQueue.main.async {
                        if granted {self.postBanner(title,text,action:action)} else {self.fallbackBanner(title,text)}
                    }
                }
            default:
                DispatchQueue.main.async {self.fallbackBanner(title,text)}
            }
        }
    }
    func userNotificationCenter(_ center:UNUserNotificationCenter,didReceive response:UNNotificationResponse,withCompletionHandler completionHandler:@escaping ()->Void) {
        let action=response.notification.request.content.userInfo["jarvis_action"] as? String
        DispatchQueue.main.async {
            self.window.makeKeyAndOrderFront(nil);NSApp.activate(ignoringOtherApps:true)
            if action=="mac-permissions" {self.emit("notification-action",["action":"mac-permissions"])}
            completionHandler()
        }
    }
    func fallbackBanner(_ title:String,_ text:String) {
        func quoted(_ value:String)->String {value.replacingOccurrences(of:"\\",with:"\\\\").replacingOccurrences(of:"\"",with:"\\\"")}
        let process=Process();process.executableURL=URL(fileURLWithPath:"/usr/bin/osascript")
        process.arguments=["-e","display notification \"\(quoted(text))\" with title \"\(quoted(title))\" sound name \"Glass\""]
        try? process.run()
    }
    func stopSpeech(notify:Bool=true) {
        voiceGeneration=UUID();voiceProcess?.terminate();voiceProcess=nil;voicePlayer?.stop();voicePlayer=nil
        if let file=voiceFile {try? FileManager.default.removeItem(at:file);voiceFile=nil}
        currentUtterance=nil;speaker.stopSpeaking(at:.immediate)
        if notify {emit("speaking",["active":false])}
    }
    func speak(_ text:String,agent:String="JARVIS",voiceOverride:String?=nil) {
        listenWanted=false;stopListening(deliver:false);stopSpeech(notify:false)
        let voiceID=voiceOverride ?? agentVoice(agent)
        let lower=text.lowercased()
        let turkishWords=["merhaba"," için "," bir "," değil"," nasıl","ş","ğ","ı","ü","ö","ç"]
        let englishWords=["hello"," the "," you "," this ","please","what ","i am","yes,","let us"]
        let locale=turkishWords.contains(where:{lower.contains($0)}) ? "tr-TR" : englishWords.contains(where:{lower.contains($0)}) ? "en-US" : (uiLanguage == "en" ? "en-US" : "tr-TR")
        if UserDefaults.standard.string(forKey:"voiceEngine") != "system",speakNatural(text,locale,voiceID) {return}
        speakSystem(text,locale,male:voiceID.hasPrefix("M"))
    }
    func speakNatural(_ text:String,_ locale:String,_ voiceID:String)->Bool {
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
            else {try? FileManager.default.removeItem(at:output);self.voiceFile=nil;self.emit("voice-fallback",["message":self.L("Doğal ses açılamadı (\(voiceID)); macOS sesi kullanılıyor.","Natural voice unavailable (\(voiceID)); using a macOS voice.")]);self.speakSystem(text,locale,male:voiceID.hasPrefix("M"))}
        }}
        do {try process.run();voiceProcess=process;emit("speaking",["active":true]);let data=try JSONSerialization.data(withJSONObject:["text":text,"lang":locale.hasPrefix("tr") ? "tr":"en","style":UserDefaults.standard.string(forKey:"voiceStyle") ?? "formal","voice":voiceID,"output":output.path]);input.fileHandleForWriting.write(data);try? input.fileHandleForWriting.close()
            DispatchQueue.main.asyncAfter(deadline:.now()+25){[weak self] in if self?.voiceGeneration==token,self?.voiceProcess?.isRunning==true {self?.voiceProcess?.terminate()}}
            return true
        } catch {voiceProcess=nil;return false}
    }
    func audioPlayerDidFinishPlaying(_ player:AVAudioPlayer,successfully flag:Bool) {if player === voicePlayer {voicePlayer=nil;if let file=voiceFile {try? FileManager.default.removeItem(at:file);voiceFile=nil};emit("speaking",["active":false])}}

    func speakSystem(_ text:String,_ locale:String,male:Bool=false) {
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
        speech.rate=0.5;speech.pitchMultiplier=male ? 0.78 : 1.0;speech.preUtteranceDelay=0.08;speech.postUtteranceDelay=0.12
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
        if selected == "auto",beginDualListening() {return}
        let locale=selected == "auto" ? (uiLanguage == "en" ? "en-GB" : "tr-TR") : selected
        guard let recognizer=SFSpeechRecognizer(locale:Locale(identifier:locale)),recognizer.isAvailable else {emit("voice-error",["message":J("Türkçe konuşma tanıma şu anda kullanılamıyor. Yazılı sohbet veya macOS Dikte kullanabilirsin.")]);return}
        if !recognizer.supportsOnDeviceRecognition && !askCloudSpeech() {emit("voice-error",["message":J("Ses tanıma açılmadı. Yazılı sohbet hazır.")]);return}
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
    // Turkish on-device recognition is missing on some Macs. Apple's server recognition needs a clear yes: once for this session, or always.
    func askCloudSpeech()->Bool {
        if cloudSpeechAllowed {return true}
        if cloudSpeechDeclined {return false}
        let a=NSAlert()
        a.messageText=L("Türkçe ses tanıma için Apple hizmeti gerekiyor","Turkish speech recognition needs Apple’s service")
        a.informativeText=L("Bu Mac’te Türkçe cihaz içi tanıma yok. Devam edersen mikrofon sesi Apple’ın konuşma tanıma hizmetine gönderilebilir; AI sağlayıcılarına gönderilmez. İstersen Sistem Ayarları → Klavye → Dikte → Diller bölümünden Türkçe’yi indirip her şeyi bu Mac’te tutabilirsin.","There is no on-device Turkish recognition on this Mac. If you continue, microphone audio may be sent to Apple’s speech recognition service; it is never sent to AI providers. You can download Turkish under System Settings → Keyboard → Dictation → Languages to keep everything on this Mac.")
        a.addButton(withTitle:L("Bu oturumda Apple ile devam et","Use Apple recognition this session"))
        a.addButton(withTitle:L("Her zaman Apple ile devam et","Always use Apple recognition"))
        a.addButton(withTitle:L("Vazgeç","Cancel"))
        let answer=a.runModal()
        if answer == .alertFirstButtonReturn {cloudSpeechAllowed=true;return true}
        if answer == .alertSecondButtonReturn {cloudSpeechAllowed=true;UserDefaults.standard.set(true,forKey:"cloudSpeechAlways");return true}
        cloudSpeechDeclined=true;return false
    }
    func dualRecognizer(_ ids:[String])->(String,SFSpeechRecognizer)? {
        for id in ids {if let r=SFSpeechRecognizer(locale:Locale(identifier:id)),r.isAvailable,r.supportsOnDeviceRecognition {return (id,r)}}
        for id in ids {if let r=SFSpeechRecognizer(locale:Locale(identifier:id)),r.isAvailable {return (id,r)}}
        return nil
    }
    // Automatic language: Turkish and English recognizers listen to the same audio; the more confident result wins.
    func beginDualListening()->Bool {
        var found:[(String,SFSpeechRecognizer)]=[]
        if let tr=dualRecognizer(["tr-TR"]) {found.append(tr)}
        if let en=dualRecognizer(["en-US","en-GB"]) {found.append(en)}
        if found.contains(where:{!$0.1.supportsOnDeviceRecognition}) && !askCloudSpeech() {found=found.filter{$0.1.supportsOnDeviceRecognition}}
        if found.isEmpty {return false}
        do {
            stopListening(deliver:false);transcript="";finalizing=false
            let gen=UUID();generation=gen
            let made=found.map{SpeechCandidate(locale:$0.0,recognizer:$0.1)}
            for c in made {c.request.shouldReportPartialResults=true;c.request.requiresOnDeviceRecognition=c.recognizer.supportsOnDeviceRecognition}
            candidates=made
            let input=engine.inputNode;let format=input.outputFormat(forBus:0)
            guard format.sampleRate > 0 && format.channelCount > 0 else {throw NSError(domain:J("Geçerli mikrofon bulunamadı"),code:1)}
            input.installTap(onBus:0,bufferSize:1024,format:format){buffer,_ in for c in made {c.request.append(buffer)}};tapInstalled=true
            engine.prepare();try engine.start();listening=true
            emit("listening",["active":true,"local":made.allSatisfy{$0.recognizer.supportsOnDeviceRecognition},"auto":true])
            for c in made {
                c.task=c.recognizer.recognitionTask(with:c.request){[weak self] result,error in
                    DispatchQueue.main.async {
                        guard let self=self,self.generation==gen else{return}
                        if let result=result {
                            c.text=result.bestTranscription.formattedString
                            if result.isFinal {
                                let segments=result.bestTranscription.segments
                                c.confidence=segments.isEmpty ? 0 : segments.reduce(Float(0)){$0+$1.confidence}/Float(segments.count)
                                c.finished=true
                            }
                            self.dualUpdate(final:result.isFinal)
                        } else if error != nil {c.finished=true;self.dualUpdate(final:false)}
                    }
                }
            }
            listenTimer=Timer.scheduledTimer(withTimeInterval:45,repeats:false){[weak self]_ in self?.finishDual()}
            return true
        } catch {
            stopListening(deliver:false);emit("voice-error",["message":J("Mikrofon başlatılamadı: \(error.localizedDescription)")]);return true
        }
    }
    func dualUpdate(final:Bool) {
        if finalizing {if candidates.allSatisfy({$0.finished}) {completeDual()};return}
        guard listening else{return}
        if candidates.allSatisfy({$0.finished}) {finishDual();return}
        let primary=UserDefaults.standard.string(forKey:"speechLastLocale") ?? "tr-TR"
        let lead=candidates.first(where:{$0.locale==primary && !$0.text.isEmpty}) ?? candidates.max(by:{$0.text.count < $1.text.count})
        let shown=lead?.text ?? ""
        if candidates.contains(where:{!$0.text.isEmpty}) {
            silenceTimer?.invalidate();silenceTimer=Timer.scheduledTimer(withTimeInterval:1.6,repeats:false){[weak self]_ in self?.finishDual()}
        }
        if shown != transcript {transcript=shown;emit("transcript",["text":shown,"final":false])}
        if final {finishDual()}
    }
    func finishDual() {
        guard listening,!finalizing,!candidates.isEmpty else{return}
        finalizing=true;silenceTimer?.invalidate();listenTimer?.invalidate()
        if engine.isRunning {engine.stop()};if tapInstalled {engine.inputNode.removeTap(onBus:0);tapInstalled=false}
        for c in candidates {c.request.endAudio()}
        finalizeTimer?.invalidate()
        finalizeTimer=Timer.scheduledTimer(withTimeInterval:1.8,repeats:false){[weak self]_ in self?.completeDual()}
        if candidates.allSatisfy({$0.finished}) {completeDual()}
    }
    func completeDual() {
        guard listening,finalizing else{return}
        finalizeTimer?.invalidate()
        let pick=chooseCandidate()
        let scores=candidates.map{String($0.locale.prefix(2))+" "+String(format:"%.2f",Double($0.confidence))}.joined(separator:" · ")
        transcript=pick?.text ?? ""
        if let p=pick {UserDefaults.standard.set(p.locale,forKey:"speechLastLocale")}
        let chosen=pick?.locale ?? ""
        stopListening(deliver:true)
        if !chosen.isEmpty {emit("speech-detected",["locale":chosen,"scores":scores])}
    }
    func chooseCandidate()->SpeechCandidate? {
        let spoken=candidates.filter{!$0.text.trimmingCharacters(in:.whitespacesAndNewlines).isEmpty}
        if spoken.count < 2 {return spoken.first}
        let last=UserDefaults.standard.string(forKey:"speechLastLocale") ?? "tr-TR"
        let preferred=spoken.first(where:{$0.locale==last}) ?? spoken[0]
        guard let best=spoken.max(by:{$0.confidence < $1.confidence}) else {return preferred}
        if best.confidence >= 0.01 {return best.confidence-preferred.confidence >= 0.05 ? best : preferred}
        // Confidence unavailable: compare how well each text fits its own language.
        let scored=spoken.map{($0,languageMatch($0))}
        let base=scored.first(where:{$0.0 === preferred})?.1 ?? 0
        if let top=scored.max(by:{$0.1 < $1.1}),top.1-base >= 0.25 {return top.0}
        return preferred
    }
    func languageMatch(_ c:SpeechCandidate)->Double {
        let recognizer=NLLanguageRecognizer();recognizer.languageConstraints=[.turkish,.english];recognizer.processString(c.text)
        let want:NLLanguage=c.locale.hasPrefix("tr") ? .turkish : .english
        return recognizer.languageHypotheses(withMaximum:2)[want] ?? 0
    }
    func stopListening(deliver:Bool) {
        let wasListening=listening;listening=false;generation=UUID();silenceTimer?.invalidate();listenTimer?.invalidate()
        if engine.isRunning {engine.stop()};if tapInstalled {engine.inputNode.removeTap(onBus:0);tapInstalled=false}
        request?.endAudio();recognition?.cancel();recognition=nil;request=nil
        for c in candidates {if !finalizing {c.request.endAudio()};c.task?.cancel()}
        candidates=[];finalizing=false;finalizeTimer?.invalidate()
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
        let targetBundle=(body["target_bundle"] as? String) ?? ""
        if tool=="desktop_observe" {if targetBundle.isEmpty {captureDesktopForAgent(id)} else {captureDesktopTarget(id,bundle:targetBundle)};return}
        guard AXIsProcessTrusted() else {desktopResult(id,["error":"macOS Erişilebilirlik izni gerekli. Kontrol gerçekleştirilmedi."]);return}
        if tool=="desktop_open_app" {
            let apps=["notes":"/System/Applications/Notes.app","textedit":"/System/Applications/TextEdit.app","safari":"/Applications/Safari.app","finder":"/System/Library/CoreServices/Finder.app","chrome":"/Applications/Google Chrome.app","preview":"/System/Applications/Preview.app","calendar":"/System/Applications/Calendar.app","reminders":"/System/Applications/Reminders.app","calculator":"/System/Applications/Calculator.app","pages":"/Applications/Pages.app","numbers":"/Applications/Numbers.app","keynote":"/Applications/Keynote.app","xcode":"/Applications/Xcode.app","vscode":"/Applications/Visual Studio Code.app","antigravity":"/Applications/Antigravity.app"]
            guard let app=args["app"] as? String,let path=apps[app] else{desktopResult(id,["error":"Uygulama izinli değil."]);return}
            NSWorkspace.shared.openApplication(at:URL(fileURLWithPath:path),configuration:NSWorkspace.OpenConfiguration()){_,error in
                DispatchQueue.main.async{self.desktopResult(id,error == nil ? ["acted":true] : ["error":error!.localizedDescription])}
            }
            return
        }
        if tool=="desktop_open_url" {
            guard let raw=args["url"] as? String,let url=URL(string:raw),["http","https"].contains(url.scheme ?? ""),url.user==nil,url.password==nil else {desktopResult(id,["error":"Web adresi izinli değil."]);return}
            // opened without activating the browser, so Berke's front app stays where it is
            let config=NSWorkspace.OpenConfiguration();config.activates=false
            NSWorkspace.shared.open(url,configuration:config){_,error in DispatchQueue.main.async{self.desktopResult(id,error == nil ? ["acted":true] : ["error":error!.localizedDescription])}}
            return
        }
        if !targetBundle.isEmpty {performBackgroundAction(id,tool:tool,args:args,bundle:targetBundle,editorOK:(body["editor_ok"] as? Bool) == true);return}
        let blocked=["com.apple.Terminal","com.googlecode.iterm2","com.apple.systempreferences","com.apple.SecurityAgent","com.apple.loginwindow","com.apple.keychainaccess"]
        let front=NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? ""
        guard !blocked.contains(front) else {desktopResult(id,["error":"Bu sistem/terminal penceresinde otomatik eylem kapalı."]);return}
        if tool != "desktop_open_url" && front == (Bundle.main.bundleIdentifier ?? "local.berke.jarvis") {desktopResult(id,["error":"JARVIS’in kendi penceresinde eylem kapalı. Önce hedef uygulamayı aç ve ekranı gözlemle.","application":"JARVIS"]);return}
        // Code editors: typing or shortcuts could run commands in their terminal outside the project sandbox, so JARVIS sends editor_ok only after Berke approved that very action.
        let editors=["com.microsoft.VSCode","com.google.antigravity","com.apple.dt.Xcode"]
        if (tool=="desktop_type" || tool=="desktop_key") && editors.contains(front) && (body["editor_ok"] as? Bool) != true {desktopResult(id,["error":"Kod düzenleyiciye yazmak için önce ekranı gözlemle; sonra yaz."]);return}
        if (tool=="desktop_type" || tool=="desktop_key") && editors.contains(front) && focusedLooksLikeTerminal() {desktopResult(id,["error":"İmleç editörün terminal panelinde. Terminale yazmak kapalı; önce editörün metin alanına tıkla."]);return}
        guard let screen=NSScreen.screens.first else {desktopResult(id,["error":"Ekran bulunamadı."]);return}
        if tool=="desktop_click" || tool=="desktop_move" {
            guard let px=args["x"] as? Double,let py=args["y"] as? Double,px.isFinite,py.isFinite,px>=0,py>=0 else {desktopResult(id,["error":"Koordinat ekran sınırının dışında."]);return}
            let x=px/captureScale,y=py/captureScale
            guard x<Double(screen.frame.width),y<Double(screen.frame.height) else {desktopResult(id,["error":"Koordinat ekran sınırının dışında."]);return}
            let point=CGPoint(x:x,y:y)
            let isClick = tool=="desktop_click"
            overlay.movePointer(to:point,click:isClick){[self] in
                CGWarpMouseCursorPosition(point)
                CGEvent(mouseEventSource:nil,mouseType:.mouseMoved,mouseCursorPosition:point,mouseButton:.left)?.post(tap:.cghidEventTap)
                if !isClick {desktopResult(id,["acted":true,"application":front,"pointer":["x":px,"y":py]]);return}
                CGEvent(mouseEventSource:nil,mouseType:.leftMouseDown,mouseCursorPosition:point,mouseButton:.left)?.post(tap:.cghidEventTap)
                CGEvent(mouseEventSource:nil,mouseType:.leftMouseUp,mouseCursorPosition:point,mouseButton:.left)?.post(tap:.cghidEventTap)
                desktopResult(id,["acted":true,"application":front])
            }
            return
        } else if tool=="desktop_type" {
            guard let text=args["text"] as? String,text.count<=2000 else {desktopResult(id,["error":"Metin sınırı aşıldı."]);return}
            guard !text.isEmpty else {desktopResult(id,["error":"Yazılacak metin boş."]);return}
            var focused:CFTypeRef?
            guard AXUIElementCopyAttributeValue(AXUIElementCreateSystemWide(),kAXFocusedUIElementAttribute as CFString,&focused) == .success,let focused=focused,CFGetTypeID(focused)==AXUIElementGetTypeID() else {desktopResult(id,["error":"Odaktaki metin alanı okunamadı. Önce boş editöre tıkla."]);return}
            let element=focused as! AXUIElement
            var subrole:CFTypeRef?,role:CFTypeRef?
            AXUIElementCopyAttributeValue(element,kAXSubroleAttribute as CFString,&subrole)
            AXUIElementCopyAttributeValue(element,kAXRoleAttribute as CFString,&role)
            guard (subrole as? String) != "AXSecureTextField" else {desktopResult(id,["error":"Parola/güvenli alana yazma engellendi."]);return}
            guard ["AXTextArea","AXTextField","AXComboBox"].contains(role as? String ?? "") else {desktopResult(id,["error":"Bir metin editörü odakta değil. Yeni notun boş yazı alanına tıkla, ekranı tekrar gözlemle ve sonra yaz.","focused_role":role as? String ?? "unknown"]);return}
            // Insert into the selection rather than replacing an entire existing document.
            var settable:DarwinBoolean=false
            if AXUIElementIsAttributeSettable(element,kAXSelectedTextAttribute as CFString,&settable) == .success,settable.boolValue,
               AXUIElementSetAttributeValue(element,kAXSelectedTextAttribute as CFString,text as CFString) == .success {
                desktopResult(id,["acted":true,"application":front,"method":"accessibility-insert","needs_visual_verification":true]);return
            }
            // Private event state and explicit flags avoid carrying Cmd from the preceding shortcut.
            guard let source=CGEventSource(stateID:.privateState) else {desktopResult(id,["error":"Klavye kaynağı oluşturulamadı."]);return}
            for scalar in text.unicodeScalars {
                let chars=Array(String(scalar).utf16)
                for down in [true,false] {
                    guard let event=CGEvent(keyboardEventSource:source,virtualKey:0,keyDown:down) else {desktopResult(id,["error":"Metin gönderimi kesildi; tekrar yazmadan önce ekranı kontrol et."]);return}
                    event.flags=[]
                    chars.withUnsafeBufferPointer {event.keyboardSetUnicodeString(stringLength:chars.count,unicodeString:$0.baseAddress!)}
                    event.post(tap:.cghidEventTap)
                }
            }
        } else if tool=="desktop_key" {
            guard let key=args["key"] as? String else{return}
            let keys:[String:CGKeyCode]=["enter":36,"escape":53,"tab":48,"backspace":51,"left":123,"right":124,"up":126,"down":125,"cmd+a":0,"cmd+l":37,"cmd+s":1,"cmd+z":6,"cmd+n":45]
            guard let code=keys[key] else {desktopResult(id,["error":"Kısayol izinli değil."]);return}
            for down in [true,false] {let event=CGEvent(keyboardEventSource:nil,virtualKey:code,keyDown:down);event?.flags = down && key.hasPrefix("cmd+") ? .maskCommand : [];event?.post(tap:.cghidEventTap)}
        } else if tool=="desktop_scroll" {
            guard let steps=args["steps"] as? Int,abs(steps)<=8 else {desktopResult(id,["error":"Kaydırma sınırı aşıldı."]);return}
            CGEvent(scrollWheelEvent2Source:nil,units:.line,wheelCount:1,wheel1:Int32(steps),wheel2:0,wheel3:0)?.post(tap:.cghidEventTap)
        } else {desktopResult(id,["error":"Masaüstü aracı tanınmadı."]);return}
        desktopResult(id,["acted":true,"application":front])
    }
    // Best effort: editors name their terminal input in the accessibility tree; never type or press Enter there.
    func focusedLooksLikeTerminal() -> Bool {
        var focused:CFTypeRef?
        guard AXUIElementCopyAttributeValue(AXUIElementCreateSystemWide(),kAXFocusedUIElementAttribute as CFString,&focused) == .success,let focused=focused,CFGetTypeID(focused)==AXUIElementGetTypeID() else{return false}
        return elementLooksLikeTerminal(focused as! AXUIElement)
    }
    // The element itself and its two nearest ancestors: editors label the terminal input or its panel.
    func elementLooksLikeTerminal(_ element:AXUIElement) -> Bool {
        var node:AXUIElement?=element
        for _ in 0..<3 {
            guard let current=node else{break}
            var seen=""
            for key in [kAXDescriptionAttribute,kAXTitleAttribute,kAXHelpAttribute,kAXPlaceholderValueAttribute,kAXRoleDescriptionAttribute,kAXIdentifierAttribute] {
                var value:CFTypeRef?
                if AXUIElementCopyAttributeValue(current,key as CFString,&value) == .success,let text=value as? String {seen+=" "+text.lowercased()}
            }
            if seen.contains("terminal") || seen.contains("xterm") {return true}
            node=axElement(current,kAXParentAttribute)
        }
        return false
    }
    // MARK: Background control. The app is never brought to the front: the agent sees only its window and acts through accessibility (events go straight to that process, never to Berke's mouse or keyboard).
    func runningApp(_ bundle:String) -> NSRunningApplication? {
        NSRunningApplication.runningApplications(withBundleIdentifier:bundle).first(where:{!$0.isTerminated})
    }
    func axString(_ element:AXUIElement,_ key:String) -> String? {
        var value:CFTypeRef?
        guard AXUIElementCopyAttributeValue(element,key as CFString,&value) == .success else{return nil}
        return value as? String
    }
    func axElement(_ element:AXUIElement,_ key:String) -> AXUIElement? {
        var value:CFTypeRef?
        guard AXUIElementCopyAttributeValue(element,key as CFString,&value) == .success,let value=value,CFGetTypeID(value)==AXUIElementGetTypeID() else{return nil}
        return (value as! AXUIElement)
    }
    func axActions(_ element:AXUIElement) -> [String] {
        var names:CFArray?
        guard AXUIElementCopyActionNames(element,&names) == .success,let list=names as? [String] else{return []}
        return list
    }
    func insertText(_ element:AXUIElement,_ text:String) -> Bool {
        var settable:DarwinBoolean=false
        guard AXUIElementIsAttributeSettable(element,kAXSelectedTextAttribute as CFString,&settable) == .success,settable.boolValue else{return false}
        return AXUIElementSetAttributeValue(element,kAXSelectedTextAttribute as CFString,text as CFString) == .success
    }
    func selectedRange(_ element:AXUIElement) -> CFRange? {
        var value:CFTypeRef?
        guard AXUIElementCopyAttributeValue(element,kAXSelectedTextRangeAttribute as CFString,&value) == .success,let value=value,CFGetTypeID(value)==AXValueGetTypeID() else{return nil}
        var range=CFRange()
        return AXValueGetValue(value as! AXValue,.cfRange,&range) ? range : nil
    }
    func setSelectedRange(_ element:AXUIElement,_ range:CFRange) -> Bool {
        var copy=range
        guard let value=AXValueCreate(.cfRange,&copy) else{return false}
        return AXUIElementSetAttributeValue(element,kAXSelectedTextRangeAttribute as CFString,value) == .success
    }
    func deleteBackward(_ element:AXUIElement) -> Bool {
        guard let range=selectedRange(element) else{return false}
        if range.length>0 {return insertText(element,"")}
        guard range.location>0,setSelectedRange(element,CFRange(location:range.location-1,length:1)) else{return false}
        return insertText(element,"")
    }
    func moveCaret(_ element:AXUIElement,_ delta:Int) -> Bool {
        guard let range=selectedRange(element) else{return false}
        let location = delta<0 ? (range.length>0 ? range.location : max(0,range.location-1)) : range.location+range.length+(range.length>0 ? 0 : 1)
        return setSelectedRange(element,CFRange(location:location,length:0))
    }
    // Put the caret where the agent clicked inside a text view (best effort; the old selection stays when the app cannot say).
    func placeCaret(_ element:AXUIElement,at point:CGPoint) {
        var copy=point
        guard let parameter=AXValueCreate(.cgPoint,&copy) else{return}
        var value:CFTypeRef?
        guard AXUIElementCopyParameterizedAttributeValue(element,kAXRangeForPositionParameterizedAttribute as CFString,parameter,&value) == .success,let value=value,CFGetTypeID(value)==AXValueGetTypeID() else{return}
        var range=CFRange()
        guard AXValueGetValue(value as! AXValue,.cfRange,&range) else{return}
        _=setSelectedRange(element,CFRange(location:range.location,length:0))
    }
    // The menu item whose shortcut is Cmd+<letter>: pressing it works without the app being in front.
    func menuItem(_ app:AXUIElement,cmdChar:String) -> AXUIElement? {
        guard let bar=axElement(app,kAXMenuBarAttribute) else{return nil}
        func scan(_ node:AXUIElement,_ depth:Int) -> AXUIElement? {
            if depth>3 {return nil}
            var value:CFTypeRef?
            guard AXUIElementCopyAttributeValue(node,kAXChildrenAttribute as CFString,&value) == .success,let list=value as? [AXUIElement] else{return nil}
            for item in list {
                if let character=axString(item,"AXMenuItemCmdChar"),character.lowercased()==cmdChar {
                    var mods:CFTypeRef?,enabled:CFTypeRef?
                    let modifiers=(AXUIElementCopyAttributeValue(item,"AXMenuItemCmdModifiers" as CFString,&mods) == .success ? (mods as? Int) : nil) ?? 0
                    let isOn=(AXUIElementCopyAttributeValue(item,kAXEnabledAttribute as CFString,&enabled) == .success ? (enabled as? Bool) : nil) ?? true
                    if modifiers==0 && isOn {return item}
                }
                if let found=scan(item,depth+1) {return found}
            }
            return nil
        }
        return scan(bar,0)
    }
    func postMouseClick(_ t:BackgroundTarget,at point:CGPoint) {
        guard let source=CGEventSource(stateID:.privateState) else{return}
        for type in [CGEventType.leftMouseDown,CGEventType.leftMouseUp] {
            guard let event=CGEvent(mouseEventSource:source,mouseType:type,mouseCursorPosition:point,mouseButton:.left) else{continue}
            event.setIntegerValueField(.mouseEventClickState,value:1)
            // fields 91/92: tell the app which of its windows the click belongs to, so it works while another app is in front
            for raw:UInt32 in [91,92] {if let field=CGEventField(rawValue:raw) {event.setIntegerValueField(field,value:Int64(t.windowID))}}
            event.postToPid(t.pid)
        }
    }
    func postKey(_ pid:pid_t,code:CGKeyCode,flags:CGEventFlags) {
        guard let source=CGEventSource(stateID:.privateState) else{return}
        for down in [true,false] {
            let event=CGEvent(keyboardEventSource:source,virtualKey:code,keyDown:down)
            event?.flags=flags
            event?.postToPid(pid)
        }
    }
    func postText(_ pid:pid_t,_ text:String) -> Bool {
        guard let source=CGEventSource(stateID:.privateState) else{return false}
        for scalar in text.unicodeScalars {
            let chars=Array(String(scalar).utf16)
            for down in [true,false] {
                guard let event=CGEvent(keyboardEventSource:source,virtualKey:0,keyDown:down) else{return false}
                event.flags=[]
                chars.withUnsafeBufferPointer {event.keyboardSetUnicodeString(stringLength:chars.count,unicodeString:$0.baseAddress!)}
                event.postToPid(pid)
            }
        }
        return true
    }
    func axFrame(_ element:AXUIElement) -> CGRect? {
        var position:CFTypeRef?,size:CFTypeRef?
        var origin=CGPoint.zero,extent=CGSize.zero
        guard AXUIElementCopyAttributeValue(element,kAXPositionAttribute as CFString,&position) == .success,let position=position,CFGetTypeID(position)==AXValueGetTypeID(),AXValueGetValue(position as! AXValue,.cgPoint,&origin),
              AXUIElementCopyAttributeValue(element,kAXSizeAttribute as CFString,&size) == .success,let size=size,CFGetTypeID(size)==AXValueGetTypeID(),AXValueGetValue(size as! AXValue,.cgSize,&extent) else{return nil}
        return CGRect(origin:origin,size:extent)
    }
    // Chromium/Electron editors keep their real input element next to the visible lines: look under the clicked spot for a text element whose frame contains it.
    func textElement(under node:AXUIElement,at point:CGPoint,depth:Int,budget:inout Int) -> AXUIElement? {
        if budget<=0 || depth<0 {return nil}
        budget-=1
        if backgroundTextRoles.contains(axString(node,kAXRoleAttribute) ?? ""),let frame=axFrame(node),frame.insetBy(dx:-2,dy:-2).contains(point) {return node}
        var value:CFTypeRef?
        guard AXUIElementCopyAttributeValue(node,kAXChildrenAttribute as CFString,&value) == .success,let children=value as? [AXUIElement] else{return nil}
        for child in children.prefix(40) {if let found=textElement(under:child,at:point,depth:depth-1,budget:&budget) {return found}}
        return nil
    }
    // Chromium/Electron expose the page's CSS classes; code editors (Monaco) are recognised by them.
    func domClasses(_ element:AXUIElement) -> [String] {
        var value:CFTypeRef?
        guard AXUIElementCopyAttributeValue(element,"AXDOMClassList" as CFString,&value) == .success,let list=value as? [String] else{return []}
        return list
    }
    // First text element anywhere under the node (the editor's hidden input sits beside the painted lines, not under the clicked line).
    func anyTextElement(under node:AXUIElement,depth:Int,budget:inout Int) -> AXUIElement? {
        if budget<=0 || depth<0 {return nil}
        budget-=1
        if backgroundTextRoles.contains(axString(node,kAXRoleAttribute) ?? "") {return node}
        var value:CFTypeRef?
        guard AXUIElementCopyAttributeValue(node,kAXChildrenAttribute as CFString,&value) == .success,let children=value as? [AXUIElement] else{return nil}
        for child in children.prefix(60) {if let found=anyTextElement(under:child,depth:depth-1,budget:&budget) {return found}}
        return nil
    }
    func axLabel(_ element:AXUIElement) -> String {
        let role=(axString(element,kAXRoleAttribute) ?? "?").replacingOccurrences(of:"AX",with:"")
        if let first=domClasses(element).first {return role+"."+first}
        return role
    }
    // Compact "role.class" listing of what sits under a node, so a failed click can say what the editor really exposes.
    func treeSketch(_ node:AXUIElement,depth:Int,budget:inout Int) -> String {
        if budget<=0 {return ""}
        budget-=1
        let label=axLabel(node)
        guard depth>0 else{return label}
        var value:CFTypeRef?
        guard AXUIElementCopyAttributeValue(node,kAXChildrenAttribute as CFString,&value) == .success,let children=value as? [AXUIElement],!children.isEmpty else{return label}
        return label+"("+children.prefix(8).map{treeSketch($0,depth:depth-1,budget:&budget)}.filter{!$0.isEmpty}.joined(separator:",")+")"
    }
    // Chromium apps in the background report no app-level focus: the text element the last click focused is the typing target.
    func textTarget(_ app:AXUIElement,pid:pid_t) -> AXUIElement? {
        if let remembered=bgText,remembered.pid==pid,axString(remembered.element,kAXRoleAttribute) != nil {return remembered.element}
        return axElement(app,kAXFocusedUIElementAttribute)
    }
    // Some text elements refuse AXSelectedText but accept a new AXValue: write the old text with the new text spliced in at the caret.
    func replaceValue(_ element:AXUIElement,inserting text:String) -> Bool {
        var settable:DarwinBoolean=false
        guard AXUIElementIsAttributeSettable(element,kAXValueAttribute as CFString,&settable) == .success,settable.boolValue else{return false}
        var current:CFTypeRef?
        var old=""
        if AXUIElementCopyAttributeValue(element,kAXValueAttribute as CFString,&current) == .success {
            guard let string=current as? String,string.utf16.count<200_000 else{return false}
            old=string
        }
        let units=Array(old.utf16)
        let range=selectedRange(element) ?? CFRange(location:units.count,length:0)
        let start=max(0,min(range.location,units.count)),end=max(start,min(range.location+range.length,units.count))
        let merged=String(decoding:units[0..<start],as:UTF16.self)+text+String(decoding:units[end...],as:UTF16.self)
        guard AXUIElementSetAttributeValue(element,kAXValueAttribute as CFString,merged as CFString) == .success else{return false}
        _=setSelectedRange(element,CFRange(location:start+text.utf16.count,length:0))
        return true
    }
    // Click by meaning, not by moving Berke's mouse: focus the text field under the point, else press the control or select the row, and only if the app exposes nothing there post a click to that process. `path` lists the accessibility roles under the point (innermost first) so a failed click can be diagnosed.
    func backgroundClick(_ t:BackgroundTarget,at point:CGPoint,app:AXUIElement) -> (method:String,path:String) {
        bgText=nil
        var chain:[AXUIElement]=[]
        var hit:AXUIElement?
        if AXUIElementCopyElementAtPosition(app,Float(point.x),Float(point.y),&hit) == .success,let start=hit {
            var node:AXUIElement?=start
            while let current=node,chain.count<9 {chain.append(current);node=axElement(current,kAXParentAttribute)}
        }
        var path=chain.prefix(9).map{axLabel($0)}.joined(separator:"<")
        func focus(_ element:AXUIElement) -> (method:String,path:String) {
            AXUIElementSetAttributeValue(element,kAXFocusedAttribute as CFString,kCFBooleanTrue)
            placeCaret(element,at:point)
            bgText=(pid:t.pid,element:element)
            return ("ax-focus",path)
        }
        for current in chain where backgroundTextRoles.contains(axString(current,kAXRoleAttribute) ?? "") {return focus(current)}
        var budget=150
        for current in chain.prefix(4) {if let found=textElement(under:current,at:point,depth:3,budget:&budget) {return focus(found)}}
        // Monaco (VS Code, Antigravity): the editor's real input element is a sibling of the painted lines, inside the editor container.
        if let editor=chain.first(where:{domClasses($0).contains("monaco-editor")}) {
            var wide=700
            if let found=anyTextElement(under:editor,depth:8,budget:&wide) {return focus(found)}
            var sketchBudget=45
            path+=" | editor:"+treeSketch(editor,depth:4,budget:&sketchBudget)
        }
        for current in chain.prefix(7) {
            let role=axString(current,kAXRoleAttribute) ?? ""
            if axActions(current).contains(kAXPressAction),AXUIElementPerformAction(current,kAXPressAction as CFString) == .success {return ("ax-press",path)}
            if ["AXRow","AXOutlineRow"].contains(role) {
                var settable:DarwinBoolean=false
                if AXUIElementIsAttributeSettable(current,kAXSelectedAttribute as CFString,&settable) == .success,settable.boolValue,AXUIElementSetAttributeValue(current,kAXSelectedAttribute as CFString,kCFBooleanTrue) == .success {return ("ax-select",path)}
            }
        }
        postMouseClick(t,at:point)
        return ("pid-click",path)
    }
    func backgroundKey(_ t:BackgroundTarget,key:String,app:AXUIElement) -> (ok:Bool,method:String) {
        let codes:[String:CGKeyCode]=["enter":36,"escape":53,"tab":48,"backspace":51,"left":123,"right":124,"up":126,"down":125,"cmd+a":0,"cmd+l":37,"cmd+s":1,"cmd+z":6,"cmd+n":45]
        guard let code=codes[key] else{return (false,"Kısayol izinli değil.")}
        if key=="tab" {bgText=nil}
        if key.hasPrefix("cmd+"),let item=menuItem(app,cmdChar:String(key.dropFirst(4))),AXUIElementPerformAction(item,kAXPressAction as CFString) == .success {return (true,"ax-menu")}
        if let focused=textTarget(app,pid:t.pid) {
            switch key {
            case "enter":
                if axString(focused,kAXRoleAttribute) == "AXTextArea",insertText(focused,"\n") {return (true,"ax-insert")}
                if axActions(focused).contains(kAXConfirmAction),AXUIElementPerformAction(focused,kAXConfirmAction as CFString) == .success {return (true,"ax-confirm")}
            case "escape":
                if axActions(focused).contains(kAXCancelAction),AXUIElementPerformAction(focused,kAXCancelAction as CFString) == .success {return (true,"ax-cancel")}
            case "backspace":
                if deleteBackward(focused) {return (true,"ax-delete")}
            case "left","right":
                if moveCaret(focused,key=="left" ? -1 : 1) {return (true,"ax-caret")}
            default:
                break
            }
        }
        postKey(t.pid,code:code,flags:key.hasPrefix("cmd+") ? .maskCommand : [])
        return (true,"pid-key")
    }
    func backgroundScroll(_ t:BackgroundTarget,steps:Int,app:AXUIElement) -> String {
        let centre=CGPoint(x:t.frame.midX,y:t.frame.midY)
        var hit:AXUIElement?
        if AXUIElementCopyElementAtPosition(app,Float(centre.x),Float(centre.y),&hit) == .success {
            var node=hit;var depth=0
            while let current=node,depth<12 {
                if axString(current,kAXRoleAttribute) == "AXScrollArea",let bar=axElement(current,kAXVerticalScrollBarAttribute) {
                    var value:CFTypeRef?
                    if AXUIElementCopyAttributeValue(bar,kAXValueAttribute as CFString,&value) == .success,let position=value as? Double {
                        let next=min(1.0,max(0.0,position-Double(steps)*0.06))
                        if AXUIElementSetAttributeValue(bar,kAXValueAttribute as CFString,NSNumber(value:next)) == .success {return "ax-scrollbar"}
                    }
                }
                node=axElement(current,kAXParentAttribute);depth+=1
            }
        }
        if let event=CGEvent(scrollWheelEvent2Source:nil,units:.line,wheelCount:1,wheel1:Int32(steps),wheel2:0,wheel3:0) {event.location=centre;event.postToPid(t.pid)}
        return "pid-scroll"
    }
    func backgroundPoint(_ args:[String:Any],_ t:BackgroundTarget) -> (screen:CGPoint,image:CGPoint)? {
        guard let px=args["x"] as? Double,let py=args["y"] as? Double,px.isFinite,py.isFinite,px>=0,py>=0 else{return nil}
        guard px<=Double(t.frame.width)*t.scale,py<=Double(t.frame.height)*t.scale else{return nil}
        return (CGPoint(x:t.frame.minX+CGFloat(px/t.scale),y:t.frame.minY+CGFloat(py/t.scale)),CGPoint(x:px,y:py))
    }
    func performBackgroundAction(_ id:String,tool:String,args:[String:Any],bundle:String,editorOK:Bool) {
        let blocked=["com.apple.Terminal","com.googlecode.iterm2","com.apple.systempreferences","com.apple.SecurityAgent","com.apple.loginwindow","com.apple.keychainaccess",Bundle.main.bundleIdentifier ?? "local.berke.jarvis"]
        guard !blocked.contains(bundle) else {desktopResult(id,["error":"Bu sistem/terminal/JARVIS penceresinde otomatik eylem kapalı."]);return}
        guard let t=bgTarget,t.bundle==bundle,let running=runningApp(bundle),running.processIdentifier==t.pid else {desktopResult(id,["error":"Hedef pencere gözlenmedi veya uygulama kapandı. Önce ekranı gözlemle."]);return}
        let app=AXUIElementCreateApplication(t.pid)
        AXUIElementSetMessagingTimeout(app,2)
        // Code editors: typing or shortcuts could run commands in their terminal outside the project sandbox, so JARVIS sends editor_ok only after Berke approved that very action.
        let editors=["com.microsoft.VSCode","com.google.antigravity","com.apple.dt.Xcode"]
        if (tool=="desktop_type" || tool=="desktop_key") && editors.contains(bundle) {
            if !editorOK {desktopResult(id,["error":"Kod düzenleyiciye yazmak için önce ekranı gözlemle; sonra yaz."]);return}
            if let focused=textTarget(app,pid:t.pid),elementLooksLikeTerminal(focused) {desktopResult(id,["error":"İmleç editörün terminal panelinde. Terminale yazmak kapalı; önce editörün metin alanına tıkla."]);return}
        }
        switch tool {
        case "desktop_move","desktop_click":
            guard let point=backgroundPoint(args,t) else {desktopResult(id,["error":"Koordinat pencerenin dışında."]);return}
            let isClick = tool=="desktop_click"
            let inFront=NSWorkspace.shared.frontmostApplication?.processIdentifier==t.pid
            overlay.movePointerInTarget(screenPoint:point.screen,imagePoint:point.image,onScreen:inFront,click:isClick){[self] in
                if !isClick {desktopResult(id,["acted":true,"application":t.name,"method":"virtual-pointer","pointer":["x":Double(point.image.x),"y":Double(point.image.y)]]);return}
                let how=backgroundClick(t,at:point.screen,app:app)
                desktopResult(id,["acted":true,"application":t.name,"method":how.method,"hit_path":how.path,"needs_visual_verification":true])
            }
        case "desktop_type":
            guard let text=args["text"] as? String,text.count<=2000,!text.isEmpty else {desktopResult(id,["error":"Metin boş veya sınırı aşıyor."]);return}
            guard let focused=textTarget(app,pid:t.pid) else {desktopResult(id,["error":"Hedef uygulamada odaklı bir metin alanı yok. Önce metin alanına tıkla, ekranı gözlemle, sonra yaz."]);return}
            if axString(focused,kAXSubroleAttribute) == "AXSecureTextField" {desktopResult(id,["error":"Parola/güvenli alana yazma engellendi."]);return}
            let role=axString(focused,kAXRoleAttribute) ?? ""
            guard backgroundTextRoles.contains(role) else {desktopResult(id,["error":"Bir metin alanı odakta değil. Metin alanına tıkla, ekranı tekrar gözlemle ve sonra yaz.","focused_role":role]);return}
            if insertText(focused,text) {desktopResult(id,["acted":true,"application":t.name,"method":"accessibility-insert","needs_visual_verification":true]);return}
            if replaceValue(focused,inserting:text) {desktopResult(id,["acted":true,"application":t.name,"method":"accessibility-value","needs_visual_verification":true]);return}
            // Last resort: key events posted to that process only. Some apps ignore them while not in front, so the agent must check the picture.
            guard postText(t.pid,text) else {desktopResult(id,["error":"Klavye kaynağı oluşturulamadı."]);return}
            desktopResult(id,["acted":true,"application":t.name,"method":"pid-keys","needs_visual_verification":true,"note":"Arka planda tuş olayı gönderildi; uygulama yok saymış olabilir. Ekranı gözlemleyip yazının göründüğünü doğrula; görünmediyse Berke’ye öne almadan yazamadığını söyle."])
        case "desktop_key":
            guard let key=args["key"] as? String else {desktopResult(id,["error":"Kısayol belirtilmedi."]);return}
            let result=backgroundKey(t,key:key,app:app)
            desktopResult(id,result.ok ? ["acted":true,"application":t.name,"method":result.method,"needs_visual_verification":true] : ["error":result.method])
        case "desktop_scroll":
            guard let steps=args["steps"] as? Int,abs(steps)<=8 else {desktopResult(id,["error":"Kaydırma sınırı aşıldı."]);return}
            desktopResult(id,["acted":true,"application":t.name,"method":backgroundScroll(t,steps:steps,app:app),"needs_visual_verification":true])
        default:
            desktopResult(id,["error":"Masaüstü aracı tanınmadı."])
        }
    }
    // The window the app itself treats as its current one (a new document or window the agent just made), matched to its capture handle by position and size. Without this the agent would keep looking at the app's biggest old window.
    func preferredWindow(_ windows:[SCWindow],pid:pid_t) -> SCWindow? {
        let app=AXUIElementCreateApplication(pid)
        for key in [kAXFocusedWindowAttribute,kAXMainWindowAttribute] {
            guard let element=axElement(app,key) else{continue}
            var position:CFTypeRef?,size:CFTypeRef?
            var origin=CGPoint.zero,extent=CGSize.zero
            guard AXUIElementCopyAttributeValue(element,kAXPositionAttribute as CFString,&position) == .success,let position=position,CFGetTypeID(position)==AXValueGetTypeID(),AXValueGetValue(position as! AXValue,.cgPoint,&origin),
                  AXUIElementCopyAttributeValue(element,kAXSizeAttribute as CFString,&size) == .success,let size=size,CFGetTypeID(size)==AXValueGetTypeID(),AXValueGetValue(size as! AXValue,.cgSize,&extent) else{continue}
            if let match=windows.first(where:{abs($0.frame.minX-origin.x)<3 && abs($0.frame.minY-origin.y)<3 && abs($0.frame.width-extent.width)<3 && abs($0.frame.height-extent.height)<3}) {return match}
        }
        return nil
    }
    func captureDesktopTarget(_ id:String,bundle:String) {
        guard CGPreflightScreenCaptureAccess() else {desktopResult(id,["error":"macOS Ekran Kaydı izni gerekli. Görüntü gönderilmedi."]);return}
        guard bundle != (Bundle.main.bundleIdentifier ?? "local.berke.jarvis") else {desktopResult(id,["error":"JARVIS’in kendi penceresi gözlenmez."]);return}
        guard let running=runningApp(bundle) else {desktopResult(id,["error":"Uygulama henüz açık değil. Birkaç saniye bekleyip yeniden gözlemle; açılmadıysa desktop_open_app kullan."]);return}
        let pid=running.processIdentifier,name=running.localizedName ?? bundle
        // Chromium/Electron apps (VS Code, Chrome) build their accessibility tree only when asked.
        if ["com.microsoft.VSCode","com.google.antigravity","com.google.Chrome"].contains(bundle) {
            AXUIElementSetAttributeValue(AXUIElementCreateApplication(pid),"AXManualAccessibility" as CFString,kCFBooleanTrue)
        }
        SCShareableContent.getExcludingDesktopWindows(true,onScreenWindowsOnly:false){[weak self] content,error in
            guard let self=self else{return}
            let windows=(content?.windows ?? []).filter{$0.owningApplication?.processID==pid && $0.windowLayer==0 && $0.frame.width>=160 && $0.frame.height>=100}
            func rank(_ w:SCWindow) -> Double {(w.isOnScreen ? 1e9 : 0)+Double(w.frame.width*w.frame.height)}
            guard let window=(self.preferredWindow(windows,pid:pid) ?? windows.max(by:{rank($0)<rank($1)})) else {
                // A freshly started app may have no window yet (document apps keep their open panel hidden while in the background). That is still a valid look: the agent can create one with a menu shortcut such as cmd+n and look again.
                DispatchQueue.main.async{
                    self.bgTarget=(pid:pid,bundle:bundle,name:name,windowID:0,frame:.zero,scale:1)
                    self.overlay.hideAgentScreen()
                    self.desktopResult(id,["application":name,"bundle":bundle,"background":true,"window_visible":false,"no_window":true,"note":"Uygulamanın görünür penceresi yok. cmd+n gibi bir menü kısayoluyla yeni belge/pencere aç, sonra yeniden gözlemle."])
                }
                return
            }
            let ratio=min(1.0,1200.0/Double(window.frame.width))
            let config=SCStreamConfiguration()
            config.width=max(1,Int((Double(window.frame.width)*ratio).rounded()));config.height=max(1,Int((Double(window.frame.height)*ratio).rounded()))
            config.showsCursor=false;config.ignoreShadowsSingleWindow=true
            SCScreenshotManager.captureImage(contentFilter:SCContentFilter(desktopIndependentWindow:window),configuration:config){image,error in
                DispatchQueue.main.async {
                    guard let image=image,let data=NSBitmapImageRep(cgImage:image).representation(using:.jpeg,properties:[.compressionFactor:0.65]) else {self.desktopResult(id,["error":"Pencere görüntüsü alınamadı: "+(error?.localizedDescription ?? "bilinmeyen hata")]);return}
                    self.bgTarget=(pid:pid,bundle:bundle,name:name,windowID:window.windowID,frame:window.frame,scale:Double(image.width)/Double(window.frame.width))
                    if NSWorkspace.shared.frontmostApplication?.processIdentifier==pid {self.overlay.hideAgentScreen()} else {self.overlay.showAgentScreen(image:image,label:self.overlay.owner+" · "+name)}
                    self.desktopResult(id,["image":"data:image/jpeg;base64,"+data.base64EncodedString(),"width":image.width,"height":image.height,"application":name,"bundle":bundle,"background":true,"window_visible":window.isOnScreen,"window_title":window.title ?? "","other_windows":max(0,windows.count-1)])
                }
            }
        }
    }
    func captureDesktopForAgent(_ id:String) {
        guard CGPreflightScreenCaptureAccess(),let screen=NSScreen.screens.first else {desktopResult(id,["error":"macOS Ekran Kaydı izni gerekli. Görüntü gönderilmedi."]);return}
        let width=Int(screen.frame.width),height=Int(screen.frame.height)
        // A smaller picture costs the model fewer tokens; the agent's x/y are in this smaller picture and are scaled back when it clicks.
        let scale=min(1.0,1200.0/Double(width)),outWidth=Int((Double(width)*scale).rounded()),outHeight=Int((Double(height)*scale).rounded())
        let hidden=overlay.windowNumbers
        SCShareableContent.getExcludingDesktopWindows(false,onScreenWindowsOnly:true){[weak self] content,error in
            guard let self=self,let display=content?.displays.first(where:{$0.displayID==CGMainDisplayID()}) else {DispatchQueue.main.async{self?.desktopResult(id,["error":"Ekran içeriğine erişilemedi."])};return}
            let skip=(content?.windows ?? []).filter{hidden.contains($0.windowID)}
            let filter=SCContentFilter(display:display,excludingWindows:skip),config=SCStreamConfiguration();config.width=outWidth;config.height=outHeight;config.showsCursor=true
            SCScreenshotManager.captureImage(contentFilter:filter,configuration:config){image,error in
                DispatchQueue.main.async {
                    guard let image=image,let data=NSBitmapImageRep(cgImage:image).representation(using:.jpeg,properties:[.compressionFactor:0.65]) else {self.desktopResult(id,["error":"Ekran görüntüsü alınamadı."]);return}
                    self.captureScale=scale
                    self.desktopResult(id,["image":"data:image/jpeg;base64,"+data.base64EncodedString(),"width":outWidth,"height":outHeight,"application":NSWorkspace.shared.frontmostApplication?.localizedName ?? "unknown","bundle":NSWorkspace.shared.frontmostApplication?.bundleIdentifier ?? ""])
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
