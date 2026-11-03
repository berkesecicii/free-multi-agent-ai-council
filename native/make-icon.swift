import AppKit
let destination=CommandLine.arguments[1]
let size=NSSize(width:1024,height:1024)
let image=NSImage(size:size)
image.lockFocus()
NSColor(calibratedRed:0.035,green:0.065,blue:0.09,alpha:1).setFill()
NSBezierPath(roundedRect:NSRect(origin:.zero,size:size),xRadius:220,yRadius:220).fill()
let cyan=NSColor(calibratedRed:0.4,green:0.88,blue:0.97,alpha:1)
for (radius,width,alpha) in [(370.0,2.0,0.5),(340.0,20.0,0.8),(295.0,3.0,0.6),(255.0,8.0,0.9)] {
    cyan.withAlphaComponent(alpha).setStroke()
    let path=NSBezierPath();path.lineWidth=width
    path.appendArc(withCenter:NSPoint(x:512,y:512),radius:radius,startAngle:CGFloat(radius==340 ? 35 : 0),endAngle:CGFloat(radius==340 ? 315 : 360));path.stroke()
}
for index in 0..<36 {
    let angle=Double(index)*Double.pi/18
    let start=NSPoint(x:512+cos(angle)*385,y:512+sin(angle)*385)
    let end=NSPoint(x:512+cos(angle)*Double(index%3==0 ? 407 : 396),y:512+sin(angle)*Double(index%3==0 ? 407 : 396))
    let tick=NSBezierPath();tick.move(to:start);tick.line(to:end);tick.lineWidth=3;cyan.withAlphaComponent(0.65).setStroke();tick.stroke()
}
let attrs:[NSAttributedString.Key:Any]=[.font:NSFont.systemFont(ofSize:330,weight:.ultraLight),.foregroundColor:cyan]
let text="J" as NSString;let t=text.size(withAttributes:attrs);text.draw(at:NSPoint(x:(1024-t.width)/2,y:(1024-t.height)/2+18),withAttributes:attrs)
let label="J.A.R.V.I.S." as NSString;let small:[NSAttributedString.Key:Any]=[.font:NSFont.monospacedSystemFont(ofSize:29,weight:.medium),.foregroundColor:cyan.withAlphaComponent(0.7),.kern:7];let l=label.size(withAttributes:small);label.draw(at:NSPoint(x:(1024-l.width)/2,y:333),withAttributes:small)
image.unlockFocus()
let rep=NSBitmapImageRep(data:image.tiffRepresentation!)!
try rep.representation(using:.png,properties:[:])!.write(to:URL(fileURLWithPath:destination))
