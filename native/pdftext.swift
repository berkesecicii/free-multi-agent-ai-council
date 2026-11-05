import Foundation
import PDFKit
import Vision
import AppKit
if CommandLine.arguments.count != 3 {exit(2)}
guard let document=PDFDocument(url:URL(fileURLWithPath:CommandLine.arguments[1])) , !document.isLocked else {exit(3)}
var output=""
for i in 0..<min(document.pageCount,100) {
    guard let page=document.page(at:i) else {continue}
    var text=page.string ?? ""
    if text.trimmingCharacters(in:.whitespacesAndNewlines).count < 20 {
        let image=page.thumbnail(of:NSSize(width:1600,height:2000),for:.mediaBox)
        var rect=CGRect(origin:.zero,size:image.size)
        if let cg=image.cgImage(forProposedRect:&rect,context:nil,hints:nil) {
            let request=VNRecognizeTextRequest();request.recognitionLevel = .accurate
            if #available(macOS 13.0,*) {request.automaticallyDetectsLanguage=true}
            try? VNImageRequestHandler(cgImage:cg).perform([request])
            text=(request.results ?? []).compactMap{$0.topCandidates(1).first?.string}.joined(separator:"\n")
        }
    }
    output += "\n[Sayfa \(i+1)]\n"+text
    if output.count>=200000 {break}
}
do {try String(output.prefix(200000)).write(toFile:CommandLine.arguments[2],atomically:true,encoding:.utf8)} catch {exit(4)}
