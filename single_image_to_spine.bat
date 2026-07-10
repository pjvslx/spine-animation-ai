@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
set "SCRIPTS=%ROOT%scripts"
set "VENV=%ROOT%.pipeline-venv"

echo ========================================
echo Single Image to Spine Pipeline
echo gpt-image-2 + OpenCV + template Spine JSON
echo ========================================
echo.

set "INPUT_IMAGE=%~1"
if "%INPUT_IMAGE%"=="" (
  set /p "INPUT_IMAGE=Drag or type character image path: "
)
set "INPUT_IMAGE=%INPUT_IMAGE:"=%"

if not exist "%INPUT_IMAGE%" (
  echo [ERROR] Input image not found: %INPUT_IMAGE%
  pause
  exit /b 1
)

if "%OPENAI_API_KEY%"=="" (
  echo OPENAI_API_KEY is not set in this terminal.
  set /p "OPENAI_API_KEY=Paste OPENAI_API_KEY: "
)

if "%OPENAI_API_KEY%"=="" (
  echo [ERROR] OPENAI_API_KEY is required.
  pause
  exit /b 1
)

for %%F in ("%INPUT_IMAGE%") do set "BASENAME=%%~nF"
set "OUT_DIR=%ROOT%generated_spine\%BASENAME%"
set "PARTS_DIR=%OUT_DIR%\parts"
set "ATLAS_DIR=%OUT_DIR%\atlas"
set "DEBUG_DIR=%OUT_DIR%\debug"
set "GENERATED_ATLAS=%OUT_DIR%\deconstructed_atlas.png"
set "LAYOUT=%OUT_DIR%\layout.json"
set "CONFIG=%OUT_DIR%\spine_config.json"
set "SKELETON=%OUT_DIR%\skeleton.json"
set "PREVIEW=%OUT_DIR%\preview.html"

echo.
echo Output directory:
echo   %OUT_DIR%
echo.

if not exist "%SCRIPTS%\split_character.py" (
  echo [ERROR] scripts folder not found: %SCRIPTS%
  pause
  exit /b 1
)

echo [1/8] Preparing Python environment...
if not exist "%VENV%\Scripts\python.exe" (
  python -m venv "%VENV%"
  if errorlevel 1 goto :fail
)
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :fail
"%VENV%\Scripts\python.exe" -m pip install requests opencv-python Pillow numpy
if errorlevel 1 goto :fail

if not exist "%OUT_DIR%" mkdir "%OUT_DIR%"
if not exist "%PARTS_DIR%" mkdir "%PARTS_DIR%"
if not exist "%ATLAS_DIR%" mkdir "%ATLAS_DIR%"

echo.
echo [2/8] Splitting character into body-part PNGs with gpt-image-2...
"%VENV%\Scripts\python.exe" "%SCRIPTS%\split_character.py" "%INPUT_IMAGE%" --output-dir "%PARTS_DIR%" --atlas-out "%GENERATED_ATLAS%"
if errorlevel 1 goto :fail

echo.
echo [3/8] Auto-positioning parts against the original image...
"%VENV%\Scripts\python.exe" "%SCRIPTS%\position_parts.py" --reference "%INPUT_IMAGE%" --parts "%PARTS_DIR%" --output "%LAYOUT%" --debug "%DEBUG_DIR%"
if errorlevel 1 goto :fail

echo.
echo [4/8] Converting layout to Spine skeleton config...
"%VENV%\Scripts\python.exe" "%SCRIPTS%\layout_to_spine_config.py" --layout "%LAYOUT%" --parts "%PARTS_DIR%" --output "%CONFIG%" --name "%BASENAME%"
if errorlevel 1 goto :fail

echo.
echo [5/8] Building Spine JSON...
"%VENV%\Scripts\python.exe" "%SCRIPTS%\build_spine_json.py" --config "%CONFIG%" --output "%SKELETON%"
if errorlevel 1 goto :fail

echo.
echo [6/8] Packing texture atlas...
"%VENV%\Scripts\python.exe" "%SCRIPTS%\make_atlas.py" --parts "%PARTS_DIR%" --output "%ATLAS_DIR%" --name skeleton
if errorlevel 1 goto :fail

echo.
echo [7/8] Generating self-contained HTML preview...
"%VENV%\Scripts\python.exe" "%SCRIPTS%\generate_spine_player.py" --skeleton "%SKELETON%" --atlas "%ATLAS_DIR%\skeleton.atlas" --atlas-image "%ATLAS_DIR%\skeleton.png" --output "%PREVIEW%"
if errorlevel 1 goto :fail

echo.
echo [8/8] Done.
echo.
echo Generated files:
echo   Parts:    %PARTS_DIR%
echo   JSON:     %SKELETON%
echo   Atlas:    %ATLAS_DIR%\skeleton.atlas
echo   PNG:      %ATLAS_DIR%\skeleton.png
echo   Preview:  %PREVIEW%
echo.
start "" "%PREVIEW%"
pause
exit /b 0

:fail
echo.
echo [ERROR] Pipeline failed. Check the messages above.
echo Output directory may contain partial files:
echo   %OUT_DIR%
pause
exit /b 1
