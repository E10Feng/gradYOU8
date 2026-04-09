$body = Get-Content 'C:\Users\ethan\.openclaw\workspace\minimax_request.json' -Raw
$headers = @{
    'Authorization' = 'Bearer sk-cp-eONyc1lsRF8VqUMKE41edOMcpXnFqd_vFFtJVZ_ZlrDOWofcj3eWqkiSU7nrNZwuyqDLzc8UyP3Lljh3DwzKFIyOaDqo3ok22P_V3kr-MpydccZcXl60bpQ'
    'Content-Type' = 'application/json'
    'anthropic-version' = '2023-06-01'
}
$response = Invoke-WebRequest -Uri 'https://api.minimax.io/anthropic/v1/messages' -Method POST -Headers $headers -Body $body
$response.Content | Out-File 'C:\Users\ethan\.openclaw\workspace\minimax_response.json'
