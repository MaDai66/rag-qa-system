@echo off
SETLOCAL ENABLEEXTENSIONS

REM
set UV_LINK_MODE=copy

REM Check if argument is dev mode
SET MODE=%1
IF "%MODE%"=="--dev" GOTO DEV
IF "%MODE%"=="-d" GOTO DEV
IF "%MODE%"=="dev" GOTO DEV
IF "%MODE%"=="development" GOTO DEV

:PROD
echo Starting langchat in [PRODUCTION] mode...
start uv run server.py
REM Wait for user to close
GOTO END

:DEV
echo Starting langchat in [DEVELOPMENT] mode...
start uv run server.py --reload
REM Wait for user to close
pause

:END
ENDLOCAL
