@echo off
REM Crea l'eseguibile standalone (nessun Python richiesto per USARLO).
REM Da rilanciare ogni volta che il codice cambia -- serve Python +
REM PyInstaller SOLO per questo passaggio di build, non per usare l'exe.
REM Setup una tantum, se "python -m PyInstaller --version" fallisce:
REM     pip install pyinstaller
cd /d "%~dp0"

python -m PyInstaller --noconfirm --onedir --name "UmaLegacyLoopOptimizer" ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  app.py

if errorlevel 1 (
  echo.
  echo Build fallita, vedi errori sopra.
  pause
  exit /b 1
)

echo.
echo Copio i dati (data\, incluse le immagini in cache) accanto all'eseguibile...
xcopy /E /I /Y "data" "dist\UmaLegacyLoopOptimizer\data" >nul

echo Copio i leggimi (IT/EN)...
copy /Y "LEGGIMI.txt" "dist\UmaLegacyLoopOptimizer\LEGGIMI.txt" >nul
copy /Y "README.txt" "dist\UmaLegacyLoopOptimizer\README.txt" >nul

echo.
echo Fatto. Eseguibile in dist\UmaLegacyLoopOptimizer\UmaLegacyLoopOptimizer.exe
echo Per distribuirlo, copia l'INTERA cartella dist\UmaLegacyLoopOptimizer\.
pause
