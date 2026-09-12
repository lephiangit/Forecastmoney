@echo off
REM ============================================================================
REM  Commit dot sua thu 2 cua ban quet toan du an ForecastAI.
REM  Nhay doi chuot vao file nay, hoac chay trong PowerShell: .\commit-fix2.bat
REM ============================================================================
cd /d "%~dp0"

echo.
echo === Don file khoa git cu (neu con) ===
if exist ".git\index.lock" del /f /q ".git\index.lock"

echo.
echo === Go 107 file CSV backup ra khoi git (van giu tren dia) ===
git rm -r --cached data_backup_20260829_124746 -q 2>nul

echo.
echo === Them thay doi ===
git add -A backend frontend training kaggle

echo.
echo === Commit ===
git commit -F commit-msg-fix2.txt
if errorlevel 1 (
  echo.
  echo [!] Commit that bai. Doc thong bao ben tren.
  pause
  exit /b 1
)

echo.
echo === Xong. Lich su gan nhat: ===
git log --oneline -3

echo.
echo Con lai (tuy chon): day len GitHub bang  git push origin main
echo Sau do co the xoa hai file: commit-msg-fix2.txt va commit-fix2.bat
echo.
pause
