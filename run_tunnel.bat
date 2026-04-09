@echo off
C:\Users\ethan\.local\bin\cloudflared.exe tunnel --url http://localhost:5173 > %USERPROFILE%\cloudflared_url.txt 2>&1
