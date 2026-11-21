# Starts one build of a service in its own console window (so that Ctrl+C can later be sent to it alone),
# with stdout and stderr redirected to files, writes the java PID to <Log>.pid and returns at once.
# Generic version of the test-4/5 script (test 6 onward): the service name and extra JVM options are parameters.
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File start-java.ps1 -Service transformer -Jar transformer-v2.jar `
#       -Log run-v2 -Xmx 1536m -JvmOpts '-Dcontivo.runtime.classpath=C:\...\maps','-Dcontivo.runtime.datadir=C:\...\data'
# Runs: java -Xmx<Xmx> <JvmOpts...> -jar <Jar> run <Service>.yaml <Service>.properties network-services.properties datadog.properties
#
# Why the SetConsoleCtrlHandler call: a process started from the tool shell inherits the "ignore Ctrl+C" flag, and
# so would java; it then ignores the Ctrl+C and never runs its shutdown hooks. Clearing the flag here, before
# java is created, means java inherits it cleared.
param(
    [Parameter(Mandatory = $true)][string]$Service,
    [Parameter(Mandatory = $true)][string]$Jar,
    [Parameter(Mandatory = $true)][string]$Log,
    [string]$Xmx = '384m',
    [string[]]$JvmOpts = @()
)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class CtrlFlag {
    [DllImport("kernel32.dll", SetLastError = true)] public static extern bool SetConsoleCtrlHandler(IntPtr handler, bool add);
}
"@
[void][CtrlFlag]::SetConsoleCtrlHandler([IntPtr]::Zero, $false)        # false = stop ignoring Ctrl+C
Set-Location $PSScriptRoot
# -File passes "a,b" from another shell as ONE string: split it on ';' (pass -JvmOpts 'opt1;opt2')
$JvmOpts = @($JvmOpts | ForEach-Object { $_ -split ';' } | Where-Object { $_ })
$javaArgs = @("-Xmx$Xmx") + $JvmOpts + @('-jar', $Jar, 'run', "$Service.yaml", "$Service.properties",
                                        'network-services.properties', 'datadog.properties')
$proc = Start-Process -FilePath java.exe -PassThru -WindowStyle Minimized -ArgumentList $javaArgs `
    -RedirectStandardOutput "$Log.log" -RedirectStandardError "$Log.err"
$proc.Id | Out-File -Encoding ascii "$Log.pid"
"started java PID $($proc.Id): java $($javaArgs -join ' ')"
