@echo off
rem Double-clic : ouvre MonteurOS Studio dans le navigateur. Glisse un dossier de rushs sur ce fichier pour l'utiliser.
rem Laisse cette fenetre ouverte pendant que tu travailles ; la fermer arrete le Studio.
setlocal
chcp 65001 >nul
set "HERE=%~dp0"
set "RUSHS=%~1"
if "%RUSHS%"=="" set "RUSHS=%HERE%rushs"
if not exist "%RUSHS%" mkdir "%RUSHS%"
echo MonteurOS Studio - rushs : %RUSHS%
call "%HERE%bin\monteur.cmd" studio --root "%RUSHS%"
echo.
echo Le Studio s'est arrete. Appuie sur une touche pour fermer.
pause >nul
