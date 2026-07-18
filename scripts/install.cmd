@echo off
REM ============================================================================
REM Sarthi Agent Installer for Windows (CMD wrapper)
REM ============================================================================
REM This batch file launches the PowerShell installer for users running CMD.
REM
REM Usage:
REM   curl -fsSL https://raw.githubusercontent.com/jitu06583/sarthi-agent_desktop/main/scripts/install.cmd -o install.cmd && install.cmd && del install.cmd
REM
REM Or if you're already in PowerShell, use the direct command instead:
REM   iex (irm https://sarthi-agent.vercel.app/install.ps1)
REM ============================================================================

echo.
echo  Sarthi Agent Installer
echo  Launching PowerShell installer...
echo.

powershell -ExecutionPolicy ByPass -NoProfile -Command "iex (irm https://sarthi-agent.vercel.app/install.ps1)"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  Installation failed. Please try running PowerShell directly:
    echo    powershell -ExecutionPolicy ByPass -c "iex (irm https://sarthi-agent.vercel.app/install.ps1)"
    echo.
    pause
    exit /b 1
)
