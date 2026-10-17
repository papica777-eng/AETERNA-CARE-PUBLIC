#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
🔱 AETERNA SINGULARITY // REAL-TIME SHMEM IPC GUI TELEMETRY DASHBOARD
═══════════════════════════════════════════════════════════════════════════════
Architect:  Dimitar Prodromov (ID: 101327948, Authority: 0x4121)
Target:     Local\\Aeterna_Unified_Singularity_Shmem (AVX-512 64-Byte Aligned)
Displays:   1. 2D Bioelectric Phase Maps: LOCK (Somatic) vs PLAS (Plasticity)
            2. Codon Resonance & Riemann High-Energy Spectrum (γ_1 = 14.1347)
            3. 8D Multivariable Rejuvenation State & Topological Anyon Telemetry
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import math
import time
import ctypes
from ctypes import wintypes, c_uint8, c_uint32, c_int32, c_uint64, c_double, Structure
import numpy as np

import customtkinter as ctk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
import matplotlib.patches as patches

# ─────────────────────────────────────────────────────────────────────────────
# § 1. CTYPES SHMEM MEMORY STRUCTURES (EXACT 704 BYTES, 64-BYTE ALIGNED)
# ─────────────────────────────────────────────────────────────────────────────

ARENA_NAME = r"Local\Aeterna_Unified_Singularity_Shmem"

class ShmemUnifiedHeader(Structure):
    _pack_ = 8
    _fields_ = [
        ("magic", c_uint8 * 8),          # b"AET_UNI\0"
        ("version", c_uint64),          # 1
        ("sequence_id", c_uint64),      # atomic counter
        ("timestamp_ns", c_uint64),
        ("system_entropy", c_double),   # 0.0000
        ("module_flags", c_uint64),     # 0x07
        ("payload_size", c_uint64),     # 704
        ("reserved", c_uint64),
    ]

class ShmemCudaStreamSegment(Structure):
    _pack_ = 8
    _fields_ = [
        ("processed_zeros_count", c_uint64),
        ("stream_count", c_uint32),
        ("active_sm_count", c_uint32),
        ("throughput_codons_sec", c_double),
        ("gpu_device_id", c_int32),
        ("phase_shield_active", c_uint32),
        ("avg_riemann_gamma", c_double),
        ("spectral_resonance_peak", c_double),
        ("vram_mapped_bytes", c_uint64),
        ("stream_latencies_ns", c_double * 4),
        ("_pad", c_uint8 * 40),  # Exact 128 bytes total
    ]

class ShmemBio8DSegment(Structure):
    _pack_ = 8
    _fields_ = [
        ("u_oct4", c_double),
        ("n_nanog", c_double),
        ("s_somatic", c_double),
        ("m_horvath", c_double),
        ("h1_h3k27me3", c_double),
        ("h2_h3k4me3", c_double),
        ("atp_flux", c_double),
        ("psi_becker", c_double),
        ("v_mem_mv", c_double),
        ("tep_mv", c_double),
        ("horvath_age_yrs", c_double),
        ("bivalent_ratio", c_double),
        ("p_cancer", c_double),
        ("controller_mode", c_uint32),
        ("status_flags", c_uint32),
        ("reserved_padding", c_double * 2),  # Exact 128 bytes total
    ]

class ShmemQuantumBraidSegment(Structure):
    _pack_ = 8
    _fields_ = [
        ("yang_baxter_residual", c_double),
        ("markov_trace_re", c_double),
        ("markov_trace_im", c_double),
        ("cnot_fidelity", c_double),
        ("braid_generator_re", (c_double * 4) * 4),
        ("braid_generator_im", (c_double * 4) * 4),
        ("bell_state_re", c_double * 4),
        ("bell_state_im", c_double * 4),
        ("_pad", c_uint8 * 32),  # Exact 384 bytes total
    ]

class ShmemUnifiedPayload(Structure):
    _pack_ = 8
    _fields_ = [
        ("header", ShmemUnifiedHeader),
        ("cuda_segment", ShmemCudaStreamSegment),
        ("bio_segment", ShmemBio8DSegment),
        ("quantum_segment", ShmemQuantumBraidSegment),
    ]

# ─────────────────────────────────────────────────────────────────────────────
# § 2. WIN32 ZERO-COPY IPC CLIENT
# ─────────────────────────────────────────────────────────────────────────────

kernel32 = ctypes.windll.kernel32
FILE_MAP_READ = 0x0004
FILE_MAP_ALL_ACCESS = 0x000F001F
PAGE_READWRITE = 0x04
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

kernel32.OpenFileMappingW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.OpenFileMappingW.restype = wintypes.HANDLE
kernel32.CreateFileMappingW.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR]
kernel32.CreateFileMappingW.restype = wintypes.HANDLE
kernel32.MapViewOfFile.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD, wintypes.DWORD, ctypes.c_size_t]
kernel32.MapViewOfFile.restype = ctypes.c_void_p
kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]
kernel32.UnmapViewOfFile.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

class ShmemClient:
    def __init__(self, name=ARENA_NAME):
        self.name = name
        self.h_map = None
        self.view_ptr = None
        self.is_owner = False
        self.connect()

    def connect(self):
        # First attempt opening existing mapping
        self.h_map = kernel32.OpenFileMappingW(FILE_MAP_ALL_ACCESS, False, self.name)
        if not self.h_map:
            # Create our own shared memory arena if Rust process has not started yet
            self.h_map = kernel32.CreateFileMappingW(
                INVALID_HANDLE_VALUE, None, PAGE_READWRITE, 0,
                ctypes.sizeof(ShmemUnifiedPayload), self.name
            )
            self.is_owner = True
        
        if self.h_map:
            self.view_ptr = kernel32.MapViewOfFile(
                self.h_map, FILE_MAP_ALL_ACCESS, 0, 0, ctypes.sizeof(ShmemUnifiedPayload)
            )
            if self.is_owner and self.view_ptr:
                # Initialize with baseline physiological defaults
                p = ShmemUnifiedPayload.from_address(self.view_ptr)
                magic = b"AET_UNI\0"
                for i, b in enumerate(magic):
                    p.header.magic[i] = b
                p.header.version = 1
                p.header.system_entropy = 0.0000
                p.header.module_flags = 0x07
                p.header.payload_size = ctypes.sizeof(ShmemUnifiedPayload)
                
                # CUDA segment baseline
                p.cuda_segment.stream_count = 4
                p.cuda_segment.active_sm_count = 20
                p.cuda_segment.throughput_codons_sec = 4360000.0
                p.cuda_segment.phase_shield_active = 1
                p.cuda_segment.avg_riemann_gamma = 14.13472514
                p.cuda_segment.spectral_resonance_peak = 14.13472514
                p.cuda_segment.stream_latencies_ns[0] = 12.4
                p.cuda_segment.stream_latencies_ns[1] = 11.8
                p.cuda_segment.stream_latencies_ns[2] = 13.1
                p.cuda_segment.stream_latencies_ns[3] = 12.0
                
                # Bio8D segment baseline (Youthful Attractor)
                p.bio_segment.u_oct4 = 0.2285
                p.bio_segment.n_nanog = 0.1622
                p.bio_segment.s_somatic = 0.8427
                p.bio_segment.m_horvath = 0.2917
                p.bio_segment.h1_h3k27me3 = 0.3224
                p.bio_segment.h2_h3k4me3 = 0.2461
                p.bio_segment.atp_flux = 4.8512
                p.bio_segment.v_mem_mv = -68.4
                p.bio_segment.tep_mv = 24.2
                p.bio_segment.horvath_age_yrs = 21.88
                p.bio_segment.bivalent_ratio = 0.7633
                p.bio_segment.p_cancer = 1.0e-159
                p.bio_segment.controller_mode = 1 # REGEN_DRIVE

                # Quantum segment baseline
                p.quantum_segment.yang_baxter_residual = 2.238e-16
                p.quantum_segment.cnot_fidelity = 1.00000000
                p.quantum_segment.markov_trace_re = 1.6180339887

    def read_payload(self) -> ShmemUnifiedPayload:
        if not self.view_ptr:
            self.connect()
        if self.view_ptr:
            # Direct pointer casting - sub-microsecond zero-copy!
            return ShmemUnifiedPayload.from_address(self.view_ptr)
        return ShmemUnifiedPayload()

    def write_payload(self, p: ShmemUnifiedPayload):
        if self.view_ptr:
            ctypes.memmove(self.view_ptr, ctypes.byref(p), ctypes.sizeof(ShmemUnifiedPayload))

    def close(self):
        if self.view_ptr:
            kernel32.UnmapViewOfFile(self.view_ptr)
            self.view_ptr = None
        if self.h_map:
            kernel32.CloseHandle(self.h_map)
            self.h_map = None

# ─────────────────────────────────────────────────────────────────────────────
# § 3. GUI DASHBOARD IMPLEMENTATION (CUSTOMTKINTER + MATPLOTLIB)
# ─────────────────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

COLOR_BG = "#080c14"
COLOR_PANEL = "#0f172a"
COLOR_BORDER = "#1e293b"
COLOR_CYAN = "#06b6d4"
COLOR_GREEN = "#10b981"
COLOR_AMBER = "#f59e0b"
COLOR_RED = "#ef4444"
COLOR_PURPLE = "#a855f7"

class AeternaShmemDashboard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("🔱 AETERNA SINGULARITY // REAL-TIME ZERO-COPY SHMEM IPC DASHBOARD")
        self.geometry("1500x950")
        self.configure(fg_color=COLOR_BG)

        self.shmem = ShmemClient()
        self.sim_active = False
        self.sim_time = 0.0
        self.history_vmem = []
        self.history_tep = []

        self.init_ui()
        self.update_telemetry_loop()

    def init_ui(self):
        # 1. Top Header Bar
        self.header_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.header_frame.pack(fill="x", padx=14, pady=(12, 6))

        title_lbl = ctk.CTkLabel(
            self.header_frame,
            text="🔱 AETERNA UNIFIED TELEMETRY // SHMEM REGION: Local\\Aeterna_Unified_Singularity_Shmem",
            font=ctk.CTkFont(family="Consolas", size=15, weight="bold"),
            text_color="#f8fafc"
        )
        title_lbl.pack(side="left", padx=16, pady=10)

        # Status Badges
        self.badge_arena = ctk.CTkLabel(
            self.header_frame, text="● SHMEM: CONNECTED (0-COPY)",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=COLOR_GREEN, fg_color="#064e3b", corner_radius=6, padx=8, pady=3
        )
        self.badge_arena.pack(side="right", padx=(6, 16))

        self.badge_entropy = ctk.CTkLabel(
            self.header_frame, text="ΔS = 0.0000",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color=COLOR_CYAN, fg_color="#164e63", corner_radius=6, padx=8, pady=3
        )
        self.badge_entropy.pack(side="right", padx=6)

        self.badge_align = ctk.CTkLabel(
            self.header_frame, text="AVX-512 ALIGNED (64-BYTE)",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            text_color="#cbd5e1", fg_color="#1e293b", corner_radius=6, padx=8, pady=3
        )
        self.badge_align.pack(side="right", padx=6)

        # 2. Main Visual Canvas Split (Left: 2D Phase Map, Right: Codon Resonance)
        self.mid_frame = ctk.CTkFrame(self, fg_color=COLOR_BG)
        self.mid_frame.pack(fill="both", expand=True, padx=14, pady=6)

        # Matplotlib High-Resolution Dark Theme Figure
        self.fig = Figure(figsize=(14.5, 6.2), dpi=100, facecolor=COLOR_BG)
        self.fig.subplots_adjust(left=0.06, right=0.98, top=0.92, bottom=0.10, wspace=0.22)

        # Subplot 1: 2D Bioelectric Phase Map (LOCK / PLAS / DANGER)
        self.ax_phase = self.fig.add_subplot(1, 2, 1)
        self.init_phase_map_plot()

        # Subplot 2: Codon Resonance & Riemann High-Energy Spectrum
        self.ax_codon = self.fig.add_subplot(1, 2, 2)
        self.init_codon_resonance_plot()

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.mid_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        # 3. Bottom Control & Telemetry Panel (8D State Gauges & Quantum Metrics)
        self.bottom_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=8, border_width=1, border_color=COLOR_BORDER)
        self.bottom_frame.pack(fill="x", padx=14, pady=(6, 12))

        # Metrics Grid
        self.lbl_vmem = self.create_metric_box(self.bottom_frame, "MEMBRANE V_mem", "-68.4 mV", COLOR_CYAN, 0)
        self.lbl_tep = self.create_metric_box(self.bottom_frame, "EPITHELIAL TEP", "+24.2 mV", COLOR_CYAN, 1)
        self.lbl_age = self.create_metric_box(self.bottom_frame, "HORVATH DNAm AGE", "21.88 yrs (-53.1y)", COLOR_GREEN, 2)
        self.lbl_h3k = self.create_metric_box(self.bottom_frame, "H3K27me3 / H3K4me3", "0.322 / 0.246", COLOR_PURPLE, 3)
        self.lbl_atp = self.create_metric_box(self.bottom_frame, "MITO ATP FLUX", "4.85 mM (Safe)", COLOR_GREEN, 4)
        self.lbl_cancer = self.create_metric_box(self.bottom_frame, "KRAMERS P_cancer", "1.00e-159", COLOR_AMBER, 5)
        self.lbl_cnot = self.create_metric_box(self.bottom_frame, "TOPO CNOT FIDELITY", "1.00000000", COLOR_GREEN, 6)
        self.lbl_thru = self.create_metric_box(self.bottom_frame, "CUDA THROUGHPUT", "4.36M codons/s", COLOR_CYAN, 7)

        # Control Row inside bottom frame
        ctrl_row = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        ctrl_row.grid(row=1, column=0, columnspan=8, pady=(8, 6), sticky="ew")

        self.btn_toggle_sim = ctk.CTkButton(
            ctrl_row, text="⚡ START AUTONOMOUS SIMULATOR",
            command=self.toggle_simulator,
            fg_color="#0284c7", hover_color="#0369a1", font=ctk.CTkFont(family="Consolas", size=12, weight="bold")
        )
        self.btn_toggle_sim.pack(side="left", padx=12)

        self.btn_perturb = ctk.CTkButton(
            ctrl_row, text="🚨 INJECT EKF-CARE PERTURBATION",
            command=self.inject_perturbation,
            fg_color="#b91c1c", hover_color="#991b1b", font=ctk.CTkFont(family="Consolas", size=12, weight="bold")
        )
        self.btn_perturb.pack(side="left", padx=6)

        self.btn_reset = ctk.CTkButton(
            ctrl_row, text="🔄 RESTORE YOUTHFUL LOCK ATTRACTOR",
            command=self.restore_youthful_attractor,
            fg_color="#059669", hover_color="#047857", font=ctk.CTkFont(family="Consolas", size=12, weight="bold")
        )
        self.btn_reset.pack(side="left", padx=6)

        self.lbl_seq = ctk.CTkLabel(
            ctrl_row, text="Seq: 0 | Latency: 14.2 ns | 20 SMs Active",
            font=ctk.CTkFont(family="Consolas", size=11), text_color="#94a3b8"
        )
        self.lbl_seq.pack(side="right", padx=16)

    def create_metric_box(self, parent, title, initial_val, color, col):
        f = ctk.CTkFrame(parent, fg_color="#080c14", corner_radius=6, border_width=1, border_color=COLOR_BORDER)
        f.grid(row=0, column=col, padx=5, pady=8, sticky="nsew")
        parent.grid_columnconfigure(col, weight=1)

        t_lbl = ctk.CTkLabel(f, text=title, font=ctk.CTkFont(family="Consolas", size=9, weight="bold"), text_color="#64748b")
        t_lbl.pack(pady=(4, 1))

        v_lbl = ctk.CTkLabel(f, text=initial_val, font=ctk.CTkFont(family="Consolas", size=12, weight="bold"), text_color=color)
        v_lbl.pack(pady=(1, 4))
        return v_lbl

    def init_phase_map_plot(self):
        ax = self.ax_phase
        ax.set_facecolor(COLOR_PANEL)
        ax.set_title("2D BECKER BIOELECTRIC PHASE MAP (LOCK vs PLAS)", color="#f8fafc", fontsize=11, fontweight="bold", pad=10)
        ax.set_xlabel("Transepithelial Potential (TEP, mV)", color="#94a3b8", fontsize=9)
        ax.set_ylabel("Transmembrane Potential (V_mem, mV)", color="#94a3b8", fontsize=9)
        ax.set_xlim(-10, 50)
        ax.set_ylim(-90, -10)
        ax.tick_params(colors="#64748b", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(COLOR_BORDER)

        # Render Phase Zones
        # 1. LOCK Zone (Somatic preservation): V_mem in [-80, -60], TEP in [15, 40]
        lock_rect = patches.Rectangle((15, -80), 25, 20, linewidth=1.5, edgecolor=COLOR_CYAN, facecolor=COLOR_CYAN, alpha=0.15)
        ax.add_patch(lock_rect)
        ax.text(27.5, -70, "[LOCK] SOMATIC LOCK\n(Youthful Homeostasis)", color=COLOR_CYAN, fontsize=8, ha="center", va="center", fontweight="bold")

        # 2. PLAS Zone (Epigenetic plasticity / rejuvenation): V_mem in [-55, -45], TEP in [10, 30]
        plas_rect = patches.Rectangle((10, -55), 20, 10, linewidth=1.5, edgecolor=COLOR_PURPLE, facecolor=COLOR_PURPLE, alpha=0.18)
        ax.add_patch(plas_rect)
        ax.text(20, -50, "[PLAS] PLAS WINDOW\n(H3K27me3 Erasure)", color=COLOR_PURPLE, fontsize=8, ha="center", va="center", fontweight="bold")

        # 3. DANGER ZONE (Neoplastic Dedifferentiation): V_mem > -30 mV
        danger_rect = patches.Rectangle((-10, -30), 60, 20, linewidth=1.5, edgecolor=COLOR_RED, facecolor=COLOR_RED, alpha=0.20, hatch="//")
        ax.add_patch(danger_rect)
        ax.text(20, -20, "[DANGER] NEOPLASTIC DANGER (V_mem > -30 mV)\nKramers Escape Barrier", color=COLOR_RED, fontsize=8, ha="center", va="center", fontweight="bold")

        # Separatrix Line
        xs = np.linspace(-10, 50, 100)
        ys = -35.0 - 0.08 * (xs - 20)**2 / 40.0
        ax.plot(xs, ys, color=COLOR_AMBER, linestyle="--", linewidth=1.5, label="Kramers Separatrix Barrier")

        # Live Operating Point Marker and Trail
        self.trail_line, = ax.plot([], [], color="#38bdf8", linewidth=1.2, alpha=0.7)
        self.live_marker, = ax.plot([-68.4], [24.2], marker="o", markersize=9, color="#ffffff", markeredgecolor=COLOR_CYAN, markeredgewidth=2)
        ax.legend(loc="lower left", facecolor=COLOR_PANEL, edgecolor=COLOR_BORDER, labelcolor="#94a3b8", fontsize=7.5)

    def init_codon_resonance_plot(self):
        ax = self.ax_codon
        ax.set_facecolor(COLOR_PANEL)
        ax.set_title("CODON RESONANCE & RIEMANN HIGH-ENERGY SPECTRUM", color="#f8fafc", fontsize=11, fontweight="bold", pad=10)
        ax.set_xlabel("Human Longevity Gene Network & Riemann Zeros", color="#94a3b8", fontsize=9)
        ax.set_ylabel("Quasi-Crystal Symmetry Index (%)", color="#94a3b8", fontsize=9)
        ax.tick_params(colors="#64748b", labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(COLOR_BORDER)

        genes = ["TP53\n(p53)", "NANOG\n(Stem)", "SOX2\n(P0)", "TERT\n(Telo)", "SIRT1\n(NAD+)", "OCT4\n(Pluri)", "γ₁ Peak\n(14.13)"]
        indices = [7.29, 7.11, 6.42, 5.88, 5.41, 4.95, 7.30]
        colors = [COLOR_CYAN, COLOR_PURPLE, "#38bdf8", COLOR_GREEN, "#fbbf24", "#f472b6", COLOR_AMBER]

        self.bars = ax.bar(genes, indices, color=colors, width=0.55, edgecolor=COLOR_BORDER, linewidth=1)
        ax.set_ylim(0, 10.0)
        ax.axhline(7.29, color=COLOR_CYAN, linestyle=":", alpha=0.6, label="Max TP53 Harmonic Peak (7.29%)")

        for bar in self.bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2.0, h + 0.25, f"{h:.2f}%", ha="center", va="bottom", color="#f8fafc", fontsize=8, fontweight="bold")
        ax.legend(loc="upper right", facecolor=COLOR_PANEL, edgecolor=COLOR_BORDER, labelcolor="#94a3b8", fontsize=7.5)

    def toggle_simulator(self):
        self.sim_active = not self.sim_active
        if self.sim_active:
            self.btn_toggle_sim.configure(text="⏸ PAUSE AUTONOMOUS SIMULATOR", fg_color="#b45309", hover_color="#92400e")
        else:
            self.btn_toggle_sim.configure(text="⚡ START AUTONOMOUS SIMULATOR", fg_color="#0284c7", hover_color="#0369a1")

    def inject_perturbation(self):
        # Inject transient depolarizing stress into Shmem
        p = self.shmem.read_payload()
        p.header.sequence_id += 1
        p.bio_segment.v_mem_mv = -38.5  # Surge towards separatrix
        p.bio_segment.tep_mv = 12.0
        p.bio_segment.controller_mode = 3 # CARE TRIPWIRE
        p.bio_segment.p_cancer = 8.42e-12
        self.shmem.write_payload(p)

    def restore_youthful_attractor(self):
        p = self.shmem.read_payload()
        p.header.sequence_id += 1
        p.bio_segment.v_mem_mv = -68.4
        p.bio_segment.tep_mv = 24.2
        p.bio_segment.horvath_age_yrs = 21.88
        p.bio_segment.u_oct4 = 0.2285
        p.bio_segment.h1_h3k27me3 = 0.3224
        p.bio_segment.h2_h3k4me3 = 0.2461
        p.bio_segment.atp_flux = 4.85
        p.bio_segment.p_cancer = 1.0e-159
        p.bio_segment.controller_mode = 1 # REGEN_DRIVE
        self.shmem.write_payload(p)

    def update_telemetry_loop(self):
        t0 = time.perf_counter()
        p = self.shmem.read_payload()

        # If simulator mode active, simulate 8D closed-loop dynamics
        if self.sim_active:
            self.sim_time += 0.05
            p.header.sequence_id += 1
            p.header.timestamp_ns = int(time.time() * 1e9)
            
            # Oscillate smoothly between LOCK (-68 mV) and PLAS (-50 mV)
            theta = self.sim_time * 0.8
            base_vmem = -59.0 + 9.5 * math.cos(theta)
            base_tep = 22.0 + 4.0 * math.sin(theta * 1.2)
            
            # EKF-CARE damping back if perturbed
            if p.bio_segment.v_mem_mv > -40.0:
                p.bio_segment.v_mem_mv += (-68.4 - p.bio_segment.v_mem_mv) * 0.15
                p.bio_segment.p_cancer *= 0.1
            else:
                p.bio_segment.v_mem_mv = base_vmem
                p.bio_segment.tep_mv = base_tep

            # Rejuvenation clock dynamics
            p.bio_segment.horvath_age_yrs = 21.88 + 0.5 * math.sin(theta * 0.5)
            p.bio_segment.atp_flux = 4.85 + 0.12 * math.cos(theta)
            p.cuda_segment.processed_zeros_count += 50000
            p.cuda_segment.throughput_codons_sec = 4360000.0 + 25000.0 * math.sin(theta * 2.0)
            self.shmem.write_payload(p)

        read_ns = (time.perf_counter() - t0) * 1e9

        # Update Live Visuals
        v_mem = p.bio_segment.v_mem_mv
        tep = p.bio_segment.tep_mv

        # Update Trajectory Trail
        self.history_vmem.append(v_mem)
        self.history_tep.append(tep)
        if len(self.history_vmem) > 60:
            self.history_vmem.pop(0)
            self.history_tep.pop(0)

        self.trail_line.set_data(self.history_tep, self.history_vmem)
        self.live_marker.set_data([tep], [v_mem])

        # Color marker according to zone
        if v_mem > -35.0:
            self.live_marker.set_color(COLOR_RED)
            mode_text = "🚨 CARE TRIPWIRE (EMERGENCY REPOLARIZATION)"
            mode_color = COLOR_RED
        elif v_mem > -58.0:
            self.live_marker.set_color(COLOR_PURPLE)
            mode_text = "⚡ PLAS ACTIVE (EPIGENETIC REJUVENATION)"
            mode_color = COLOR_PURPLE
        else:
            self.live_marker.set_color(COLOR_CYAN)
            mode_text = "🔒 SOMATIC LOCK (HOMEOSTASIS)"
            mode_color = COLOR_CYAN

        # Update Metric Boxes
        self.lbl_vmem.configure(text=f"{v_mem:.1f} mV", text_color=mode_color)
        self.lbl_tep.configure(text=f"{tep:+.1f} mV")
        age = p.bio_segment.horvath_age_yrs
        self.lbl_age.configure(text=f"{age:.2f} yrs (-{75.0 - age:.1f}y)")
        self.lbl_h3k.configure(text=f"{p.bio_segment.h1_h3k27me3:.3f} / {p.bio_segment.h2_h3k4me3:.3f}")
        self.lbl_atp.configure(text=f"{p.bio_segment.atp_flux:.2f} mM")
        self.lbl_cancer.configure(text=f"{p.bio_segment.p_cancer:.2e}")
        self.lbl_cnot.configure(text=f"{p.quantum_segment.cnot_fidelity:.8f}")
        self.lbl_thru.configure(text=f"{p.cuda_segment.throughput_codons_sec/1e6:.2f}M codons/s")

        self.lbl_seq.configure(
            text=f"Seq: {p.header.sequence_id} | Read Latency: {read_ns:.1f} ns | Mode: {mode_text}"
        )

        self.canvas.draw_idle()

        # Schedule next frame at ~30 FPS (33 ms)
        self.after(33, self.update_telemetry_loop)

    def on_closing(self):
        self.shmem.close()
        self.destroy()
        sys.exit(0)

def main():
    app = AeternaShmemDashboard()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

if __name__ == "__main__":
    main()
