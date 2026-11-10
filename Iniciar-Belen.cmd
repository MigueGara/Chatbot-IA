@echo off
setlocal
pushd "%~dp0" || exit /b 1

set "PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Primero crea el entorno de Belen e instala sus dependencias.
    echo Desde la terminal de VS Code, en esta carpeta, ejecuta:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    popd
    exit /b 1
)

"%PYTHON%" -c "import chromadb, langchain_chroma, langchain_core, langchain_google_genai, langchain_groq, streamlit" >nul 2>&1
if errorlevel 1 (
    echo El entorno .venv no tiene todas las dependencias instaladas.
    echo Desde la terminal de VS Code, en esta carpeta, ejecuta:
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    popd
    exit /b 1
)

"%PYTHON%" -m streamlit run "%~dp0app.py" %*
set "resultado=%errorlevel%"
if not "%resultado%"=="0" pause
popd
exit /b %resultado%
