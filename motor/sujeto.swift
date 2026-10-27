// El recorte fino del Mac: el «levantar sujeto» del sistema (el de Fotos, VNGenerateForegroundInstanceMaskRequest, macOS
// 14 o más nuevo). Sale al tamaño del cuadro y con el borde fino (orejas, pelo, dedos). Y, al lado, el recorte de personas
// del sistema (VNGeneratePersonSegmentationRequest), más blando pero que casi nunca pierde una oreja. Lo usa `persona.py`;
// en Windows, en Linux o si esto falla, el motor usa su recorte de siempre.
//
// Lo compila la instalación (`instalar.sh`) en cada Mac:
//     swiftc -O motor/sujeto.swift -o motor/bin/sujeto
//
// Uso:
//     sujeto <ancho> <alto>    lee cuadros RGB (ancho × alto × 3 bytes) por la entrada estándar y, por cada uno, escribe
//                              1 byte (1 = bien, 0 = falló), el sujeto y la persona en gris (ancho × alto bytes cada uno,
//                              255 = dentro)
//     sujeto --prueba          comprueba que el recorte funciona en este Mac (sale con 0 si sí)
//
// «Sujeto» es lo que el Mac ve en primer plano: puede llevarse una silla o una mesa pegadas a la persona. Por eso el motor
// lo cruza después con su recorte de personas.
import CoreImage
import CoreVideo
import Foundation
import Vision

func salir(_ texto: String, _ codigo: Int32) -> Never {
  FileHandle.standardError.write((texto + "\n").data(using: .utf8)!)
  exit(codigo)
}

guard #available(macOS 14.0, *) else { salir("sujeto: hace falta macOS 14 o más nuevo", 3) }

let contexto = CIContext(options: [.workingColorSpace: NSNull()])

/// El sujeto (`gris`) y la persona (`persona`) del cuadro (BGRA), o el error.
@available(macOS 14.0, *)
func recortar(_ imagen: CVPixelBuffer, _ ancho: Int, _ alto: Int, _ gris: inout [UInt8], _ persona: inout [UInt8]) throws {
  let peticion = VNGenerateForegroundInstanceMaskRequest()
  let dePersonas = VNGeneratePersonSegmentationRequest()
  dePersonas.qualityLevel = .accurate
  dePersonas.outputPixelFormat = kCVPixelFormatType_OneComponent8
  let manejador = VNImageRequestHandler(cvPixelBuffer: imagen, orientation: .up)
  try manejador.perform([peticion, dePersonas])
  // la persona sale más pequeña que el cuadro: se escala con Lanczos
  for i in 0..<persona.count { persona[i] = 0 }
  if let p = dePersonas.results?.first?.pixelBuffer {
    let m = CIImage(cvPixelBuffer: p)
    let escala = CIFilter(name: "CILanczosScaleTransform")!
    escala.setValue(m, forKey: kCIInputImageKey)
    escala.setValue(CGFloat(alto) / m.extent.height, forKey: kCIInputScaleKey)
    escala.setValue((CGFloat(ancho) / m.extent.width) / (CGFloat(alto) / m.extent.height), forKey: kCIInputAspectRatioKey)
    persona.withUnsafeMutableBytes { b in
      contexto.render(escala.outputImage!, toBitmap: b.baseAddress!, rowBytes: ancho,
                      bounds: CGRect(x: 0, y: 0, width: ancho, height: alto), format: .L8, colorSpace: nil)
    }
  }
  for i in 0..<gris.count { gris[i] = 0 }
  guard let obs = peticion.results?.first else { return }      // nada en primer plano: la máscara, vacía
  let m = try obs.generateScaledMaskForImage(forInstances: obs.allInstances, from: manejador)
  CVPixelBufferLockBaseAddress(m, .readOnly)
  defer { CVPixelBufferUnlockBaseAddress(m, .readOnly) }
  guard CVPixelBufferGetWidth(m) == ancho, CVPixelBufferGetHeight(m) == alto,
        let base = CVPixelBufferGetBaseAddress(m) else {
    throw NSError(domain: "sujeto", code: 1, userInfo: [NSLocalizedDescriptionKey: "la máscara no tiene el tamaño del cuadro"])
  }
  let fila = CVPixelBufferGetBytesPerRow(m)
  let flotante = CVPixelBufferGetPixelFormatType(m) == kCVPixelFormatType_OneComponent32Float
  gris.withUnsafeMutableBufferPointer { g in
    for y in 0..<alto {
      let p = base.advanced(by: y * fila)
      let o = y * ancho
      if flotante {
        let f = p.assumingMemoryBound(to: Float.self)
        for x in 0..<ancho { g[o + x] = UInt8(max(0, min(255, f[x] * 255 + 0.5))) }
      } else {
        let b = p.assumingMemoryBound(to: UInt8.self)
        for x in 0..<ancho { g[o + x] = b[x] }
      }
    }
  }
}

/// Un CVPixelBuffer BGRA del tamaño pedido.
func nuevoCuadro(_ ancho: Int, _ alto: Int) -> CVPixelBuffer {
  var pb: CVPixelBuffer?
  let opciones = [kCVPixelBufferIOSurfacePropertiesKey as String: [:]] as CFDictionary
  guard CVPixelBufferCreate(kCFAllocatorDefault, ancho, alto, kCVPixelFormatType_32BGRA, opciones, &pb) == kCVReturnSuccess,
        let cuadro = pb else { salir("sujeto: no hay memoria para un cuadro de \(ancho)×\(alto)", 1) }
  return cuadro
}

/// Copia un cuadro RGB a un CVPixelBuffer BGRA.
func llenar(_ cuadro: CVPixelBuffer, _ rgb: [UInt8], _ ancho: Int, _ alto: Int) {
  CVPixelBufferLockBaseAddress(cuadro, [])
  defer { CVPixelBufferUnlockBaseAddress(cuadro, []) }
  let fila = CVPixelBufferGetBytesPerRow(cuadro)
  let base = CVPixelBufferGetBaseAddress(cuadro)!
  rgb.withUnsafeBufferPointer { s in
    for y in 0..<alto {
      let d = base.advanced(by: y * fila).assumingMemoryBound(to: UInt8.self)
      let o = y * ancho * 3
      for x in 0..<ancho {
        d[4 * x] = s[o + 3 * x + 2]
        d[4 * x + 1] = s[o + 3 * x + 1]
        d[4 * x + 2] = s[o + 3 * x]
        d[4 * x + 3] = 255
      }
    }
  }
}

let args = CommandLine.arguments

if args.count == 2 && args[1] == "--prueba" {
  // un cuadro gris con un círculo oscuro: basta con que Vision lo mire sin dar error
  let lado = 256
  var rgb = [UInt8](repeating: 200, count: lado * lado * 3)
  for y in 0..<lado {
    for x in 0..<lado where (x - 128) * (x - 128) + (y - 140) * (y - 140) < 70 * 70 {
      let i = (y * lado + x) * 3
      rgb[i] = 40; rgb[i + 1] = 60; rgb[i + 2] = 90
    }
  }
  let cuadro = nuevoCuadro(lado, lado)
  llenar(cuadro, rgb, lado, lado)
  var gris = [UInt8](repeating: 0, count: lado * lado)
  var persona = [UInt8](repeating: 0, count: lado * lado)
  do {
    try recortar(cuadro, lado, lado, &gris, &persona)
  } catch {
    salir("sujeto: Vision dio error (\(error.localizedDescription))", 2)
  }
  print("bien")
  exit(0)
}

guard args.count == 3, let ancho = Int(args[1]), let alto = Int(args[2]), ancho > 0, alto > 0 else {
  salir("uso: sujeto <ancho> <alto>  (cuadros RGB por la entrada estándar)   ·   sujeto --prueba", 1)
}

let tam = ancho * alto * 3
var rgb = [UInt8](repeating: 0, count: tam)
var gris = [UInt8](repeating: 0, count: ancho * alto)
var persona = [UInt8](repeating: 0, count: ancho * alto)
let cuadro = nuevoCuadro(ancho, alto)
var n = 0
var avisados = 0
while true {
  let leidos = rgb.withUnsafeMutableBytes { fread($0.baseAddress, 1, tam, stdin) }
  if leidos < tam { break }                    // se acabaron los cuadros
  llenar(cuadro, rgb, ancho, alto)
  var bien: UInt8 = 1
  do {
    try recortar(cuadro, ancho, alto, &gris, &persona)
  } catch {
    bien = 0
    for i in 0..<gris.count { gris[i] = 0; persona[i] = 0 }
    if avisados < 3 {
      FileHandle.standardError.write("sujeto: cuadro \(n) sin recorte (\(error.localizedDescription))\n".data(using: .utf8)!)
      avisados += 1
    }
  }
  var estado = bien
  fwrite(&estado, 1, 1, stdout)
  _ = gris.withUnsafeBytes { fwrite($0.baseAddress, 1, gris.count, stdout) }
  _ = persona.withUnsafeBytes { fwrite($0.baseAddress, 1, persona.count, stdout) }
  fflush(stdout)
  n += 1
}
