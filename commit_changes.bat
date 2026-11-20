@echo off
cd /d D:\e

echo ============================================
echo  ClubSphere - review changes before commit
echo ============================================
echo.
git status --short
echo.

set /p CONFIRM="Review the list above. Type YES to stage and commit: "
if /I not "%CONFIRM%"=="YES" (
    echo Aborted - nothing was staged or committed.
    pause
    exit /b 0
)

echo.
echo Staging all changes (gitignored files are excluded)...
git add -A

echo.
echo Creating commit...
git commit -m "docs: add deployment readiness report and latest changes"
if errorlevel 1 (
    echo.
    echo Commit failed - nothing was pushed.
    pause
    exit /b 1
)

echo.
set /p PUSH="Commit created. Push to origin? (y/N): "
if /I "%PUSH%"=="y" (
    git push
    if errorlevel 1 echo Push failed - run 'git push' manually.
)

echo.
pause
