@echo off
rem A7S III (firmware 5.01): TEST (NOT RUN ON A CAMERA YET): the new sensor step alone with the proven 3840x2560 output and encoder steps, the screen at 3:2 and C3.
rem WRITES into the camera's memory (not firmware, not settings). A cold boot (battery out for 10 seconds) returns it to stock.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing: run setup.cmd first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -I -B "tools\camera_tests\CT6_memory_read_check\s3_apply.py" realrows %*
echo.
pause
