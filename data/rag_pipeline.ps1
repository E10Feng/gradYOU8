# RAG Pipeline v3 - Targeted search for specific courses and requirements
$ErrorActionPreference = "Stop"

# Load JSON
$bulletin = Get-Content 'C:\Users\ethan\.openclaw\workspace\builds\washu-navigator\data\bulletin_full.json' -Raw | ConvertFrom-Json

# Flatten all nodes recursively
function Flatten-Nodes {
    param($nodes, [System.Collections.ArrayList]$acc)
    if ($null -eq $acc) { $acc = [System.Collections.ArrayList]::new() }
    foreach ($n in $nodes) {
        $null = $acc.Add($n)
        if ($n.nodes -and $n.nodes.Count -gt 0) {
            Flatten-Nodes -nodes $n.nodes -acc $acc | Out-Null
        }
    }
    return $acc
}

$allNodes = [System.Collections.ArrayList]::new()
foreach ($topNode in $bulletin) {
    $null = $allNodes.Add($topNode)
    if ($topNode.nodes -and $topNode.nodes.Count -gt 0) {
        Flatten-Nodes -nodes $topNode.nodes -acc $allNodes | Out-Null
    }
}
Write-Host "Total flattened nodes: $($allNodes.Count)"

# TARGETED SEARCH: Find nodes that actually contain the course numbers or relevant policies
$coursePattern = "cse\s*1301|cse\s*2407|cse-1301|cse-2407"
$doubleCountPattern = "double.count|doublecount"
$compBioPattern = "computational biology"
$csMinorPattern = "computer science minor"
$cseCoursesPattern = "cse\s*\d{4}"

# Score each node
$scored = foreach ($n in $allNodes) {
    $title = $n.title
    $summary = $n.summary
    $text = $n.text
    $fullText = "$title $summary $text".ToLower()
    
    $score = 0
    
    # CRITICAL: Exact course match
    if ($fullText -match $coursePattern) { $score += 200 }
    
    # CRITICAL: Double count policy
    if ($fullText -match $doubleCountPattern) { $score += 100 }
    
    # High value: Computational biology
    if ($fullText -match $compBioPattern) { $score += 60 }
    
    # High value: CS minor
    if ($fullText -match $csMinorPattern) { $score += 50 }
    
    # Medium: CSE courses mentioned
    $cseMatches = [regex]::Matches($fullText, $cseCoursesPattern)
    $score += $cseMatches.Count * 3
    
    # Bonus: actual requirement text (has prerequisite/credit/unit info)
    if ($text -match "prerequisite|credit|unit|fall spring|Fall Spring") { $score += 10 }
    
    # Penalty: TOC/Index nodes (unless they have course content)
    $titleLower = $title.ToLower()
    if ($titleLower -match "^index$|table of contents" -and $score -lt 50) { $score = [Math]::Floor($score * 0.1) }
    
    [PSCustomObject]@{
        node_id = $n.node_id
        title = $title
        summary = $summary
        text = $text
        score = $score
    }
}

# Top 20
Write-Host "`n=== TOP 20 NODES BY TARGETED SCORE ==="
$top20 = $scored | Sort-Object score -Descending | Select-Object -First 20
foreach ($tn in $top20) {
    $textLen = $tn.text.Length
    Write-Host "Score=$($tn.score) ID=$($tn.node_id) Len=$textLen Title=$($tn.title)"
}

# Top 6
$topNodes = $top20 | Select-Object -First 6

# Build context
$contextParts = foreach ($tn in $topNodes) {
    $textSnippet = $tn.text
    if ($textSnippet.Length -gt 1200) { $textSnippet = $textSnippet.Substring(0, 1200) + "[...truncated...]" }
    "=== Node $($tn.node_id): $($tn.title) ===`n$textSnippet"
}
$context = $contextParts -join "`n`n"

$question = "If I'm majoring in computational biology and minoring in computer science, do CSE 1301 and CSE 2407 double count for both the major and minor?"

$systemPrompt = "You are a helpful WashU academic advisor assistant. Use only the provided context from the WashU Undergraduate Bulletin 2025-26 to answer the question. If the context does not contain enough information to fully answer, say so. Be precise and cite specific bulletin rules, courses, and policies."
$userPrompt = "Context from WashU Bulletin:`n$context`n`nQuestion: $question"

# Call MiniMax API
$token = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"
$body = @{
    model = "MiniMax-M2.7"
    max_tokens = 1500
    temperature = 0.3
    messages = @(
        @{role = "system"; content = $systemPrompt}
        @{role = "user"; content = $userPrompt}
    )
} | ConvertTo-Json -Depth 10

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

try {
    $response = Invoke-RestMethod -Uri "https://api.minimax.io/anthropic/v1/messages" -Method Post -Headers $headers -Body $body
    $answer = $response.content
} catch {
    $answer = "ERROR: $($_.Exception.Message)"
}

# Output
Write-Host "`n=== QUESTION ==="
Write-Host $question
Write-Host "`n=== TOP NODES SELECTED (title + node_id + score) ==="
foreach ($tn in $topNodes) {
    Write-Host "$($tn.title) | node_id: $($tn.node_id) | score: $($tn.score)"
}
Write-Host "`n=== ANSWER FROM MINIMAX ==="
Write-Host $answer
