$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:AEGIS_BIND_ADDRESS = '0.0.0.0'
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { throw 'Docker Compose failed to start MORS AEGIS.' }
$port = '8000'
if (Test-Path -LiteralPath '.env') {
    $line = Get-Content -LiteralPath '.env' | Where-Object { $_ -match '^\s*AEGIS_PORT\s*=' } | Select-Object -Last 1
    if ($line -match '^\s*AEGIS_PORT\s*=\s*["'']?(\d+)' ) { $port = $Matches[1] }
}
$addresses = Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -match 'Wi-Fi|Wireless' -and $_.IPAddress -notmatch '^(127\.|169\.254\.)' }
foreach ($address in $addresses) { Write-Host "Open on your phone: http://$($address.IPAddress):$port/" }
Write-Host 'Use the access token configured in .env. Connect the phone to the same trusted network.'
