@echo off
title AETERNA SINGULARITY // HIL APPARATUS & SHMEM IPC STACK
color 0A
echo ==============================================================================
echo 🔱 AETERNA SINGULARITY // HARDWARE-IN-THE-LOOP (HIL) COUPLING
echo Architect: Dimitar Prodromov (ID 101327948) ^| Pomorie HQ
echo Arena: Local\Aeterna_Unified_Singularity_Shmem (704 Bytes, AVX-512 Aligned)
echo ==============================================================================
echo.

echo [1/2] Starting Physical Apparatus HIL Simulator in background...
start "Aeterna Physical HIL Simulator" aeterna_apparatus_hil_simulator.exe

timeout /t 2 /nobreak >nul

echo [2/2] Launching Real-time Shmem Telemetry GUI Dashboard...
python aeterna_shmem_gui_dashboard.py

pause
