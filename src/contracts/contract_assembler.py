"""
src/contracts/contract_assembler.py
-----------------------------------
Perakit kontrak grid-cell v1.0 (PROVISIONAL, belum diratifikasi) yang conform
terhadap contracts/grid_cell_contract.schema.json.

Bagian agronomi/ekonomi (rotation_scenarios + fiscal_metrics) memakai ulang
CyberKatamFiscalActuarialEngine apa adanya (bobot terkalibrasi literatur, TIDAK
diubah). Bagian fisik (physical_indicators) diisi dari sinyal live per sel yang
dihitung PaddyLiveEvaluator, bukan placeholder.

Kebijakan non-null: skema provisional mewajibkan seluruh physical_indicators
bernilai (nullable policy belum diratifikasi). Untuk sel abstain (awan, tanpa
observasi HLS), NDVI/BSI memakai fallback klimatologi/regional yang DITANDAI
jujur lewat operational_flags.missing_observation=true dan teks
xai_decision_block.information_gaps. Fallback bukan observasi baru.

Struktur divalidasi oleh ContractValidator sebelum disajikan endpoint /predict.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from external.aryas_workresult.fiscal_actuarial import (  # noqa: E402
    CyberKatamFiscalActuarialEngine,
    RotationCandidate,
)

# Tiga kandidat rotasi kanonik (Arya, fiscal_actuarial.py __main__).
# Konstanta agronomi terkalibrasi literatur; jangan mengubah bobot/nilai ini.
CANONICAL_ROTATION_CANDIDATES: List[RotationCandidate] = [
    RotationCandidate(
        scenario_id="SCENARIO_A_EXISTING",
        crop_sequence="Padi -> Bera -> Padi (Monokultur Eksisting)",
        non_host_duration_days=15,
        water_demand_mm=680.0,
        n_fertilizer_displaced_kg_ha=0.0,
        soc_change_ton_ha=-0.42,
        bph_burden_index=0.82,
        gross_revenue_idr_ha=26_500_000.0,
        production_cost_idr_ha=15_200_000.0,
        required_ksat_mm_day=10.0,
        predicted_erosion_di=0.81,
    ),
    RotationCandidate(
        scenario_id="SCENARIO_B_OPTIMAL_LEGUME",
        crop_sequence="Padi -> Kedelai Anjasmoro -> Sorghum",
        non_host_duration_days=68,
        water_demand_mm=270.0,
        n_fertilizer_displaced_kg_ha=163.0,
        soc_change_ton_ha=1.25,
        bph_burden_index=0.04,
        gross_revenue_idr_ha=31_400_000.0,
        production_cost_idr_ha=12_800_000.0,
        required_ksat_mm_day=35.0,
        predicted_erosion_di=0.19,
    ),
    RotationCandidate(
        scenario_id="SCENARIO_C_FAST_MUNGBEAN",
        crop_sequence="Padi -> Kacang Hijau Vima-1 (60 Hari) -> Cover Crop",
        non_host_duration_days=60,
        water_demand_mm=245.0,
        n_fertilizer_displaced_kg_ha=128.0,
        soc_change_ton_ha=0.88,
        bph_burden_index=0.06,
        gross_revenue_idr_ha=27_800_000.0,
        production_cost_idr_ha=11_500_000.0,
        required_ksat_mm_day=30.0,
        predicted_erosion_di=0.22,
    ),
]


def _clip(value: float, lo: float, hi: float) -> float:
    return float(min(hi, max(lo, value)))


@dataclass(frozen=True)
class CellPhysicalSignals:
    """Sinyal fisik live per sel (domain mengikuti skema v1.0)."""

    pvrs: float                 # [0, 1]
    bf_ehsi_raw: float          # [0, 2.5] instantaneous mentah, bukan normalized
    smap_wetness: float         # [0, 1] m3/m3
    ecostress_esi: float        # [0, 1]
    lst_anomaly_c: float        # bebas (boleh negatif)
    hls_bsi: float              # [-1, 1]
    hls_ndvi: float             # [-1, 1]
    gpm_rain_7d_mm: float       # [0, inf)
    srtm_slope_deg: float       # [0, 90]


class ContractAssembler:
    """Merakit kontrak v1.0; blok agronomi/fiskal dihitung sekali lalu dipakai ulang."""

    def __init__(self) -> None:
        self._engine = CyberKatamFiscalActuarialEngine()
        (
            self._rotation_scenarios,
            self._fiscal_metrics,
            self.optimal_scenario_id,
        ) = self._agronomic_block()

    def _agronomic_block(self):
        fiscal = self._engine.compute_fiscal_and_autp_clearing(adoption_ratio_ak=1.0)
        _pareto, optimal = self._engine.solve_pareto_epsilon_constraint(
            CANONICAL_ROTATION_CANDIDATES
        )
        rotation = [
            {
                "id": c.scenario_id,
                "crop_sequence": c.crop_sequence,
                "water_demand_mm": c.water_demand_mm,
                "n_fertilizer_displaced_kg": c.n_fertilizer_displaced_kg_ha,
                "soc_change_ton": c.soc_change_ton_ha,
                "bph_risk_score": c.bph_burden_index,
                "net_margin_idr": c.net_margin_idr_ha,
            }
            for c in CANONICAL_ROTATION_CANDIDATES
        ]
        fiscal_metrics = {
            "urea_subsidy_saved_idr": fiscal["subsidy_saving_per_ha_idr"],
            "cluster_h3_7_gross_saving_idr": fiscal["gross_cluster_h3_7_saving_idr"],
            "cluster_h3_7_net_saving_s_net_idr": fiscal["net_fiscal_clearing_s_net_idr"],
            "autp_risk_reduction_pct": fiscal["autp_risk_reduction_pct"],
        }
        optimal_id = optimal.scenario_id if optimal is not None else None
        return rotation, fiscal_metrics, optimal_id

    def assemble(
        self,
        *,
        h3_index: str,
        signals: CellPhysicalSignals,
        missing_observation: bool,
        optical_lag_days: int,
        erosion_alert: bool,
        system_state: str,
        stress_category: str,
        confidence_pct: float,
        h3_parent_res7: Optional[str] = None,
        indicator_provenance: str = "unknown",
        ndvi_is_fallback: bool = False,
        bsi_is_fallback: bool = False,
        rain_7d_source: str = "bridge_observed_7d",
    ) -> Dict[str, Any]:
        """Rakit satu kontrak v1.0 dari sinyal live per sel + blok agronomi regional."""

        physical = {
            "PVRS": round(_clip(signals.pvrs, 0.0, 1.0), 4),
            "BF_EHSI": round(_clip(signals.bf_ehsi_raw, 0.0, 2.5), 4),
            "SMAP_wetness": round(_clip(signals.smap_wetness, 0.0, 1.0), 4),
            "ECOSTRESS_ESI": round(_clip(signals.ecostress_esi, 0.0, 1.0), 4),
            "LST_anomaly": round(float(signals.lst_anomaly_c), 3),
            "HLS_BSI": round(_clip(signals.hls_bsi, -1.0, 1.0), 4),
            "HLS_NDVI": round(_clip(signals.hls_ndvi, -1.0, 1.0), 4),
            "GPM_rain_7d": round(max(0.0, float(signals.gpm_rain_7d_mm)), 2),
            "SRTM_slope": round(_clip(signals.srtm_slope_deg, 0.0, 90.0), 2),
        }
        contract: Dict[str, Any] = {
            "contract_version": "1.0",
            "h3_index": h3_index,
            "physical_indicators": physical,
            "operational_flags": {
                "missing_observation": bool(missing_observation),
                "optical_lag_days": int(_clip(optical_lag_days, 0, 14)),
                "erosion_alert": bool(erosion_alert),
            },
            "rotation_scenarios": self._rotation_scenarios,
            "xai_decision_block": self._xai(
                signals=signals,
                stress_category=stress_category,
                confidence_pct=confidence_pct,
                system_state=system_state,
                missing_observation=missing_observation,
                indicator_provenance=indicator_provenance,
                ndvi_is_fallback=ndvi_is_fallback,
                bsi_is_fallback=bsi_is_fallback,
                rain_7d_source=rain_7d_source,
                erosion_alert=erosion_alert,
            ),
            "fiscal_metrics": self._fiscal_metrics,
            "system_state": system_state,
        }
        if h3_parent_res7:
            contract["h3_parent_res7"] = h3_parent_res7
        return contract

    def _xai(
        self,
        *,
        signals: CellPhysicalSignals,
        stress_category: str,
        confidence_pct: float,
        system_state: str,
        missing_observation: bool,
        indicator_provenance: str,
        ndvi_is_fallback: bool,
        bsi_is_fallback: bool,
        rain_7d_source: str,
        erosion_alert: bool,
    ) -> Dict[str, str]:
        driver = (
            "defisit lengas perakaran"
            if signals.smap_wetness < 0.25
            else "anomali suhu kanopi"
            if signals.lst_anomaly_c > 1.0
            else "hidrologi optimal"
        )
        why = (
            f"Observasi live Meteomatics + konteks satelit per sel menunjukkan {driver}: "
            f"PVRS {signals.pvrs:.2f} ({stress_category}), anomali LST {signals.lst_anomaly_c:+.1f} C, "
            f"ESI {signals.ecostress_esi:.2f}, lengas akar {signals.smap_wetness:.2f} m3/m3, "
            f"keyakinan engine {confidence_pct:.1f}%. Status governed: {system_state}."
        )
        benefits = (
            f"Rotasi optimal Pareto ({self.optimal_scenario_id or 'SCENARIO_B_OPTIMAL_LEGUME'}) "
            "memutus siklus Wereng Batang Cokelat >60 hari, menambat N alami setara "
            f"{self._fiscal_metrics['urea_subsidy_saved_idr']:,.0f} Rp/ha subsidi Urea APBN, "
            f"dan mereduksi risiko klaim AUTP {self._fiscal_metrics['autp_risk_reduction_pct']:.1f}% "
            "pada kluster H3-7."
        )
        gaps: List[str] = [
            f"Provenance indikator: {indicator_provenance}.",
            "Satelit NASA tidak memetakan pH mikro, salinitas petak, atau sumbatan pintu air tersier.",
            "TWI adalah proxy berbasis kemiringan SRTM (belum ada akumulasi aliran D8); "
            "fraksi lempung memakai default vertisol 0.52.",
        ]
        if rain_7d_source == "bridge_observed_7d":
            gaps.append(
                "GPM_rain_7d = akumulasi 7 hari observasi GPM harian per sel (bridge), "
                "bukan produk hujan live; hari tanpa observasi tetap NaN."
            )
        if missing_observation:
            gaps.append(
                "Sel ini ABSTAIN (awan/tanpa observasi HLS): missing_observation=true."
            )
        if ndvi_is_fallback:
            gaps.append("HLS_NDVI memakai fallback klimatologi per sel, bukan observasi segar.")
        if bsi_is_fallback:
            gaps.append("HLS_BSI memakai fallback regional (MBSI tak tersedia), bukan observasi segar.")
        risks = (
            f"Kemiringan SRTM {signals.srtm_slope_deg:.1f} derajat; "
            f"erosion_alert={'YA' if erosion_alert else 'tidak'}. "
            "Wajib verifikasi PPL (Gate 2 & Gate 3): pastikan drainase bebas genangan "
            "(K_sat >= 35 mm/hari) agar bintil Bradyrhizobium tidak membusuk, dan "
            "sinkronisasi tanam satu hamparan H3-7 sebelum adopsi rotasi."
        )
        return {
            "why_suggested": why,
            "multi_benefits": benefits,
            "information_gaps": " ".join(gaps),
            "local_risks_and_gates": risks,
        }