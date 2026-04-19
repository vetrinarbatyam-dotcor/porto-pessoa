# PowerShell — install Windows Task Scheduler entry for PESSOA weekly run.
# Run as: powershell -ExecutionPolicy Bypass -File install_task_scheduler.ps1

$taskName = "PESSOA-Weekly-Porto"
$bash = "C:\Program Files\Git\bin\bash.exe"
$script = "C:\Users\user\porto-pessoa\cron\weekly.sh"

# Monday 06:00 local
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 06:00
$action = New-ScheduledTaskAction -Execute $bash -Argument "`"$script`""
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RestartInterval (New-TimeSpan -Minutes 15) -RestartCount 3
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName $taskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Principal $principal `
    -Description "PESSOA · weekly FAROL+PESSOA+dashboard+notify" `
    -Force

Write-Host "Installed task '$taskName'. Triggers every Monday at 06:00."
Write-Host "Manage: Task Scheduler > Task Scheduler Library > $taskName"
