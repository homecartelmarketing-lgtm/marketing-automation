@echo off
if exist "%LOCALAPPDATA%\Programs\Python\Python311\Scripts\pip.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python311\Scripts\pip.exe" %*
) else if exist "%LOCALAPPDATA%\Programs\Python\Python312\Scripts\pip.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python312\Scripts\pip.exe" %*
) else if exist "%LOCALAPPDATA%\Programs\Python\Python313\Scripts\pip.exe" (
    "%LOCALAPPDATA%\Programs\Python\Python313\Scripts\pip.exe" %*
) else (
    pip %*
)

