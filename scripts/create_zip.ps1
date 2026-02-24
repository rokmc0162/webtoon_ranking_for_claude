$source = 'D:\CLAUDE YANGIL\webtoon_ranking_for_claude\webtoon_ranking_for_claude'
$dest = 'D:\CLAUDE YANGIL\webtoon_ranking_for_claude\webtoon_ranking_docker.zip'

# Remove old zip if exists
if (Test-Path $dest) { Remove-Item $dest }

# Create temp staging dir
$staging = Join-Path $env:TEMP 'webtoon_docker_staging'
if (Test-Path $staging) { Remove-Item $staging -Recurse -Force }
New-Item -ItemType Directory -Path $staging | Out-Null

# --- 1. docker 설정 ---
robocopy "$source\docker" "$staging\docker" /E | Out-Null

# --- 2. Next.js standalone ---
# standalone → dashboard-next/
robocopy "$source\dashboard-next\.next\standalone" "$staging\dashboard-next" /E /XD "@img" | Out-Null
# static → dashboard-next/.next/static/
robocopy "$source\dashboard-next\.next\static" "$staging\dashboard-next\.next\static" /E | Out-Null
# public → dashboard-next/public/
robocopy "$source\dashboard-next\public" "$staging\dashboard-next\public" /E | Out-Null

# --- 3. 루트 파일 ---
Copy-Item "$source\docker-compose.yml" "$staging\"
Copy-Item "$source\.env" "$staging\"

# --- 4. 모든 텍스트 파일을 LF로 변환 (CRLF 제거) ---
$textFiles = @(
    "$staging\docker-compose.yml",
    "$staging\.env",
    "$staging\docker\tunnel.sh"
)
foreach ($f in $textFiles) {
    if (Test-Path $f) {
        $content = [System.IO.File]::ReadAllText($f)
        $content = $content -replace "`r`n", "`n"
        [System.IO.File]::WriteAllText($f, $content, [System.Text.UTF8Encoding]::new($false))
    }
}

# Create zip
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $dest -Force
$size = [math]::Round((Get-Item $dest).Length / 1MB, 1)
Write-Host "ZIP created: $dest ($size MB)"

# Cleanup staging
Remove-Item $staging -Recurse -Force
