#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CYBER-KATAM: Pre-Visual Root-Stress Score (PVRS) & Native-Support Spatial Inversion Engine
Deliverable: LEADER-02 (pvrs_engine.py)
Target Domain: Agro-Climatic Remote Sensing (ECOSTRESS L2/L3, SMAP L4, HLS v2.0 30m)
"""

from __future__ import annotations
import json
import math
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass(frozen=True)
class PVRSWeights:
    """Bobot fisis terkalibrasi sesuai Spesifikasi Teknis CYBER-KATAM Bab 3.2."""
    w1_esi: float = 0.35      # Bobot anomali Evaporative Stress Index (ECOSTRESS)
    w2_lst: float = 0.35      # Bobot anomali Land Surface Temperature (ECOSTRESS)
    w3_sm: float = 0.30       # Bobot anomali kelembapan perakaran 0-100 cm (SMAP L4)
    gamma_ndvi: float = 0.50  # Faktor penekan gejala visual optik (HLS v2.0 NDVI)

    def validate(self) -> None:
        total_physio = self.w1_esi + self.w2_lst + self.w3_sm
        if not math.isclose(total_physio, 1.0, rel_tol=1e-5):
            raise ValueError(f"Jumlah bobot fisiologis wajib 1.0, terdeteksi: {total_physio}")


@dataclass
class DecadalClimatologyBaseline:
    """Parameter klimatologi historis 10-harian (dekad) spesifik sel H3."""
    mu_esi: float
    sigma_esi: float
    mu_lst_c: float
    sigma_lst_c: float
    mu_sm_root: float
    sigma_sm_root: float
    mu_ndvi: float
    sigma_ndvi: float


@dataclass
class SatelliteObservationInput:
    """Observasi aktual sensor pada sel H3 Level 9 (~10 ha)."""
    h3_index: str
    esi_actual: float              # Rasio ET/PET ECOSTRESS [0.0 - 1.0]
    lst_actual_c: float            # Suhu radiometrik kanopi ECOSTRESS (Celsius)
    sm_root_actual: float          # Lengas zona perakaran 0-100 cm hasil inversi (m3/m3)
    ndvi_actual: float             # Indeks kehijauan HLS v2.0 30m [-1.0 - 1.0]
    obs_age_hours: float           # Usia observasi bebas awan terakhir (jam)
    cloud_fraction: float          # Fraksi tutupan awan pada citra optik [0.0 - 1.0]
    sensor_zenith_deg: float       # Sudut datang sensor (derajat)
    in_situ_waterlogging: bool = False  # Anomali genangan lokal dari Gate 2


@dataclass
class LipschitzErrorParameters:
    """Parameter batas kesalahan analitis Bab 3.6: ||g(z) - g(z_hat)|| <= L_g * sum(delta)."""
    lipschitz_constant_lg: float = 1.15
    delta_sensor: float = 0.022      # Galat radiometrik instrumen satelit
    delta_support: float = 0.031     # Galat diskrepansi skala (SMAP 9km ke H3-9 30m)
    delta_model: float = 0.015       # Galat struktur model transfer radiatif
    tau_decorrelation_hours: float = 120.0  # Konstanta peluruhan temporal (5 hari)
    tolerance_threshold_tau: float = 0.120  # Ambang batas mutlak abstensi


@dataclass
class PVRSOutputContract:
    """Struktur keluaran penuh modul PVRS dan status Governed Abstention."""
    h3_index: str
    z_score_esi_deficit: float
    z_score_lst_excess: float
    z_score_sm_deficit: float
    s_physio: float
    s_visual: float
    pvrs_score: float
    stress_category: str
    estimated_optical_lag_days: int
    lst_anomaly_c: float
    error_bound_value: float
    tolerance_threshold: float
    confidence_pct: float
    gate_1_sensor_pass: bool
    gate_2_hydrology_pass: bool
    system_state: str
    advisory_code: str


class NativeSupportSpatialInverter:
    """
    Bab 3.1: Rekonstruksi Spasial Native-Support (Inversi Bebas Interpolasi Naif)
    Memecahkan: z_hat = argmin_{z in C} [ (y - Hz)^T Sigma^{-1} (y - Hz) + lambda * R(z) ]
    dengan syarat kekekalan massa sum_j(H_ij) = 1 dan theta_res <= z <= theta_sat.
    """

    def __init__(
        self,
        theta_residual: float = 0.11,  # Kadar air titik layu permanen aluvial/vertisol (m3/m3)
        theta_saturated: float = 0.48, # Porositas jenuh tanah sawah (m3/m3)
        lambda_tv: float = 0.08,       # Parameter regularisasi Total Variation (pematang sawah)
        max_iter: int = 250,
        tol: float = 1e-6,
    ) -> None:
        self.theta_res = theta_residual
        self.theta_sat = theta_saturated
        self.lambda_tv = lambda_tv
        self.max_iter = max_iter
        self.tol = tol

    @staticmethod
    def build_psf_projection_matrix(
        coords_coarse_km: np.ndarray,
        coords_fine_km: np.ndarray,
        psf_fwhm_km: float = 9.0,
    ) -> np.ndarray:
        """
        Membangun matriks operator proyeksi spasial H (M x N) berbasis Point-Spread Function (PSF)
        Gaussian 2D antena L-band dengan normalisasi kekekalan massa baris sum_j H_ij = 1.
        """
        sigma_psf = psf_fwhm_km / (2.0 * math.sqrt(2.0 * math.log(2.0)))
        diff = coords_coarse_km[:, None, :] - coords_fine_km[None, :, :]
        dist_sq = np.sum(diff ** 2, axis=-1)
        H = np.exp(-dist_sq / (2.0 * sigma_psf ** 2))
        row_sums = np.sum(H, axis=1, keepdims=True)
        row_sums = np.where(row_sums == 0.0, 1.0, row_sums)
        return H / row_sums

    @staticmethod
    def _total_variation_grad(z: np.ndarray, eps: float = 1e-4) -> np.ndarray:
        """Menghitung gradien aproksimasi mulus Total Variation 1D/graf ketetanggaan petak."""
        diff_fwd = np.roll(z, -1) - z
        diff_bwd = z - np.roll(z, 1)
        grad_tv = -(diff_fwd / np.sqrt(diff_fwd ** 2 + eps ** 2)) + (
            diff_bwd / np.sqrt(diff_bwd ** 2 + eps ** 2)
        )
        return grad_tv

    def invert_rootzone_moisture(
        self,
        y_coarse: np.ndarray,
        H: np.ndarray,
        sigma_noise_diag: np.ndarray,
        z_prior: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, float]:
        """
        Menjalankan Projected Gradient Descent (PGD) dengan pencarian garis (backtracking)
        untuk memperoleh vektor kelembapan zona perakaran resolusi petak mikro z_hat (N,).
        """
        m_coarse, n_fine = H.shape
        if y_coarse.shape[0] != m_coarse:
            raise ValueError("Dimensi vektor observasi y tidak sesuai dengan baris matriks H.")

        inv_cov = np.diag(1.0 / np.maximum(sigma_noise_diag ** 2, 1e-8))
        z = np.clip(
            z_prior.copy() if z_prior is not None else np.full(n_fine, np.mean(y_coarse)),
            self.theta_res,
            self.theta_sat,
        )

        # Estimasi konstanta Lipschitz dari bagian kuadratik: ||H^T Sigma^{-1} H||_2
        ht_sinv_h = H.T @ inv_cov @ H
        eig_max = float(np.linalg.norm(ht_sinv_h, ord=2))
        step_size = 1.0 / (eig_max + 4.0 * self.lambda_tv + 1e-6)

        for _ in range(self.max_iter):
            residual = H @ z - y_coarse
            grad_data = H.T @ (inv_cov @ residual)
            grad_reg = self.lambda_tv * self._total_variation_grad(z)
            grad_total = grad_data + grad_reg

            # Proyeksi ke himpunan konveks fisis C: [theta_residual, theta_saturated]
            z_next = np.clip(z - step_size * grad_total, self.theta_res, self.theta_sat)

            if np.linalg.norm(z_next - z) < self.tol:
                z = z_next
                break
            z = z_next

        final_residual_norm = float(np.linalg.norm(y_coarse - H @ z))
        return z, final_residual_norm


class PVRSEngine:
    """
    Mesin Perhitungan Pre-Visual Root-Stress Score (PVRS) & Protokol Abstensi Deterministik.
    Mengatasi fenomena optical lag 10-14 hari pada ekosistem padi-palawija tropis monsun.
    """

    def __init__(
        self,
        weights: Optional[PVRSWeights] = None,
        error_params: Optional[LipschitzErrorParameters] = None,
    ) -> None:
        self.weights = weights or PVRSWeights()
        self.weights.validate()
        self.error_params = error_params or LipschitzErrorParameters()

    @staticmethod
    def _safe_z(delta: float, sigma: float, clip_limit: float = 4.5) -> float:
        if sigma <= 1e-9:
            raise ValueError("Simpangan baku klimatologi (sigma) harus bernilai positif.")
        return float(np.clip(delta / sigma, -clip_limit, clip_limit))

    def compute_optical_lag_days(
        self, s_physio: float, s_visual: float, lst_anomaly_c: float
    ) -> int:
        """
        Mengestimasi jumlah hari keterlambatan gejala visual (optical lag) saat
        stres perakaran dan penutupan stomata sudah aktif tetapi klorofil daun belum terdegradasi.
        """
        if s_physio <= 0.5 or s_visual >= 0.75:
            return 0
        # Semakin lebar diskrepansi fisiologis vs visual dan kenaikan LST (+1.5 s/d +3.0 C),
        # semakin awal fase deteksi pra-visual (hingga 14 hari sebelum klorosis NDVI).
        divergence = max(0.0, s_physio - s_visual)
        thermal_factor = np.clip((lst_anomaly_c - 0.5) / 2.5, 0.0, 1.0)
        lag_days = int(round(np.clip(4.0 + 6.5 * divergence + 3.5 * thermal_factor, 1.0, 14.0)))
        return lag_days

    def evaluate_cell(
        self,
        obs: SatelliteObservationInput,
        baseline: DecadalClimatologyBaseline,
    ) -> PVRSOutputContract:
        """Menghitung skor PVRS [0, 1] dan mengevaluasi gerbang abstensi deterministik."""
        # 1. Z-Score Komponen Fisiologis (Positif = Stres Meningkat)
        z_esi = self._safe_z(baseline.mu_esi - obs.esi_actual, baseline.sigma_esi)
        z_lst = self._safe_z(obs.lst_actual_c - baseline.mu_lst_c, baseline.sigma_lst_c)
        z_sm = self._safe_z(baseline.mu_sm_root - obs.sm_root_actual, baseline.sigma_sm_root)

        s_physio = (
            self.weights.w1_esi * z_esi
            + self.weights.w2_lst * z_lst
            + self.weights.w3_sm * z_sm
        )

        # 2. Z-Score Gejala Visual Optik (Saat optical lag terjadi, daun masih hijau -> s_visual <= 0)
        s_visual = self._safe_z(baseline.mu_ndvi - obs.ndvi_actual, baseline.sigma_ndvi)

        # 3. Formulasi Komposit Sigmoid Bounded [0, 1]
        logit_arg = s_physio - (self.weights.gamma_ndvi * s_visual)
        pvrs_score = float(1.0 / (1.0 + math.exp(-logit_arg)))

        # 4. Estimasi Keterlambatan Optik (Optical Lag Days)
        lst_anomaly = obs.lst_actual_c - baseline.mu_lst_c
        optical_lag_days = self.compute_optical_lag_days(s_physio, s_visual, lst_anomaly)

        # 5. Klasifikasi Stres Fisiologis
        if pvrs_score >= 0.70:
            category = "CRITICAL_PRE_VISUAL_STRESS"
        elif pvrs_score >= 0.45:
            category = "MODERATE_STOMATAL_CLOSURE"
        else:
            category = "OPTIMAL_TRANSPIRATION"

        # 6. Evaluasi Batas Kesalahan Analitis Lipschitz (Bab 3.6)
        ep = self.error_params
        delta_age = (obs.obs_age_hours / ep.tau_decorrelation_hours) * 0.025
        cloud_penalty = max(0.0, (obs.cloud_fraction - 0.30) * 0.04)
        total_delta = ep.delta_sensor + ep.delta_support + ep.delta_model + delta_age + cloud_penalty
        error_bound = float(ep.lipschitz_constant_lg * total_delta)

        # 7. Evaluasi Gerbang Verifikasi 1 & 2 serta Status Governed Abstention
        gate_1_pass = (
            obs.obs_age_hours <= 72.0
            and obs.cloud_fraction <= 0.65
            and obs.sensor_zenith_deg <= 55.0
        )
        # Konflik sinyal: Satelit mendeteksi defisit air perakaran tapi lapangan tergenang (waterlogging)
        signal_conflict = (z_sm > 1.0) and obs.in_situ_waterlogging
        gate_2_pass = not signal_conflict

        if error_bound <= ep.tolerance_threshold_tau and gate_1_pass and gate_2_pass:
            system_state = "ACTIVE_RECOMMENDATION"
            advisory_code = "EMIT_ADVISORY"
        else:
            system_state = "ABSTAIN_FIELD_AUDIT_REQUIRED"
            advisory_code = "ABSTAIN_AUDIT_REQUIRED"

        confidence_pct = float(np.clip((1.0 - error_bound) * 100.0, 0.0, 99.9))

        return PVRSOutputContract(
            h3_index=obs.h3_index,
            z_score_esi_deficit=round(z_esi, 4),
            z_score_lst_excess=round(z_lst, 4),
            z_score_sm_deficit=round(z_sm, 4),
            s_physio=round(s_physio, 4),
            s_visual=round(s_visual, 4),
            pvrs_score=round(pvrs_score, 4),
            stress_category=category,
            estimated_optical_lag_days=optical_lag_days,
            lst_anomaly_c=round(lst_anomaly, 2),
            error_bound_value=round(error_bound, 4),
            tolerance_threshold=ep.tolerance_threshold_tau,
            confidence_pct=round(confidence_pct, 2),
            gate_1_sensor_pass=gate_1_pass,
            gate_2_hydrology_pass=gate_2_pass,
            system_state=system_state,
            advisory_code=advisory_code,
        )


if __name__ == "__main__":
    # 1. Uji Rekonstruksi Spasial Native-Support (SMAP 9 km -> 5 Petak Mikro H3-9)
    inverter = NativeSupportSpatialInverter()
    coarse_centers = np.array([[0.0, 0.0], [9.0, 0.0]])
    fine_centers = np.array([[0.0, 0.0], [1.5, 0.5], [3.0, -0.5], [6.0, 0.2], [8.5, 0.0]])
    H_mat = inverter.build_psf_projection_matrix(coarse_centers, fine_centers, psf_fwhm_km=9.0)
    y_smap = np.array([0.185, 0.240])  # Observasi SMAP L4 (m3/m3)
    sigma_smap = np.array([0.02, 0.02])
    z_prior_topo = np.array([0.17, 0.19, 0.20, 0.23, 0.25])

    z_hat, res_norm = inverter.invert_rootzone_moisture(y_smap, H_mat, sigma_smap, z_prior_topo)

    # 2. Uji Perhitungan PVRS pada Sel H3 Banyumas (Kondisi Stres Pra-Visual / Optical Lag)
    baseline_banyumas = DecadalClimatologyBaseline(
        mu_esi=0.68, sigma_esi=0.12,
        mu_lst_c=29.4, sigma_lst_c=1.15,
        mu_sm_root=0.31, sigma_sm_root=0.055,
        mu_ndvi=0.72, sigma_ndvi=0.08,
    )
    obs_cell = SatelliteObservationInput(
        h3_index="892e42426ffffff",
        esi_actual=0.38,                 # Anjlok: stomata menutup menahan transpirasi
        lst_actual_c=31.5,               # Naik +2.1 C di atas normal kanopi
        sm_root_actual=float(z_hat[1]),  # ~0.19 m3/m3 hasil inversi SMAP L4
        ndvi_actual=0.74,                # Masih tampak hijau semu (Optical Lag aktif!)
        obs_age_hours=36.0,
        cloud_fraction=0.18,
        sensor_zenith_deg=24.0,
        in_situ_waterlogging=False,
    )

    engine = PVRSEngine()
    result = engine.evaluate_cell(obs_cell, baseline_banyumas)
    print("=== HASIL EVALUASI PVRS & NATIVE-SUPPORT INVERSION ===")
    print(f"Vektor Lengas Perakaran Laten z_hat (m3/m3): {np.round(z_hat, 4)}")
    print(json.dumps(asdict(result), indent=2))