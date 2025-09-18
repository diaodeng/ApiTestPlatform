Rem kill bootstrap and trade-wrap process
for /F "tokens=5" %%I in ('netstat /ano ^| findstr 0.0.0.0:8081') do taskkill /f /pid %%I
for /F "tokens=5" %%I in ('netstat /ano ^| findstr 0.0.0.0:18889') do taskkill /f /pid %%I
Rem Close the old CMD window
taskkill /FI "WINDOWTITLE eq Offline-Service" /IM cmd.exe /F