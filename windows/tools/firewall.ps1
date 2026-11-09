# -*- coding: utf-8 -*-
"""Windows Güvenlik Duvarı kuralı: PrintBridge ajanı için gelen TCP portu.

Yönetici olarak çalıştırın:
    powershell -ExecutionPolicy Bypass -File tools\\firewall.ps1
    powershell -ExecutionPolicy Bypass -File tools\\firewall.ps1 -Remove

Kural yalnızca "Özel" (Private) ağ profiline ve varsa ajan .exe'sine kısıtlanır.
"""

param(
    [switch]$Remove,
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$ruleName = 'PrintBridge Agent'

$principal = New-Object Security.Principal.WindowsPrincipal(
    [Security.Principal.WindowsIdentity]::GetCurrent()
)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Bu betik yönetici yetkisi gerektirir. PowerShell''i "Yönetici olarak çalıştır" ile açın.'
}

if ($Port -le 0) {
    $Port = 8477
    $configPath = Join-Path $env:ProgramData 'PrintBridge\config.json'
    if (Test-Path $configPath) {
        try {
            $Port = [int](Get-Content $configPath -Raw | ConvertFrom-Json).port
        } catch {
            Write-Warning "config.json okunamadı; varsayılan port $Port kullanılacak."
        }
    }
}

if ($Remove) {
    $existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if ($existing) {
        Remove-NetFirewallRule -DisplayName $ruleName
        Write-Host "Kural kaldırıldı: $ruleName" -ForegroundColor Green
    } else {
        Write-Host "Kural bulunamadı: $ruleName"
    }
    return
}

Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule

$root = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $root 'dist\PrintBridge-Agent.exe'
$arguments = @{
    DisplayName = $ruleName
    Description = 'PrintBridge Agent - iPhone yazdirma koprusu (ozel ag)'
    Direction = 'Inbound'
    Action = 'Allow'
    Protocol = 'TCP'
    LocalPort = $Port
    Profile = 'Private'
}
if (Test-Path $exe) {
    $arguments['Program'] = $exe
}

New-NetFirewallRule @arguments | Out-Null
Write-Host "Kural eklendi: $ruleName (TCP $Port, ozel ag)" -ForegroundColor Green
if (-not (Test-Path $exe)) {
    Write-Host 'Not: .exe henuz derlenmedigi icin kural programa baglanmadi (tum uygulamalar).' -ForegroundColor Yellow
}
