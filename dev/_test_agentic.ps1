$token = "sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ"

$body = @{
    model = "MiniMax-M2.7"
    max_tokens = 1500
    temperature = 0.3
    messages = @(
        @{role = "system"; content = "You are a WashU academic advisor. Answer using the context. If you need more info say NEED_MORE_INFO: <topic>."}
        @{role = "user"; content = "Context: `n## CS Minor`nCS minor requires CSE 131, CSE 240, 2 upper CSE courses. CSE 1301 and CSE 2407 are outside electives. `n`n## Biology GenComput Biology`nRequired outside electives: CSE 1301 and CSE 2407. `n`nQuestion: Do CSE 1301 and CSE 2407 double count for both the computational biology major and CS minor?"}
    )
} | ConvertTo-Json -Depth 5

$tmp = [System.IO.Path]::GetTempPath() + "mm_body.json"
$body | Out-File -FilePath $tmp -Encoding UTF8

$headers = @{ "Authorization" = "Bearer $token"; "Content-Type" = "application/json" }
$uri = "https://api.minimax.io/v1/chat/completions"

Write-Host "Calling MiniMax..."
try {
    $resp = Invoke-RestMethod -Uri $uri -Method POST -Headers $headers -Body $tmp -TimeoutSec 60
    Write-Host "SUCCESS!"
    Write-Host $resp.choices[0].message.content
} catch {
    Write-Host "FAILED: $($_.Exception.Message)"
} finally {
    Remove-Item $tmp -ErrorAction SilentlyContinue
}