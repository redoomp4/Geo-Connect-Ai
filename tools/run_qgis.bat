@echo off
set "QGIS_ROOT=C:\Program Files\QGIS 4.2.1"
set "OSGEO4W_ROOT=%QGIS_ROOT%"
set "PYTHONHOME=%QGIS_ROOT%\apps\Python312"
set "PYTHONUTF8=1"
set "PYTHONPATH=%QGIS_ROOT%\apps\qgis\python;%~dp0..;%PYTHONPATH%"
set "PATH=%QGIS_ROOT%\apps\qgis\bin;%QGIS_ROOT%\apps\qt6\bin;%QGIS_ROOT%\apps\Python312;%QGIS_ROOT%\apps\Python312\Scripts;%QGIS_ROOT%\bin;%PATH%"
set "QGIS_PREFIX_PATH=%QGIS_ROOT:\=/%/apps/qgis"
set "QT_PLUGIN_PATH=%QGIS_ROOT%\apps\qgis\qtplugins;%QGIS_ROOT%\apps\qt6\plugins"
set "GDAL_DATA=%QGIS_ROOT%\apps\gdal\share\gdal"
set "PROJ_DATA=%QGIS_ROOT%\share\proj"

"%QGIS_ROOT%\bin\python3.exe" %*
