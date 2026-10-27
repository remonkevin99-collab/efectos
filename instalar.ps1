# Instala el motor de efectos (Windows). Se puede correr las veces que quieras: lo que ya está, no se toca.
#
#     powershell -ExecutionPolicy Bypass -File instalar.ps1
#
# Hace tres cosas, todas dentro de esta carpeta:
#   1. crea el entorno de Python en .venv (Python 3.10, 3.11 o 3.12; si tienes `uv`, lo usa y él baja Python si falta),
#   2. instala lo necesario (requirements.txt),
#   3. baja los dos modelos de Google (la persona y la cara) a modelos\.
# Y al final comprueba que todo funciona y dice LISTO.

$ErrorActionPreference = 'Continue'
$ProgressPreference = 'SilentlyContinue'     # sin la barra de progreso, las descargas van mucho más rápido
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Aqui
$Venv = Join-Path $Aqui '.venv'
$Py = Join-Path $Venv 'Scripts\python.exe'
$Comprobar = 'import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)'

function Existe([string]$Nombre) {
    return $null -ne (Get-Command $Nombre -ErrorAction SilentlyContinue)
}

function Falla([string]$Texto) {
    Write-Host ''
    Write-Host "ERROR: $Texto"
    exit 1
}

Write-Host '== Motor de efectos: instalación =='

# ── ffmpeg ──────────────────────────────────────────────────────────────────────────────────────────────────────────
if (Existe 'ffmpeg') {
    Write-Host "ffmpeg: lo tienes ($((Get-Command ffmpeg).Source))"
} else {
    Write-Host 'ffmpeg: no está instalado en tu sistema. No pasa nada: se usará el que trae el paquete imageio-ffmpeg.'
    Write-Host "        (Si quieres el tuyo: 'winget install Gyan.FFmpeg' y abre otra ventana.)"
}

# ── ¿el .venv que ya hay sirve? (Python 3.10 a 3.12) ──────────────────────────────────────────────────────────────
$VenvSirve = $false
if (Test-Path $Py) {
    & $Py -c $Comprobar 2>$null
    if ($LASTEXITCODE -eq 0) { $VenvSirve = $true }
}

if ($VenvSirve) {
    Write-Host "Python: ya hay un entorno en .venv ($(& $Py --version 2>&1)), se usa ese."
} elseif (Existe 'uv') {
    Write-Host 'Python: creando .venv con uv (Python 3.12; si no lo tienes, uv lo baja)...'
    if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
    uv venv --seed --python 3.12 $Venv
    if ($LASTEXITCODE -ne 0) { Falla 'uv no pudo crear el entorno de Python (mira el mensaje de arriba).' }
} else {
    # el lanzador «py» de Windows primero (elige la versión), y si no, el python que haya
    $Base = $null
    foreach ($Candidato in @('py -3.12', 'py -3.11', 'py -3.10', 'python', 'python3')) {
        $Partes = $Candidato.Split(' ')
        $Exe = $Partes[0]
        if ($Partes.Length -gt 1) { $Extra = $Partes[1..($Partes.Length - 1)] } else { $Extra = @() }
        if (Existe $Exe) {
            & $Exe @Extra -c $Comprobar 2>$null
            if ($LASTEXITCODE -eq 0) { $Base = $Candidato; break }
        }
    }
    if ($null -eq $Base) {
        # no hay un Python que sirva: se instala uv (el instalador oficial, en tu carpeta de usuario), que baja Python solo
        Write-Host 'Python: no tienes Python 3.10, 3.11 o 3.12 (MediaPipe todavía no funciona con los más nuevos).'
        Write-Host '        Instalo uv, que lo baja solo (es una vez, en tu carpeta de usuario)...'
        try { powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex" *> $null } catch { }
        $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
        if (Existe 'uv') {
            Write-Host 'Python: creando .venv con uv (Python 3.12)...'
            if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
            uv venv --seed --python 3.12 $Venv
            if ($LASTEXITCODE -ne 0) { Falla 'uv no pudo crear el entorno de Python (mira el mensaje de arriba).' }
        }
    }
    if ($null -eq $Base -and -not (Test-Path $Py)) {
        Write-Host ''
        Write-Host 'ERROR: falta Python 3.10, 3.11 o 3.12 (MediaPipe todavía no funciona con versiones más nuevas).'
        Write-Host '  La forma más fácil: instala uv y vuelve a correr este archivo; uv baja Python solo:'
        Write-Host '    powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"'
        Write-Host '  O instala Python 3.12 a mano:'
        Write-Host '    winget install Python.Python.3.12   (o el instalador de https://www.python.org/downloads/)'
        Write-Host '  Después, cierra esta ventana, abre otra y vuelve a correr la instalación.'
        exit 1
    }
    if ($null -ne $Base) {
        $Partes = $Base.Split(' ')
        $Exe = $Partes[0]
        if ($Partes.Length -gt 1) { $Extra = $Partes[1..($Partes.Length - 1)] } else { $Extra = @() }
        Write-Host "Python: creando .venv con $Base ($(& $Exe @Extra --version 2>&1))..."
        if (Test-Path $Venv) { Remove-Item -Recurse -Force $Venv }
        & $Exe @Extra -m venv $Venv
        if ($LASTEXITCODE -ne 0) { Falla 'no se pudo crear el entorno de Python (mira el mensaje de arriba).' }
    }
}

# un .venv viejo hecho con uv puede no tener pip (y el transcriptor de palabras lo usa): se le pone
& $Py -m pip --version *> $null
if ($LASTEXITCODE -ne 0 -and (Existe 'uv')) {
    uv pip install --quiet --python $Py pip
}

# ── los paquetes ────────────────────────────────────────────────────────────────────────────────────────────────────
Write-Host 'Paquetes: instalando lo de requirements.txt (la primera vez tarda un par de minutos)...'
if (Existe 'uv') {
    uv pip install --quiet --python $Py -r requirements.txt
} else {
    & $Py -m pip install --quiet --upgrade pip
    & $Py -m pip install --quiet -r requirements.txt
}
if ($LASTEXITCODE -ne 0) { Falla 'no se pudieron instalar los paquetes (mira el mensaje de arriba).' }

# ── los modelos de Google ───────────────────────────────────────────────────────────────────────────────────────────
New-Item -ItemType Directory -Force -Path (Join-Path $Aqui 'modelos') | Out-Null
function Bajar([string]$Archivo, [string]$Url) {
    $Destino = Join-Path (Join-Path $Aqui 'modelos') $Archivo
    if ((Test-Path $Destino) -and ((Get-Item $Destino).Length -gt 0)) {
        Write-Host "Modelo: $Archivo ya está."
        return
    }
    Write-Host "Modelo: bajando $Archivo..."
    try {
        Invoke-WebRequest -Uri $Url -OutFile "$Destino.parte" -UseBasicParsing
        Move-Item -Force "$Destino.parte" $Destino
    } catch {
        Falla "no se pudo bajar $Archivo. ¿Hay internet? ($($_.Exception.Message))"
    }
}
Bajar 'selfie_segmenter.tflite' 'https://storage.googleapis.com/mediapipe-models/image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite'
Bajar 'blaze_face_short_range.tflite' 'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/latest/blaze_face_short_range.tflite'

# ── la prueba final ─────────────────────────────────────────────────────────────────────────────────────────────────
& $Py efectos.py --comprobar
if ($LASTEXITCODE -ne 0) { Falla 'la comprobación encontró algo mal (arriba dice qué).' }
Write-Host ''
Write-Host 'Para usarlo (desde esta carpeta):'
Write-Host '  .venv\Scripts\python.exe efectos.py --lista'
Write-Host '  .venv\Scripts\python.exe efectos.py orbita mi-video.mp4 --desde 2 --hasta 6'
Write-Host ''
Write-Host 'LISTO'
