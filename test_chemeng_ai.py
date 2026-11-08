"""
ChemEng AI — Functional & Negative Quality Assurance Suite (Tahap 2 & Tahap 7)
==============================================================================
Menguji 8 skenario positif dan 3 skenario negatif sesuai spesifikasi produk ChemEng AI v0.1.
"""

import unittest
from fastapi import HTTPException
from chemeng_ai_mcp_server import (
    MassBalanceInput,
    EnergyBalanceInput,
    ThermodynamicsInput,
    EquipmentSizingInput,
    PropertyMethodInput,
    TroubleshootAspenInput,
    SimulationCaseInput,
    EvaluateSolutionInput,
    SearchPapersInput,
    calculate_mass_balance,
    calculate_energy_balance,
    calculate_thermodynamics,
    size_process_equipment,
    recommend_property_method,
    troubleshoot_aspen,
    design_simulation_case,
    evaluate_engineering_solution,
    search_chemical_papers,
    CORE_SYSTEM_INSTRUCTIONS,
)


class TestChemEngAIPlugin(unittest.TestCase):
    # -----------------------------------------------------------------
    # SKENARIO POSITIF (8 Skenario Utama)
    # -----------------------------------------------------------------
    def test_01_tutorial_aspen_pemula(self):
        """Skenario 1: Tutorial Aspen pemula — Instruksi bertahap (1 langkah UI per giliran)."""
        res = design_simulation_case(
            SimulationCaseInput(topic="Pemisahan Benzena-Toluena", user_level="Mahasiswa S1", simulator="Aspen Plus")
        )
        self.assertIn("guided_step_1", res["case_study_structure"])
        self.assertIn("Langkah 1 UI", res["case_study_structure"]["guided_step_1"])

    def test_02_pemilihan_property_method(self):
        """Skenario 2: Pemilihan Property Method — Mempertimbangkan komposisi dan kondisi."""
        res = recommend_property_method(
            PropertyMethodInput(
                components=["Ethanol", "Water"],
                polarity="polar-non-electrolyte",
                pressure_bar=1.013,
                simulator="Aspen Plus",
            )
        )
        self.assertIn("NRTL", res["recommended_property_method"])

    def test_03_aspen_convergence_error(self):
        """Skenario 3: Aspen mengalami convergence error — Diagnosis berdasarkan bukti."""
        res = troubleshoot_aspen(
            TroubleshootAspenInput(
                simulator="Aspen Plus",
                unit_operation="RadFrac",
                error_message="SEVERE ERROR: RADFRAC NOT CONVERGED IN 25 ITERATIONS",
            )
        )
        self.assertEqual(len(res["diagnostic_workflow"]), 3)
        self.assertIn("Design Specs", res["single_ui_step_next"])

    def test_04_neraca_massa_konsisten(self):
        """Skenario 4: Neraca massa — Hasil dan satuan konsisten serta tertutup (closed)."""
        res = calculate_mass_balance(
            MassBalanceInput(
                unit_name="Distillation Column C-101",
                feed_flow_kg_h=1000.0,
                feed_composition={"Benzene": 0.4, "Toluene": 0.6},
                split_fractions_to_top={"Benzene": 0.95, "Toluene": 0.05},
            )
        )
        self.assertTrue(res.consistency_check["mass_balance_closed"])
        self.assertEqual(res.results_and_units["Total Distilat / Top (D)"], "410.00 kg/h")
        self.assertEqual(res.results_and_units["Total Bottom (B)"], "590.00 kg/h")

    def test_05_neraca_energi_valid(self):
        """Skenario 5: Neraca energi — Persamaan, satuan, dan asumsi benar."""
        res = calculate_energy_balance(
            EnergyBalanceInput(
                stream_name="Feed Heater E-101",
                mass_flow_kg_h=3600.0,
                cp_kj_kg_k=2.1,
                t_in_c=25.0,
                t_out_c=85.0,
            )
        )
        self.assertTrue(res.consistency_check["sign_convention_valid"])
        self.assertIn("126.00 kW", res.results_and_units["Q_total"])

    def test_06_analisis_jurnal_terverifikasi(self):
        """Skenario 6: Pencarian & Analisis jurnal — Menggunakan endpoint resmi Crossref."""
        res = search_chemical_papers(SearchPapersInput(query="extractive distillation ethanol", year_from=2020))
        self.assertIn("https://api.crossref.org/works", res["api_integration_endpoint"])

    def test_07_desain_heat_exchanger(self):
        """Skenario 7: Desain heat exchanger — Asumsi desain dan pemeriksaan LMTD dijelaskan."""
        res = size_process_equipment(
            EquipmentSizingInput(
                equipment_type="heat_exchanger",
                heat_duty_kw=500.0,
                overall_u_w_m2_k=600.0,
                t_hot_in_c=120.0,
                t_hot_out_c=70.0,
                t_cold_in_c=30.0,
                t_cold_out_c=60.0,
            )
        )
        self.assertTrue(res.consistency_check["no_temperature_cross"])
        self.assertTrue(len(res.assumptions_and_limits) >= 2)

    def test_08_termodinamika_antoine(self):
        """Skenario 8: Perhitungan termodinamika tekanan uap jenuh & nilai K ideal."""
        res = calculate_thermodynamics(
            ThermodynamicsInput(
                component_name="Benzene",
                temperature_c=80.1,
                pressure_bar=1.01325,
                antoine_a=4.01814,
                antoine_b=1203.835,
                antoine_c=-53.226,
            )
        )
        self.assertTrue(res.consistency_check["positive_vapor_pressure"])

    # -----------------------------------------------------------------
    # SKENARIO NEGATIF (3 Kasus Wajib MCP)
    # -----------------------------------------------------------------
    def test_neg_01_tolak_fraksi_massa_tidak_valid(self):
        """Negatif 1: Menolak input neraca massa jika jumlah fraksi massa != 1.0."""
        with self.assertRaises(HTTPException):
            calculate_mass_balance(
                MassBalanceInput(
                    feed_flow_kg_h=1000.0,
                    feed_composition={"Benzene": 0.7, "Toluene": 0.5},  # Total = 1.2 (Invalid)
                    split_fractions_to_top={"Benzene": 0.9, "Toluene": 0.1},
                )
            )

    def test_neg_02_tolak_temperature_cross_heat_exchanger(self):
        """Negatif 2: Menolak desain Heat Exchanger jika terjadi temperature cross (melanggar Hukum II Termodinamika)."""
        with self.assertRaises(HTTPException):
            size_process_equipment(
                EquipmentSizingInput(
                    equipment_type="heat_exchanger",
                    heat_duty_kw=500.0,
                    overall_u_w_m2_k=600.0,
                    t_hot_in_c=90.0,
                    t_hot_out_c=50.0,
                    t_cold_in_c=40.0,
                    t_cold_out_c=95.0,  # T_cold_out > T_hot_in (Impossible)
                )
            )

    def test_neg_03_deteksi_klaim_efisiensi_mustahil_dan_aturan_inti(self):
        """Negatif 3: Mendeteksi klaim efisiensi > 100% dan memastikan larangan klaim sertifikasi keselamatan/jurnal palsu."""
        eval_res = evaluate_engineering_solution(
            EvaluateSolutionInput(
                problem_statement="Reaktor konversi amonia",
                user_calculation_steps="Konversi dihitung 115%",
                claimed_efficiency_or_yield=115.0,
            )
        )
        self.assertEqual(eval_res["status"], "Perlu Perbaikan")
        self.assertTrue(len(eval_res["detected_warnings"]) > 0)
        self.assertIn("Tidak mengarang data eksperimen", CORE_SYSTEM_INSTRUCTIONS)
        self.assertIn("Tidak memberikan sertifikasi keselamatan proses", CORE_SYSTEM_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
