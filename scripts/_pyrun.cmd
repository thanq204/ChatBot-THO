@echo off
REM Cross-platform Python launcher for AI log hooks (Windows cmd.exe).
REM Tries py -3 -> python -> python3 in order, runs the given script with all args.
REM Exits 0 silently if no Python is found - hooks must never block the AI tool.

REM Codex desktop's bundled runtime is the most reliable option in hooks.
set "CODEX_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%CODEX_PYTHON%" (
  "%CODEX_PYTHON%" %*
  exit /b %ERRORLEVEL%
)

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 %*
  if not errorlevel 1 exit /b 0
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python %*
  if not errorlevel 1 exit /b 0
)

where python3 >nul 2>nul
if %ERRORLEVEL%==0 (
  python3 %*
  if not errorlevel 1 exit /b 0
)

exit /b 0
