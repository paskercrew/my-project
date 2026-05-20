# Build script PowerShell - Android Forensic Tools
# Jalankan: klik kanan -> Run with PowerShell

$Host.UI.RawUI.WindowTitle = "Android Forensic Tools - Build EXE"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Android Forensic Tools - Build EXE untuk Windows"           -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Cek Python
try {
    $pyVer = python --version 2>&1
    Write-Host "[OK] $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python tidak ditemukan!" -ForegroundColor Red
    Write-Host "Unduh di: https://www.python.org/downloads/"
    Read-Host "Tekan Enter untuk keluar"
    exit 1
}

# Install dependensi
Write-Host ""
Write-Host "[1/5] Install dependensi..." -ForegroundColor Yellow
pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Gagal install dependensi." -ForegroundColor Red
    Read-Host "Tekan Enter untuk keluar"
    exit 1
}
Write-Host "      OK" -ForegroundColor Green

# Buat folder output
if (-not (Test-Path "dist")) { New-Item -ItemType Directory -Path "dist" | Out-Null }

$tools = @(
    @{ Name = "AndroidForensicUltra"; Script = "android_forensics.py"; Step = "2" },
    @{ Name = "SamsungFRPErase";      Script = "frp_erase.py";         Step = "3" },
    @{ Name = "XiaomiADB";            Script = "xiaomi_adb.py";         Step = "4" }
)

foreach ($tool in $tools) {
    Write-Host ""
    Write-Host "[$($tool.Step)/5] Build $($tool.Name).exe ..." -ForegroundColor Yellow

    pyinstaller `
        --onefile `
        --console `
        --clean `
        --noconfirm `
        --name $tool.Name `
        --distpath dist `
        --workpath "build_tmp\$($tool.Name)" `
        --specpath build_tmp `
        $tool.Script

    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Build $($tool.Name).exe gagal." -ForegroundColor Red
        Read-Host "Tekan Enter untuk keluar"
        exit 1
    }
    Write-Host "      OK - dist\$($tool.Name).exe" -ForegroundColor Green
}

# Bersihkan build temp
Write-Host ""
Write-Host "[5/5] Bersihkan file sementara..." -ForegroundColor Yellow
if (Test-Path "build_tmp") { Remove-Item -Recurse -Force "build_tmp" }
Write-Host "      OK" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  BUILD SELESAI!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "File EXE tersimpan di folder: dist\\"
Write-Host ""
Get-ChildItem dist\*.exe | Format-Table Name, Length, LastWriteTime
Write-Host ""
Read-Host "Tekan Enter untuk keluar"
