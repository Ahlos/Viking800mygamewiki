@echo off
setlocal
cd /d "%~dp0"
set "WIKI_OUT=wiki-demo-%RANDOM%-%RANDOM%"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 wiki_generator.py demo_FULLSAVE --output "%WIKI_OUT%"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python hittades inte. Las README.md och installera Python 3.10 eller senare.
        pause
        exit /b 2
    )
    python wiki_generator.py demo_FULLSAVE --output "%WIKI_OUT%"
)
if errorlevel 1 (
    echo Genereringen misslyckades. Se meddelandet ovan och README.md.
    pause
    exit /b 2
)
start "" "%WIKI_OUT%\index.html"
echo Wikin finns i %WIKI_OUT%
pause
