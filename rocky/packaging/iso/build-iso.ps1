# Build the Rocky Debian live ISO on Windows using Docker Desktop.
#
#   cd rocky\packaging\iso
#   .\build-iso.ps1              # ISO lands in your Downloads folder
#   .\build-iso.ps1 -Clean      # also delete the build image and cache afterward
#   .\build-iso.ps1 -OutDir D:\isos
#
# Needs Docker Desktop running. The whole build runs inside a throwaway container,
# so the large build tree never touches your Windows disk. Only the finished ISO
# is copied out. The container is removed on exit (--rm); your other containers
# and images are not touched.
param(
    [string]$OutDir = (Join-Path $env:USERPROFILE "Downloads"),
    [switch]$Clean
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker was not found. Install Docker Desktop and start it, then re-run."
    exit 1
}
try { docker info *> $null } catch {
    Write-Error "Docker is installed but the engine is not running. Start Docker Desktop and re-run."
    exit 1
}

$isoDir   = $PSScriptRoot
$rockyDir = (Resolve-Path (Join-Path $isoDir "..\..")).Path   # the rocky\ directory
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

Write-Host "Building the image (cached after the first run)..."
docker build -f (Join-Path $isoDir "Dockerfile") -t rocky-iso $rockyDir

Write-Host "Building the ISO inside a container. Output goes to $OutDir"
# --rm removes this container when it finishes. --privileged is needed because
# live-build uses loop mounts. Only $OutDir is mounted, as /out.
docker run --rm --privileged -v "${OutDir}:/out" rocky-iso

$iso = Get-ChildItem -Path $OutDir -Filter "rocky-*-amd64.iso" |
       Sort-Object LastWriteTime | Select-Object -Last 1
if ($iso) {
    Write-Host "Done. ISO at $($iso.FullName)"
} else {
    Write-Error "Build finished but no .iso was found in $OutDir. Check the output above."
    exit 1
}

if ($Clean) {
    Write-Host "Cleaning up the build image and cache..."
    docker rmi rocky-iso 2>$null | Out-Null
    docker builder prune -f | Out-Null
    Write-Host "Removed the rocky-iso image and build cache. Your other Docker data is untouched."
} else {
    Write-Host "Kept the rocky-iso image for faster rebuilds. Run with -Clean to remove it."
}
