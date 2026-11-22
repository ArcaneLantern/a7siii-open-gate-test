@echo off
rem A7S III (firmware 5.01): put back only the two rear-screen steps (press C3 until the screen is at 3:2 first).
rem WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\s3_apply.py" screen-putback %*
echo.
pause
