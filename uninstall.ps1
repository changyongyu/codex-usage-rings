$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$expectedArgument = '"' + (Join-Path $projectRoot 'launch_supervised.py') + '"'
$task = Get-ScheduledTask -TaskName 'CodexUsageRings' -ErrorAction SilentlyContinue
if ($task -and $task.Actions.Arguments -ne $expectedArgument) {
    throw 'The scheduled task belongs to another installation. No changes were made.'
}
if ($task) { Disable-ScheduledTask -TaskName 'CodexUsageRings' | Out-Null }
$stateDirectory = Join-Path ([Environment]::GetFolderPath('LocalApplicationData')) 'CodexUsageRings'
New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
New-Item -ItemType File -Path (Join-Path $stateDirectory 'stop.requested') -Force | Out-Null
if ($task) { Stop-ScheduledTask -TaskName 'CodexUsageRings' }
# Stop only this deployment's two exact script paths; never all Python processes.
$scriptPaths = @((Join-Path $projectRoot 'launch_supervised.py'), (Join-Path $projectRoot 'codex_usage_widget.py'))
$processes = Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe', 'pythonw.exe') }
foreach ($process in $processes) {
    foreach ($scriptPath in $scriptPaths) {
        if ($process.CommandLine -and $process.CommandLine -match ('(?:"|\s)' + [regex]::Escape($scriptPath) + '(?:"|\s|$)')) {
            Stop-Process -Id $process.ProcessId -ErrorAction SilentlyContinue
            break
        }
    }
}
if ($task) { Unregister-ScheduledTask -TaskName 'CodexUsageRings' -Confirm:$false }
$shortcutPath = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Codex Usage Rings.lnk'
if (Test-Path -LiteralPath $shortcutPath) {
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    if ($shortcut.Arguments -eq ('"' + (Join-Path $projectRoot 'start_widget.py') + '"')) {
        Remove-Item -LiteralPath $shortcutPath
    }
}
Write-Output 'Uninstalled task and shortcut. Source, settings, Codex sign-in and history were preserved.'
