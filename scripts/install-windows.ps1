# One-shot installer for Windows: venv + Task Scheduler task that starts the bot at logon
# and restarts it if it stops. Run in PowerShell FROM THE PROJECT FOLDER:
#   powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
$ErrorActionPreference = "Stop"
$Dir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $Dir

if (-not (Test-Path ".env"))       { Write-Error ".env missing (copy .env.example)" }
if (-not (Test-Path "token.json") -and -not (Test-Path "data\token.json")) { Write-Error "token.json missing (run 'python auth.py' first)" }

Write-Host "[1/3] python venv + dependencies"
if (-not (Test-Path ".venv")) { py -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".venv\Scripts\python.exe" -m pip install -r app\requirements.txt -q
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

Write-Host "[2/3] Task Scheduler task 'CalendarBot'"
$TaskName = "CalendarBot"
$Action   = New-ScheduledTaskAction -Execute "$Dir\.venv\Scripts\pythonw.exe" -Argument "app\main.py" -WorkingDirectory $Dir
$Trigger  = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -RunLevel Limited | Out-Null
Start-ScheduledTask -TaskName $TaskName

Write-Host "[3/3] done. The bot now runs in the background and starts at every logon."
Write-Host "Logs:   Get-Content logs\bot.log -Wait"
Write-Host "Stop:   Stop-ScheduledTask -TaskName CalendarBot"
Write-Host "Remove: Unregister-ScheduledTask -TaskName CalendarBot -Confirm:`$false"
Write-Host "Tip: set Power Options -> Sleep -> Never, otherwise the bot pauses when the PC sleeps."
