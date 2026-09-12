@echo off
setlocal
REM ============================================================================
REM  Commit backtest viet lai - ForecastAI
REM  Chay: nhay doi chuot, hoac trong PowerShell go:  .\commit-fix3.bat
REM
REM  Script DUNG LAI ngay khi co buoc nao that bai, de khong lap lai tinh huong
REM  "commit hong nhung file thong diep van bi xoa".
REM ============================================================================
cd /d "%~dp0"
echo.
echo ============================================================
echo  ForecastAI - commit backtest viet lai
echo ============================================================

REM ---- Buoc 1: go file khoa chet -------------------------------------------
if exist ".git\index.lock" (
  echo [1/4] Tim thay .git\index.lock - dang xoa...
  del /f /q ".git\index.lock"
  if exist ".git\index.lock" (
    echo.
    echo [X] KHONG xoa duoc .git\index.lock.
    echo     Nghia la co mot tien trinh git DANG THAT SU chay - thuong la
    echo     VS Code hoac SourceTree. Dong chung lai roi chay lai file nay.
    echo.
    pause
    exit /b 1
  )
  echo       da xoa.
) else (
  echo [1/4] Khong co file khoa. OK.
)

REM ---- Buoc 2: kiem tra file thong diep -------------------------------------
if not exist "commit-msg-fix3.txt" (
  echo.
  echo [X] Thieu commit-msg-fix3.txt trong thu muc nay.
  echo     Bao Claude tao lai, hoac tu go thong diep commit bang tay.
  echo.
  pause
  exit /b 1
)
echo [2/4] Co commit-msg-fix3.txt. OK.

REM ---- Buoc 3: them thay doi ------------------------------------------------
echo [3/4] git add...
git add -A backend
if errorlevel 1 (
  echo.
  echo [X] git add that bai. Doc thong bao ben tren.
  pause
  exit /b 1
)

REM ---- Buoc 4: commit ------------------------------------------------------
echo [4/4] git commit...
git commit -F commit-msg-fix3.txt
if errorlevel 1 (
  echo.
  echo [X] Commit that bai. File commit-msg-fix3.txt VAN CON de chay lai.
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  XONG. Lich su gan nhat:
echo ============================================================
git log --oneline -3
echo.
echo Tuy chon: day len GitHub bang   git push origin main
echo Sau khi push xong co the xoa: commit-msg-fix3.txt, commit-fix3.bat,
echo va hai file commit-*fix2* con sot lai tu dot truoc.
echo.
pause
