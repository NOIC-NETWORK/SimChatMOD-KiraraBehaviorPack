$tempFile = $args[0]
$ggufPath = $args[1]

$content = Get-Content -Path $tempFile -Raw -Encoding UTF8
$content = $content -replace '^FROM .*$', "FROM `"$ggufPath`""
Set-Content -Path $tempFile -Value $content -Encoding UTF8 -NoNewline