param(
    [string]$PythonPath,
    [switch]$SkipDependencies,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
if (-not $PythonPath) {
    $localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
    $PythonPath = if (Test-Path -LiteralPath $localPython) { $localPython } else { (Get-Command python -ErrorAction Stop).Source }
}
$PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
& $PythonPath -c 'import sys, tkinter; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'A working Python 3.11+ installation with Tkinter is required.' }
if (-not $SkipDependencies) {
    & $PythonPath -m pip install -r (Join-Path $projectRoot 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $PythonPath -c 'import PIL, pystray'
if ($LASTEXITCODE -ne 0) { throw 'Pillow and pystray are required.' }
$pythonw = Join-Path (Split-Path -Parent $PythonPath) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonw)) { throw "Missing GUI interpreter: $pythonw" }
$taskOwner = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$taskAction = New-ScheduledTaskAction -Execute $pythonw -Argument ('"' + (Join-Path $projectRoot 'launch_supervised.py') + '"') -WorkingDirectory $projectRoot
$taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $taskOwner
$taskPrincipal = New-ScheduledTaskPrincipal -UserId $taskOwner -LogonType Interactive -RunLevel Limited
$taskSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew -StartWhenAvailable
$existingTask = Get-ScheduledTask -TaskName 'CodexUsageRings' -ErrorAction SilentlyContinue
if ($existingTask) {
    if ($existingTask.State -eq 'Running') { throw 'Exit the running widget before updating the installation.' }
    if ($existingTask.Actions.Arguments -ne $taskAction.Arguments) { throw 'CodexUsageRings is registered from another folder. Uninstall that deployment first.' }
}
Register-ScheduledTask -TaskName 'CodexUsageRings' -Action $taskAction -Trigger $taskTrigger -Principal $taskPrincipal -Settings $taskSettings -Force | Out-Null
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex Usage Rings.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + (Join-Path $projectRoot 'start_widget.py') + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Codex usage rings and monthly workspace allowance'
$shortcut.Save()
if (-not $NoStart) { Start-ScheduledTask -TaskName 'CodexUsageRings' }
Write-Output "Installed. Desktop shortcut: $shortcutPath"
