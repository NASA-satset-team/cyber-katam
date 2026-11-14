#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CYBER-KATAM: Bare-Field Erosion & Heat Shock Index (BF-EHSI) & Risk Integral Engine
Deliverable: LEADER-03 (bf_ehsi_engine.py)
Target Domain: Soil Physics, Vertisol Desiccation Mechanics, RUSLE & GPM IMERG Extremes
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, asdict
from typing import List, Optional
import numpy as np


@dataclass(frozen=True)
class BFEHSIConstants:
    """Konstanta fisika tanah sesuai Spesifikasi Teknis CYBER-KATAM Bab 2.2 & Bab 3.3."""
    alpha_thermal: float = 0.40          # Bobot degradasi termal-biologis
    beta_kinetic: float = 0.60           # Bobot erosi kinetik-mekanis
    lst_crit_c: float = 42.0             # Ambang suhu tanah kritis kematian mikroba (Celsius)
    r_crit_mm_hr: float = 50.0           # Ambang hujan ekstrem persentil ke-95 GPM IMERG (mm/jam)
    r_norm_mm_hr: float = 35.0           # Faktor normalisasi intensitas hujan monsun (mm/jam)
    bsi_bare_threshold: float = 0.30     # Ambang batas tanah terbuka kritis (BSI > 0.30)
    k_rusle_vertisol: float = 0.038      # Faktor erodibilitas tanah aluvial/vertisol (t.ha.h/(ha.MJ.mm))
    twi_max_banyumas: float = 18.5       # Topographic Wetness Index maksimum lanskap Serayu-Pantura
    d_tolerance_limit: float = 0.45      # Ambang batas toleransi integral degradasi D_i


@dataclass
class HLSReflectanceStep:
    """Data harian/dekadal per langkah waktu t pada jendela lahan bera."""
    day_index: int
    rho_nir: float             # Band NIR HLS v2.0 (B05 pada L30 / B8A pada S30)
    rho_swir1: float           # Band SWIR1 HLS v2.0 (B06 pada L30 / B11 pada S30)
    rho_swir2: float           # Band SWIR2 HLS v2.0 (B07 pada L30 / B12 pada S30)
    lst_ecostress_c: float     # Suhu radiometrik permukaan tanah ECOSTRESS (Celsius)
    r_gpm_max_mm_hr: float     # Intensitas hujan maksimum harian GPM IMERG (mm/jam)
    sm_surface_m3m3: float     # Lengas permukaan tanah untuk estimasi rekahan desikasi (m3/m3)
    delta_t_days: float = 1.0  # Durasi langkah integrasi waktu (hari)


@dataclass
class BFEHSIOutputContract:
    """Keluaran komprehensif evaluasi bahaya lahan bera dan erosi."""
    h3_index: str
    landscape_zone: str
    slope_deg: float
    slope_pct: float
    mbsi_latest: float
    bare_soil_fraction_b: float
    is_bare_field_exposed: bool
    desiccation_crack_depth_cm: float
    preferential_leaching_risk: str
    hydrological_connectivity_c: float
    bf_ehsi_instantaneous: float
    cumulative_risk_integral_di: float
    estimated_sheet_erosion_ton_ha_yr: float
    exceeds_erosion_tolerance: bool
    emergency_cover_crop_mandate: str


class BFEHSIEngine:
    """
    Mesin Perhitungan Bare-Field Erosion & Heat Shock Index (BF-EHSI)
    serta Integral Keterpaparan Risiko Kumulatif (D_i).
    """

    def __init__(self, constants: Optional[BFEHSIConstants] = None) -> None:
        self.c = constants or BFEHSIConstants()

    @staticmethod
    def compute_mbsi(rho_swir1: float, rho_swir2: float, rho_nir: float) -> float:
        """
        Bab 3.3: Modified Bare Soil Index (MBSI) dari citra HLS 30 m:
        MBSI = (rho_SWIR1 - rho_SWIR2 - rho_NIR) / (rho_SWIR1 + rho_SWIR2 + rho_NIR)
        """
        denom = rho_swir1 + rho_swir2 + rho_nir
        if abs(denom) < 1e-8:
            return 0.0
        return float((rho_swir1 - rho_swir2 - rho_nir) / denom)

    def mbsi_to_bare_fraction(self, mbsi: float) -> float:
        """
        Memetakan nilai MBSI [-1, 1] menjadi fraksi tanah terbuka terverifikasi b_{it} in [0, 1].
        Nilai MBSI > -0.05 mulai menunjukkan pembukaan tajuk; MBSI >= 0.25 menunjukkan bera penuh.
        """
        b_it = (mbsi + 0.15) / 0.45
        return float(np.clip(b_it, 0.0, 1.0))

    @staticmethod
    def estimate_desiccation_crack_depth_cm(
        sm_surface: float,
        clay_fraction: float = 0.52,
        theta_shrinkage_limit: float = 0.24,
    ) -> float:
        """
        Bab 2.2: Pemodelan fisika penyusutan lempung montmorillonit/vertisol.
        Ketika lengas tanah turun di bawah batas susut, terbentuk celah vertikal >60 cm.
        """
        if sm_surface >= theta_shrinkage_limit:
            return 0.0
        moisture_deficit_ratio = (theta_shrinkage_limit - sm_surface) / theta_shrinkage_limit
        # Kedalaman maksimum pada vertisol murni (clay ~0.55) mencapai 65-75 cm
        crack_depth = 85.0 * clay_fraction * (moisture_deficit_ratio ** 0.85) * 1.65
        return float(np.clip(crack_depth, 0.0, 75.0))

    def compute_hydrological_connectivity(self, slope_deg: float, twi: float) -> float:
        """
        Bab 3.3: Vektor konektivitas hidrologis permukaan mikro berbasis kemiringan SRTM:
        c_{it} = sin(theta_SRTM) * (1 + TWI / TWI_max)
        """
        theta_rad = math.radians(max(0.1, min(slope_deg, 60.0)))
        twi_norm = np.clip(twi / self.c.twi_max_banyumas, 0.0, 1.5)
        return float(math.sin(theta_rad) * (1.0 + twi_norm))

    def compute_instantaneous_bf_ehsi(
        self,
        b_it: float,
        lst_c: float,
        slope_deg: float,
        r_gpm_95th_mm_hr: float,
    ) -> float:
        """
        Bab 3.3: Indeks Bahaya Instan Lahan Bera (BF-EHSI):
        BF-EHSI = b_{it} * [ alpha * (LST / LST_crit) + beta * tan(theta_SRTM) * (R_GPM,95th / R_norm) ]
        """
        theta_rad = math.radians(max(0.1, min(slope_deg, 60.0)))
        thermal_term = self.c.alpha_thermal * (max(0.0, lst_c) / self.c.lst_crit_c)
        kinetic_term = (
            self.c.beta_kinetic
            * math.tan(theta_rad)
            * (max(0.0, r_gpm_95th_mm_hr) / self.c.r_norm_mm_hr)
        )
        bf_ehsi = b_it * (thermal_term + kinetic_term)
        return float(np.clip(bf_ehsi, 0.0, 2.5))

    def evaluate_fallow_window(
        self,
        h3_index: str,
        landscape_zone: str,
        slope_deg: float,
        twi: float,
        time_series: List[HLSReflectanceStep],
        clay_fraction: float = 0.52,
        k_rusle_override: Optional[float] = None,
    ) -> BFEHSIOutputContract:
        """
        Menghitung Integral Keterpaparan Risiko Kumulatif D_i sepanjang jendela bera T:
        D_i = sum_{t=1}^T [ b_{it} * k_i * c_{it} * e_{it} * delta_t ]
        """
        if not time_series:
            raise ValueError("Time series pengamatan lahan bera tidak boleh kosong.")

        k_i = k_rusle_override if k_rusle_override is not None else self.c.k_rusle_vertisol
        c_it = self.compute_hydrological_connectivity(slope_deg, twi)

        d_i_cumulative = 0.0
        latest_step = time_series[-1]
        max_r_gpm = max(step.r_gpm_max_mm_hr for step in time_series)

        for step in time_series:
            mbsi_t = self.compute_mbsi(step.rho_swir1, step.rho_swir2, step.rho_nir)
            b_it = self.mbsi_to_bare_fraction(mbsi_t)

            # Daya kinetik hujan ekstrem GPM IMERG: e_{it} = (R_GPM / R_crit)^2 saat R >= R_95th
            if step.r_gpm_max_mm_hr >= self.c.r_crit_mm_hr:
                e_it = (step.r_gpm_max_mm_hr / self.c.r_crit_mm_hr) ** 2
            else:
                # Kontribusi kinetik dasar untuk presipitasi moderat
                e_it = 0.15 * ((step.r_gpm_max_mm_hr / self.c.r_crit_mm_hr) ** 2)

            # Faktor skala konversi hari ke akumulasi indeks kerusakan musiman
            step_damage = b_it * (k_i * 100.0) * c_it * e_it * step.delta_t_days
            d_i_cumulative += step_damage

        # Evaluasi kondisi instan pada pengamatan terbaru
        mbsi_latest = self.compute_mbsi(
            latest_step.rho_swir1, latest_step.rho_swir2, latest_step.rho_nir
        )
        b_latest = self.mbsi_to_bare_fraction(mbsi_latest)
        bf_ehsi_now = self.compute_instantaneous_bf_ehsi(
            b_latest, latest_step.lst_ecostress_c, slope_deg, max_r_gpm
        )

        crack_depth_cm = self.estimate_desiccation_crack_depth_cm(
            latest_step.sm_surface_m3m3, clay_fraction=clay_fraction
        )

        # Estimasi kehilangan tanah erosi lembar (ton/ha/tahun) berbasis RUSLE & D_i
        sheet_erosion_ton_ha = float(
            np.clip(18.5 * d_i_cumulative + 9.2 * bf_ehsi_now, 0.5, 45.0)
        )

        is_exposed = b_latest > self.c.bsi_bare_threshold
        exceeds_tol = (d_i_cumulative > self.c.d_tolerance_limit) or (bf_ehsi_now >= 0.55)

        if crack_depth_cm >= 60.0:
            leaching_risk = "SEVERE_VERTICAL_BYPASS_CRACKING (>60 cm)"
        elif crack_depth_cm >= 30.0:
            leaching_risk = "MODERATE_MACRO_PORE_LEACHING (30-60 cm)"
        else:
            leaching_risk = "LOW_MATRIX_INFILTRATION"

        if exceeds_tol:
            mandate = (
                "MANDATORY_IMMEDIATE_COVER_CROP: Tanam darurat legum perakaran dalam "
                "(Kedelai Anjasmoro / Kacang Hijau) sebelum puncak Monsun Barat."
            )
        else:
            mandate = "SAFE_TRANSITION_WINDOW: Struktur agregat tanah terlindungi."

        slope_pct = math.tan(math.radians(slope_deg)) * 100.0

        return BFEHSIOutputContract(
            h3_index=h3_index,
            landscape_zone=landscape_zone,
            slope_deg=round(slope_deg, 2),
            slope_pct=round(slope_pct, 2),
            mbsi_latest=round(mbsi_latest, 4),
            bare_soil_fraction_b=round(b_latest, 4),
            is_bare_field_exposed=is_exposed,
            desiccation_crack_depth_cm=round(crack_depth_cm, 1),
            preferential_leaching_risk=leaching_risk,
            hydrological_connectivity_c=round(c_it, 4),
            bf_ehsi_instantaneous=round(bf_ehsi_now, 4),
            cumulative_risk_integral_di=round(d_i_cumulative, 4),
            estimated_sheet_erosion_ton_ha_yr=round(sheet_erosion_ton_ha, 2),
            exceeds_erosion_tolerance=exceeds_tol,
            emergency_cover_crop_mandate=mandate,
        )


if __name__ == "__main__":
    # Simulasi 10 Hari Transisi Kemarau ke Monsun Barat di Banyumas / Koridor Pantura
    # Tanah dibiarkan bera setelah panen padi -> mengering & retak -> dihantam hujan 54 mm/jam
    sim_steps = [
        HLSReflectanceStep(day_index=i, rho_nir=0.16, rho_swir1=0.34, rho_swir2=0.11,
                           lst_ecostress_c=39.5 + 0.4 * i, r_gpm_max_mm_hr=5.0 if i < 8 else 54.0,
                           sm_surface_m3m3=max(0.08, 0.16 - 0.01 * i), delta_t_days=1.0)
        for i in range(1, 11)
    ]

    bf_engine = BFEHSIEngine()
    out = bf_engine.evaluate_fallow_window(
        h3_index="892e42426ffffff",
        landscape_zone="Banyumas_Kedungbanteng_Transition_Slope",
        slope_deg=4.8,  # ~8.4% slope factor sesuai spesifikasi B2G Dashboard
        twi=11.4,
        time_series=sim_steps,
        clay_fraction=0.54,
    )
    print("=== HASIL EVALUASI BF-EHSI & INTEGRAL DEGRADASI LAHAN BERA ===")
    print(json.dumps(asdict(out), indent=2))