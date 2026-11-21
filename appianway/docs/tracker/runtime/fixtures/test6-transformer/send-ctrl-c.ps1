# Sends Ctrl+C to the console of one process, as a terminal does, so that the JVM runs its shutdown hooks
# (a task stop or taskkill /F skips them). Usage: powershell -NoProfile -File send-ctrl-c.ps1 -ProcessId <pid>
param([Parameter(Mandatory = $true)][int]$ProcessId)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class ConsoleControl {
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool AttachConsole(uint processId);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool FreeConsole();
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool SetConsoleCtrlHandler(IntPtr handler, bool add);
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool GenerateConsoleCtrlEvent(uint ctrlEvent, uint processGroupId);
}
"@

[void][ConsoleControl]::FreeConsole()                                   # leave this script's own console
if (-not [ConsoleControl]::AttachConsole([uint32]$ProcessId)) { throw "AttachConsole($ProcessId) failed" }
[void][ConsoleControl]::SetConsoleCtrlHandler([IntPtr]::Zero, $true)    # this script ignores the Ctrl+C itself
if (-not [ConsoleControl]::GenerateConsoleCtrlEvent(0, 0)) { throw "GenerateConsoleCtrlEvent failed" }   # 0 = CTRL_C_EVENT, to the whole console
Start-Sleep -Milliseconds 500
[void][ConsoleControl]::FreeConsole()
"sent Ctrl+C to the console of process $ProcessId"
