# RAG Q&A Pipeline: Biology Major Requirements
# Uses MiniMax Chat API (Anthropic-compatible endpoint from models.json)

$ErrorActionPreference = 'Continue'

$MINIMAX_TOKEN = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
$API_URL = "https://api.minimax.io/anthropic/v1/messages"

# 1. Load JSON
$JSON_PATH = "C:\Users\ethan\.openclaw\media\inbound\document-structure-pi-cmnjh3eow03yj01qp0hv0s1f0---7806c9ed-271a-496e-81db-5d4619b8ee35.json"
$jsonContent = Get-Content $JSON_PATH -Raw | ConvertFrom-Json

# 2. Flatten all nodes
function Get-AllNodes($nodes, $acc) {
    foreach ($n in $nodes) {
        $acc.Add($n) | Out-Null
        if ($n.nodes) {
            Get-AllNodes $n.nodes $acc
        }
    }
    $acc
}
$allNodes = Get-AllNodes $jsonContent ([System.Collections.Generic.List[object]]::new())

# Deduplicate by node_id
$seen = @{}
$uniqueNodes = @()
foreach ($n in $allNodes) {
    if (-not $seen.ContainsKey($n.node_id)) {
        $seen[$n.node_id] = $true
        $uniqueNodes += $n
    }
}
$allNodes = $uniqueNodes

Write-Host "=== Total unique nodes: $($allNodes.Count) ===" -ForegroundColor Cyan

# 3. Relevance scoring
$question = "What are the requirements for the Biology major?"
$keywords = @("biology", "major", "requirement", "specialization", "course", "unit", "credit", "prerequisite", "program", "area")

function Score-Node($node) {
    $text = "$($node.title) $($node.summary) $($node.text)".ToLower()
    $score = 0
    foreach ($kw in $keywords) {
        $count = ([regex]::Matches($text, [regex]::Escape($kw))).Count
        $score += $count
    }
    if ($node.title -match "Biology" -and $node.title -match "Major") { $score += 20 }
    if ($node.title -eq "Majors") { $score += 10 }
    if ($node.node_id -eq "0001") { $score += 15 }
    $score
}

Write-Host "`n=== Scoring top 20 nodes ===" -ForegroundColor Cyan
$scored = $allNodes | ForEach-Object {
    $s = Score-Node $_
    [PSCustomObject]@{ NodeId = $_.node_id; Title = $_.title; Score = $s; Node = $_ }
} | Sort-Object Score -Descending | Select-Object -First 20

foreach ($s in $scored) {
    Write-Host "  Score=$($s.Score) [$($s.NodeId)] $($s.Title)"
}

$top4 = $scored[0..3]

Write-Host "`n=== Top 4 selected ===" -ForegroundColor Green
foreach ($t in $top4) {
    Write-Host "  [$($t.NodeId)] Score=$($t.Score) -> $($t.Title)"
}

# 4. Build context string
$sep = [Environment]::NewLine + ("=" * 80) + [Environment]::NewLine
$contextParts = @()
foreach ($t in $top4) {
    $contextParts += "## Node [$($t.NodeId)]: $($t.Title)" + $sep + $t.Node.text
}
$contextString = $contextParts -join $sep

if ($contextString.Length -gt 6000) {
    $contextString = $contextString.Substring(0, 6000) + "... [truncated]"
}

Write-Host "`n=== Context built ($($contextString.Length) chars) ===" -ForegroundColor Cyan

# 5. Build Anthropic-format messages
$systemContent = "You are a helpful academic advisor assistant. Using ONLY the provided context extracted from the WashU Arts & Sciences Bulletin, answer the user's question about Biology major requirements. Be precise and cite which section(s) your answer comes from. If the context does not contain enough detail to fully answer, say so clearly."

$userContent = "Question: `"$question`"$([Environment]::NewLine)$([Environment]::NewLine)Context:$([Environment]::NewLine)$contextString"

$body = @{
    model = "MiniMax-M2.7"
    max_tokens = 1024
    messages = @(
        @{ role = "user"; content = $userContent }
    )
    system = $systemContent
} | ConvertTo-Json -Depth 10

Write-Host "`n=== Calling MiniMax API (Anthropic format) ===" -ForegroundColor Cyan
Write-Host "URL: $API_URL"
Write-Host "Top-4 nodes used:"
foreach ($t in $top4) { Write-Host "  - [$($t.NodeId)] $($t.Title)" }

$headers = @{
    "Authorization" = "Bearer $MINIMAX_TOKEN"
    "Content-Type" = "application/json"
    "x-api-key" = $MINIMAX_TOKEN
    "anthropic-version" = "2023-06-01"
}

try {
    $response = Invoke-RestMethod -Uri $API_URL -Method Post -Headers $headers -Body $body -TimeoutSec 60
    Write-Host "`n========================================" -ForegroundColor Green
    Write-Host "       RAG Q&A ANSWER" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Question: $question"
    Write-Host ""
    Write-Host "--- Full API Response ---" -ForegroundColor Yellow
    $response | ConvertTo-Json -Depth 10 | Write-Host
    Write-Host ""
    Write-Host "--- Answer ---" -ForegroundColor Green
    if ($response.content) {
        $response.content | ForEach-Object { $_.text | Write-Host }
    } else {
        $response | Write-Host
    }
} catch {
    Write-Host "`n=== ERROR ===" -ForegroundColor Red
    Write-Host $_.Exception.Message
    try {
        $errBody = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream()).ReadToEnd()
        Write-Host "Response body: $errBody"
    } catch {}
}
