@echo off
setlocal
pushd "%~dp0" || exit /b 1

if not exist ".venv\Scripts\python.exe" (
    echo Primero crea el entorno de Belen e instala sus dependencias.
    echo Desde la terminal de VS Code, en esta carpeta, ejecuta:
    echo   python -m venv .venv
    echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    popd
    exit /b 1
)

".venv\Scripts\python.exe" -m streamlit run app.py %*
set "resultado=%errorlevel%"
if not "%resultado%"=="0" pause
popd
exit /b %resultado%
