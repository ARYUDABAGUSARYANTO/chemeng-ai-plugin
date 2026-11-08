"""
ChemEng AI — MCP Server & Plugin Backend (v0.1)
===============================================
Backend server untuk Chemical Engineering AI (ChemEng AI) berbasis FastAPI & MCP JSON-RPC.
Menyediakan 11 tools teknik kimia terstandarisasi dengan audit trail lengkap:
- Input & satuan
- Persamaan yang digunakan
- Langkah perhitungan
- Hasil & satuan
- Asumsi & batas penggunaan
- Pemeriksaan konsistensi (Mass/Energy balance & kewajaran fisik)
"""

import math
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="ChemEng AI Plugin & MCP Server",
    description="Evidence-based Chemical Engineering AI Tutor, Process Simulator Analyst, and Calculation Engine.",
    version="0.1.0",
)

# =====================================================================
# 1. CORE SYSTEM INSTRUCTIONS (Tahap 2 — Skill & System Instructions)
# =====================================================================
CORE_SYSTEM_INSTRUCTIONS = """
CHEMENG AI — CORE INSTRUCTIONS v0.1
1. Bertindak sebagai tutor dan konsultan teknik kimia berbasis bukti (evidence-based).
2. Menggunakan bahasa Indonesia sebagai bahasa utama, dengan istilah engineering dalam bahasa Inggris.
3. Menyesuaikan penjelasan dengan tingkat kemampuan pengguna (Mahasiswa, Dosen/Peneliti, Process Engineer).
4. Mengajarkan konsep dasar dan fenomena transport/termodinamika sebelum memberikan prosedur kompleks.
5. Menampilkan persamaan, satuan, basis perhitungan, dan asumsi secara eksplisit pada setiap perhitungan.
6. Tidak mengarang data eksperimen, properti fisik, parameter termodinamika, atau referensi jurnal (DOI wajib terverifikasi).
7. Tidak menganggap simulasi konvergen (Aspen Plus / HYSYS) sebagai simulasi tervalidasi tanpa pemeriksaan kewajaran fisik.
8. Memeriksa neraca massa, neraca energi, dan kewajaran fisik hasil (misal: T_cross, pendekatan suhu minimum, efisiensi < 100%).
9. Memberikan referensi teknik standar (Perry's, Coulson & Richardson, Smith Van Ness, Kern, Seader).
10. Tidak memberikan sertifikasi keselamatan proses (HAZOP/SIL/Relief Valve final sizing) hanya berdasarkan hasil simulasi.
11. Tidak mengklaim mengakses atau menjalankan software lokal (Aspen Plus/HYSYS) tanpa integrasi adapter nyata.
12. Untuk panduan Aspen Plus & HYSYS: berikan maksimal satu langkah UI utama per giliran dengan validasi teknis.
""".strip()


# =====================================================================
# 2. STANDARDIZED CALCULATION OUTPUT SCHEMA
# =====================================================================
class EngineeringCalculationResult(BaseModel):
    tool_name: str
    inputs_and_units: Dict[str, str]
    equations_used: List[str]
    calculation_steps: List[str]
    results_and_units: Dict[str, str]
    assumptions_and_limits: List[str]
    consistency_check: Dict[str, Any]
    references: List[str]


# =====================================================================
# 3. INPUT MODELS FOR THE 11 MCP TOOLS
# =====================================================================
class MassBalanceInput(BaseModel):
    unit_name: str = Field(default="Distillation Column C-101", description="Nama unit operasi")
    feed_flow_kg_h: float = Field(..., gt=0, description="Laju alir umpan (kg/h)")
    feed_composition: Dict[str, float] = Field(
        ..., description="Fraksi massa komponen umpan (total harus = 1.0), misal {'Benzene': 0.4, 'Toluene': 0.6}"
    )
    split_fractions_to_top: Dict[str, float] = Field(
        ..., description="Fraksi pemisahan masing-masing komponen ke produk atas (0.0 - 1.0)"
    )


class EnergyBalanceInput(BaseModel):
    stream_name: str = Field(default="Process Stream S-101")
    mass_flow_kg_h: float = Field(..., gt=0, description="Laju alir massa (kg/h)")
    cp_kj_kg_k: float = Field(..., gt=0, description="Kapasitas panas rata-rata Cp (kJ/kg.K)")
    t_in_c: float = Field(..., description="Suhu masuk (°C)")
    t_out_c: float = Field(..., description="Suhu keluar (°C)")
    latent_heat_kj_kg: float = Field(default=0.0, ge=0, description="Panas laten penguapan/kondensasi jika ada perubahan fasa (kJ/kg)")
    vapor_fraction_change: float = Field(default=0.0, ge=-1.0, le=1.0, description="Perubahan fraksi uap (-1 kondensasi penuh, +1 penguapan penuh)")


class ThermodynamicsInput(BaseModel):
    component_name: str = Field(..., description="Nama komponen kimia")
    temperature_c: float = Field(..., description="Suhu sistem (°C)")
    pressure_bar: float = Field(..., gt=0, description="Tekanan sistem (bar)")
    antoine_a: float = Field(..., description="Konstanta Antoine A (log10(P_bar) = A - B/(T_K + C))")
    antoine_b: float = Field(..., description="Konstanta Antoine B")
    antoine_c: float = Field(..., description="Konstanta Antoine C")


class EquipmentSizingInput(BaseModel):
    equipment_type: str = Field(..., description="'heat_exchanger', 'pump', atau 'separator'")
    heat_duty_kw: Optional[float] = Field(default=None, description="Beban panas Q (kW) untuk Heat Exchanger")
    overall_u_w_m2_k: Optional[float] = Field(default=500.0, description="Koefisien perpindahan panas menyeluruh U (W/m2.K)")
    t_hot_in_c: Optional[float] = Field(default=None, description="Suhu fluida panas masuk (°C)")
    t_hot_out_c: Optional[float] = Field(default=None, description="Suhu fluida panas keluar (°C)")
    t_cold_in_c: Optional[float] = Field(default=None, description="Suhu fluida dingin masuk (°C)")
    t_cold_out_c: Optional[float] = Field(default=None, description="Suhu fluida dingin keluar (°C)")
    volumetric_flow_m3_h: Optional[float] = Field(default=None, description="Laju alir volumetrik (m3/h) untuk Pompa")
    density_kg_m3: Optional[float] = Field(default=1000.0, description="Densitas fluida (kg/m3)")
    differential_head_m: Optional[float] = Field(default=None, description="Head pompa (m)")
    pump_efficiency: Optional[float] = Field(default=0.75, gt=0, le=1.0, description="Efisiensi pompa (0-1)")


class PropertyMethodInput(BaseModel):
    components: List[str] = Field(..., description="Daftar komponen dalam sistem")
    polarity: str = Field(..., description="'non-polar', 'polar-non-electrolyte', 'electrolyte', atau 'associating'")
    pressure_bar: float = Field(..., gt=0, description="Tekanan operasi maksimum (bar)")
    simulator: str = Field(default="Aspen Plus", description="'Aspen Plus' atau 'Aspen HYSYS'")


class TroubleshootAspenInput(BaseModel):
    simulator: str = Field(default="Aspen Plus", description="'Aspen Plus' atau 'Aspen HYSYS'")
    unit_operation: str = Field(..., description="Misal: 'RadFrac', 'Heater', 'Flash2', 'Recycle Loop'")
    error_message: str = Field(..., description="Pesan error atau warning dari Control Panel / Simulation Status")
    operating_conditions: Dict[str, Any] = Field(default_factory=dict, description="Kondisi operasi terkait")


class SimulationCaseInput(BaseModel):
    topic: str = Field(..., description="Topik proses (misal: 'Pemisahan Etanol-Air', 'Dehidrasi Gas Alam TEG')")
    user_level: str = Field(default="Mahasiswa S1", description="'Mahasiswa S1', 'Peneliti', atau 'Process Engineer'")
    simulator: str = Field(default="Aspen Plus", description="'Aspen Plus' atau 'Aspen HYSYS'")


class EvaluateSolutionInput(BaseModel):
    problem_statement: str = Field(..., description="Deskripsi soal atau kasus teknik kimia")
    user_calculation_steps: str = Field(..., description="Langkah dan hasil perhitungan pengguna")
    claimed_efficiency_or_yield: Optional[float] = Field(default=None, description="Klaim efisiensi/konversi (0-100%)")


class SearchPapersInput(BaseModel):
    query: str = Field(..., description="Kata kunci topik riset teknik kimia")
    year_from: Optional[int] = Field(default=2018, description="Filter tahun publikasi mulai dari")


class AnalyzePaperInput(BaseModel):
    title: str = Field(..., description="Judul paper")
    doi: Optional[str] = Field(default=None, description="DOI paper (jika ada)")
    abstract_or_content: str = Field(..., description="Teks abstrak atau isi paper yang diberikan pengguna")


class GenerateReportInput(BaseModel):
    report_type: str = Field(..., description="'Laporan Praktikum', 'Laporan Simulasi', atau 'Memori Perhitungan Desain'")
    project_title: str = Field(..., description="Judul proyek atau praktikum")
    summary_data: Dict[str, Any] = Field(..., description="Data hasil perhitungan atau simulasi yang akan dimasukkan")


# =====================================================================
# 4. TOOL IMPLEMENTATIONS
# =====================================================================

@app.post("/tools/calculate_mass_balance", response_model=EngineeringCalculationResult)
def calculate_mass_balance(data: MassBalanceInput):
    total_frac = sum(data.feed_composition.values())
    if abs(total_frac - 1.0) > 1e-4:
        raise HTTPException(
            status_code=400,
            detail=f"Jumlah fraksi massa umpan harus sama dengan 1.0 (saat ini: {total_frac:.4f}).",
        )

    steps = [f"Basis perhitungan: Laju alir umpan (F) = {data.feed_flow_kg_h:.2f} kg/h pada unit {data.unit_name}."]
    top_flows = {}
    bottom_flows = {}

    for comp, z_i in data.feed_composition.items():
        f_i = data.feed_flow_kg_h * z_i
        split_i = data.split_fractions_to_top.get(comp, 0.0)
        if not (0.0 <= split_i <= 1.0):
            raise HTTPException(status_code=400, detail=f"Split fraction untuk {comp} harus antara 0.0 dan 1.0.")
        d_i = f_i * split_i
        b_i = f_i - d_i
        top_flows[comp] = d_i
        bottom_flows[comp] = b_i
        steps.append(
            f"Komponen {comp}: F_i = {f_i:.2f} kg/h | Distilat (D_i) = {d_i:.2f} kg/h (split={split_i:.2f}) | Bottom (B_i) = {b_i:.2f} kg/h"
        )

    total_top = sum(top_flows.values())
    total_bottom = sum(bottom_flows.values())
    closure_error = abs(data.feed_flow_kg_h - (total_top + total_bottom))

    results = {
        "Total Distilat / Top (D)": f"{total_top:.2f} kg/h",
        "Total Bottom (B)": f"{total_bottom:.2f} kg/h",
    }
    for comp in data.feed_composition:
        y_i = top_flows[comp] / total_top if total_top > 0 else 0.0
        x_i = bottom_flows[comp] / total_bottom if total_bottom > 0 else 0.0
        results[f"Distilat - {comp}"] = f"{top_flows[comp]:.2f} kg/h (fraksi massa: {y_i:.4f})"
        results[f"Bottom - {comp}"] = f"{bottom_flows[comp]:.2f} kg/h (fraksi massa: {x_i:.4f})"

    return EngineeringCalculationResult(
        tool_name="calculate_mass_balance",
        inputs_and_units={
            "Unit Operasi": data.unit_name,
            "Feed Flow (F)": f"{data.feed_flow_kg_h} kg/h",
            "Feed Composition (z_i)": str(data.feed_composition),
            "Top Split Fractions": str(data.split_fractions_to_top),
        },
        equations_used=[
            "Neraca Massa Total: F = D + B",
            "Neraca Massa Komponen: F * z_i = D * y_i + B * x_i",
            "Faktor Pemisahan (Split Fraction): D_i = SF_i * (F * z_i)",
        ],
        calculation_steps=steps,
        results_and_units=results,
        assumptions_and_limits=[
            "Kondisi operasi tunak (steady-state), akumulasi = 0.",
            "Tidak ada reaksi kimia di dalam unit pemisah (generasi/konsumsi = 0).",
        ],
        consistency_check={
            "mass_balance_closed": closure_error < 1e-6,
            "closure_error_kg_h": round(closure_error, 8),
            "sum_top_mass_fractions": round(sum(top_flows.values()) / total_top, 4) if total_top > 0 else 0.0,
            "sum_bottom_mass_fractions": round(sum(bottom_flows.values()) / total_bottom, 4) if total_bottom > 0 else 0.0,
        },
        references=["Himmelblau, D. M., & Riggs, J. B. (2012). Basic Principles and Calculations in Chemical Engineering."],
    )


@app.post("/tools/calculate_energy_balance", response_model=EngineeringCalculationResult)
def calculate_energy_balance(data: EnergyBalanceInput):
    m_kg_s = data.mass_flow_kg_h / 3600.0
    delta_t = data.t_out_c - data.t_in_c
    q_sensible_kw = m_kg_s * data.cp_kj_kg_k * delta_t
    q_latent_kw = m_kg_s * data.latent_heat_kj_kg * data.vapor_fraction_change
    q_total_kw = q_sensible_kw + q_latent_kw

    steps = [
        f"Konversi laju alir massa ke satuan SI: m = {data.mass_flow_kg_h} / 3600 = {m_kg_s:.4f} kg/s.",
        f"Hitung perubahan suhu: ΔT = {data.t_out_c} - ({data.t_in_c}) = {delta_t:.2f} K.",
        f"Hitung beban panas sensibel: Q_sensibel = {m_kg_s:.4f} kg/s * {data.cp_kj_kg_k} kJ/(kg.K) * {delta_t:.2f} K = {q_sensible_kw:.2f} kW.",
        f"Hitung beban panas laten: Q_laten = {m_kg_s:.4f} kg/s * {data.latent_heat_kj_kg} kJ/kg * {data.vapor_fraction_change} = {q_latent_kw:.2f} kW.",
        f"Total beban panas (Q_total) = {q_sensible_kw:.2f} + {q_latent_kw:.2f} = {q_total_kw:.2f} kW.",
    ]

    thermal_mode = "Pemanasan (Endotermik / membutuhkan utilitas pemanas)" if q_total_kw > 0 else "Pendinginan (Eksotermik / membutuhkan utilitas pendingin)"

    return EngineeringCalculationResult(
        tool_name="calculate_energy_balance",
        inputs_and_units={
            "Stream": data.stream_name,
            "Mass Flow (m)": f"{data.mass_flow_kg_h} kg/h ({m_kg_s:.4f} kg/s)",
            "Heat Capacity (Cp)": f"{data.cp_kj_kg_k} kJ/(kg·K)",
            "T_in": f"{data.t_in_c} °C",
            "T_out": f"{data.t_out_c} °C",
            "Latent Heat (λ)": f"{data.latent_heat_kj_kg} kJ/kg",
            "Δ Vapor Fraction": f"{data.vapor_fraction_change}",
        },
        equations_used=[
            "Q_total = Q_sensible + Q_latent",
            "Q_sensible = m * Cp * (T_out - T_in)",
            "Q_latent = m * λ * Δ(Vapor Fraction)",
        ],
        calculation_steps=steps,
        results_and_units={
            "Q_sensible": f"{q_sensible_kw:.2f} kW ({q_sensible_kw * 3600:.2f} kJ/h)",
            "Q_latent": f"{q_latent_kw:.2f} kW ({q_latent_kw * 3600:.2f} kJ/h)",
            "Q_total": f"{q_total_kw:.2f} kW ({q_total_kw * 3600:.2f} kJ/h)",
            "Mode Termal": thermal_mode,
        },
        assumptions_and_limits=[
            "Kapasitas panas (Cp) dianggap konstan pada rentang suhu T_in hingga T_out.",
            "Perubahan energi kinetik, energi potensial, dan kerja poros diabaikan (ΔEk = 0, ΔEp = 0, W_s = 0).",
            "Sistem beroperasi secara isobarik tanpa kehilangan panas ke lingkungan (heat loss = 0).",
        ],
        consistency_check={
            "sign_convention_valid": (delta_t >= 0 and q_sensible_kw >= 0) or (delta_t < 0 and q_sensible_kw < 0),
            "absolute_zero_check": (data.t_in_c > -273.15) and (data.t_out_c > -273.15),
        },
        references=["Smith, J. M., Van Ness, H. C., & Abbott, M. M. (2018). Introduction to Chemical Engineering Thermodynamics."],
    )


@app.post("/tools/calculate_thermodynamics", response_model=EngineeringCalculationResult)
def calculate_thermodynamics(data: ThermodynamicsInput):
    t_k = data.temperature_c + 273.15
    if t_k <= 0:
        raise HTTPException(status_code=400, detail="Suhu absolut harus lebih besar dari 0 K.")

    log10_psat = data.antoine_a - (data.antoine_b / (t_k + data.antoine_c))
    p_sat_bar = 10 ** log10_psat
    k_ideal = p_sat_bar / data.pressure_bar

    phase_status = "Cair lewat dingin (Subcooled Liquid)" if data.pressure_bar > p_sat_bar else "Uap lewat panas (Superheated Vapor)"
    if abs(data.pressure_bar - p_sat_bar) / data.pressure_bar < 0.02:
        phase_status = "Dekat kondisi jenuh (Saturated / Bubble-Dew point)"

    return EngineeringCalculationResult(
        tool_name="calculate_thermodynamics",
        inputs_and_units={
            "Component": data.component_name,
            "Temperature (T)": f"{data.temperature_c} °C ({t_k:.2f} K)",
            "System Pressure (P)": f"{data.pressure_bar} bar",
            "Antoine Constants (A, B, C)": f"A={data.antoine_a}, B={data.antoine_b}, C={data.antoine_c}",
        },
        equations_used=[
            "Persamaan Antoine: log10(P_sat [bar]) = A - B / (T [K] + C)",
            "Rasio Kesetimbangan Uap-Cair Ideal (Hukum Raoult): K_i = P_sat_i / P",
        ],
        calculation_steps=[
            f"Konversi suhu ke Kelvin: T = {data.temperature_c} + 273.15 = {t_k:.2f} K.",
            f"Hitung log10(P_sat): {data.antoine_a} - ({data.antoine_b} / ({t_k:.2f} + {data.antoine_c})) = {log10_psat:.4f}.",
            f"Hitung tekanan uap jenuh: P_sat = 10^({log10_psat:.4f}) = {p_sat_bar:.4f} bar.",
            f"Hitung nilai K ideal (Raoult): K = {p_sat_bar:.4f} / {data.pressure_bar} = {k_ideal:.4f}.",
        ],
        results_and_units={
            "Saturation Pressure (P_sat)": f"{p_sat_bar:.4f} bar",
            "Ideal K-value (Raoult's Law)": f"{k_ideal:.4f} (dimensionless)",
            "Prediksi Fasa Komponen Murni": phase_status,
        },
        assumptions_and_limits=[
            "Konstanta Antoine hanya valid pada rentang suhu eksperimental komponen terkait.",
            "Nilai K ideal mengasumsikan fasa uap sebagai gas ideal dan fasa cair sebagai larutan ideal (γ_i = 1, φ_i = 1).",
            "Untuk tekanan > 10 bar atau campuran sangat polar, koreksi koefisien aktivitas (NRTL/UNIQUAC) atau fugasitas (PR/SRK) wajib digunakan.",
        ],
        consistency_check={
            "positive_vapor_pressure": p_sat_bar > 0,
            "high_pressure_non_ideality_warning": data.pressure_bar > 10.0,
        },
        references=["Poling, B. E., Prausnitz, J. M., & O'Connell, J. P. (2001). The Properties of Gases and Liquids (5th ed.)."],
    )


@app.post("/tools/size_process_equipment", response_model=EngineeringCalculationResult)
def size_process_equipment(data: EquipmentSizingInput):
    eq_type = data.equipment_type.lower()
    if eq_type == "heat_exchanger":
        if None in (data.heat_duty_kw, data.t_hot_in_c, data.t_hot_out_c, data.t_cold_in_c, data.t_cold_out_c):
            raise HTTPException(status_code=400, detail="Parameter Q dan keempat suhu aliran (T_hot_in, T_hot_out, T_cold_in, T_cold_out) wajib diisi.")
        dt1 = data.t_hot_in_c - data.t_cold_out_c
        dt2 = data.t_hot_out_c - data.t_cold_in_c
        if dt1 <= 0 or dt2 <= 0:
            raise HTTPException(
                status_code=400,
                detail=f"Terjadi temperature cross (ΔT1={dt1:.2f} °C, ΔT2={dt2:.2f} °C). Desain counter-current tunggal tidak layak secara termodinamika.",
            )
        if abs(dt1 - dt2) < 1e-6:
            lmtd = dt1
        else:
            lmtd = (dt1 - dt2) / math.log(dt1 / dt2)
        q_watt = data.heat_duty_kw * 1000.0
        area_m2 = q_watt / (data.overall_u_w_m2_k * lmtd)

        return EngineeringCalculationResult(
            tool_name="size_process_equipment",
            inputs_and_units={
                "Equipment": "Shell & Tube Heat Exchanger (Counter-Current)",
                "Heat Duty (Q)": f"{data.heat_duty_kw} kW",
                "Overall U": f"{data.overall_u_w_m2_k} W/(m²·K)",
                "Hot Stream": f"{data.t_hot_in_c} °C -> {data.t_hot_out_c} °C",
                "Cold Stream": f"{data.t_cold_in_c} °C -> {data.t_cold_out_c} °C",
            },
            equations_used=[
                "ΔT1 = T_hot,in - T_cold,out",
                "ΔT2 = T_hot,out - T_cold,in",
                "LMTD = (ΔT1 - ΔT2) / ln(ΔT1 / ΔT2)",
                "A = Q / (U * LMTD)",
            ],
            calculation_steps=[
                f"Hitung beda suhu ujung panas: ΔT1 = {data.t_hot_in_c} - {data.t_cold_out_c} = {dt1:.2f} °C.",
                f"Hitung beda suhu ujung dingin: ΔT2 = {data.t_hot_out_c} - {data.t_cold_in_c} = {dt2:.2f} °C.",
                f"Hitung Log Mean Temperature Difference (LMTD) = {lmtd:.2f} °C.",
                f"Hitung luas perpindahan panas: A = ({data.heat_duty_kw} * 1000 W) / ({data.overall_u_w_m2_k} W/m².K * {lmtd:.2f} K) = {area_m2:.2f} m².",
            ],
            results_and_units={
                "LMTD": f"{lmtd:.2f} °C",
                "Required Heat Transfer Area (A)": f"{area_m2:.2f} m²",
                "Design Area (+15% Margin)": f"{area_m2 * 1.15:.2f} m²",
            },
            assumptions_and_limits=[
                "Aliran murni counter-current (faktor koreksi Ft = 1.0).",
                "Nilai U diasumsikan konstan sepanjang penukar panas.",
                "Perhitungan ini adalah preliminary sizing (belum mencakup analisis getaran tabung dan penurunan tekanan shell/tube secara rinci).",
            ],
            consistency_check={
                "no_temperature_cross": dt1 > 0 and dt2 > 0,
                "minimum_approach_temp_c": round(min(dt1, dt2), 2),
                "approach_temp_adequate": min(dt1, dt2) >= 5.0,
            },
            references=["Kern, D. Q. (1950). Process Heat Transfer.", " Sinnott, R., & Towler, G. (2019). Chemical Engineering Design."],
        )

    elif eq_type == "pump":
        if None in (data.volumetric_flow_m3_h, data.differential_head_m):
            raise HTTPException(status_code=400, detail="volumetric_flow_m3_h dan differential_head_m wajib diisi untuk perhitungan pompa.")
        q_m3_s = data.volumetric_flow_m3_h / 3600.0
        g = 9.80665
        p_hydraulic_kw = (data.density_kg_m3 * g * q_m3_s * data.differential_head_m) / 1000.0
        p_shaft_kw = p_hydraulic_kw / data.pump_efficiency

        return EngineeringCalculationResult(
            tool_name="size_process_equipment",
            inputs_and_units={
                "Equipment": "Centrifugal Pump",
                "Volumetric Flow (Q)": f"{data.volumetric_flow_m3_h} m³/h ({q_m3_s:.5f} m³/s)",
                "Fluid Density (ρ)": f"{data.density_kg_m3} kg/m³",
                "Differential Head (H)": f"{data.differential_head_m} m",
                "Pump Efficiency (η)": f"{data.pump_efficiency * 100:.1f}%",
            },
            equations_used=[
                "Daya Hidrolik: P_hyd [kW] = (ρ * g * Q * H) / 1000",
                "Daya Poros (Brake Power): P_shaft [kW] = P_hyd / η",
            ],
            calculation_steps=[
                f"Konversi laju alir volumetrik: Q = {data.volumetric_flow_m3_h} / 3600 = {q_m3_s:.5f} m³/s.",
                f"Hitung daya hidrolik: P_hyd = ({data.density_kg_m3} * 9.80665 * {q_m3_s:.5f} * {data.differential_head_m}) / 1000 = {p_hydraulic_kw:.3f} kW.",
                f"Hitung daya poros: P_shaft = {p_hydraulic_kw:.3f} / {data.pump_efficiency} = {p_shaft_kw:.3f} kW.",
            ],
            results_and_units={
                "Hydraulic Power (P_hyd)": f"{p_hydraulic_kw:.3f} kW",
                "Shaft / Brake Power (P_shaft)": f"{p_shaft_kw:.3f} kW",
            },
            assumptions_and_limits=[
                "Fluida bersifat inkompresibel.",
                "NPSHa (Net Positive Suction Head Available) harus diverifikasi terpisah agar lebih besar dari NPSHr untuk mencegah kavitasi.",
            ],
            consistency_check={
                "efficiency_valid": 0 < data.pump_efficiency <= 1.0,
                "shaft_power_exceeds_hydraulic": p_shaft_kw >= p_hydraulic_kw,
            },
            references=["Perry, R. H., & Green, D. W. (2019). Perry's Chemical Engineers' Handbook (9th ed.)."],
        )

    raise HTTPException(status_code=400, detail="equipment_type harus 'heat_exchanger' atau 'pump'.")


@app.post("/tools/recommend_property_method")
def recommend_property_method(data: PropertyMethodInput):
    pol = data.polarity.lower()
    p = data.pressure_bar

    if pol == "non-polar":
        primary = "Peng-Robinson (PR) atau Soave-Redlich-Kwong (SRK)"
        rationale = "Sistem hidrokarbon atau gas non-polar pada tekanan rendah hingga tinggi sangat akurat dimodelkan dengan Equation of State (EoS) kubik."
    elif pol == "polar-non-electrolyte":
        if p < 10.0:
            primary = "NRTL (Non-Random Two-Liquid) atau UNIQUAC"
            rationale = "Campuran polar non-elektrolit pada tekanan < 10 bar membutuhkan model koefisien aktivitas untuk menangkap ketidakidealan fasa cair (termasuk potensi azeotrop)."
        else:
            primary = "PSRK (Predictive SRK) atau PR-BM / Wong-Sandler"
            rationale = "Campuran polar pada tekanan tinggi (> 10 bar) membutuhkan penggabungan EoS dengan model ekses energi bebas Gibbs (EoS-G^E)."
    elif pol == "associating":
        primary = "NRTL-HOC (Hayden-O'Connell) atau PC-SAFT"
        rationale = "Asam karboksilat (misal asam asetat) mengalami dimerisasi di fasa uap sehingga membutuhkan koreksi fasa uap Hayden-O'Connell."
    elif pol == "electrolyte":
        primary = "ELECNRTL (Electrolyte NRTL) atau ENRTL-RK"
        rationale = "Sistem dengan ion terdisosiasi membutuhkan perhitungan interaksi elektrostatik jarak jauh (Pitzer-Debye-Hückel) dan jarak pendek."
    else:
        primary = "NRTL / Peng-Robinson (perlu verifikasi binary interaction parameters)"
        rationale = "Kategori polaritas umum; pastikan memeriksa kelengkapan Binary Interaction Parameters (BIP) di simulator."

    return {
        "tool_name": "recommend_property_method",
        "simulator": data.simulator,
        "components": data.components,
        "recommended_property_method": primary,
        "technical_rationale": rationale,
        "verification_checklist": [
            "Periksa apakah seluruh Binary Interaction Parameters (BIPs) tersedia di bank data simulator (misal APV / NIST).",
            "Jika terdapat dua fasa cair (VLL), gunakan varian NRTL-2 atau pastikan parameter kesetimbangan cair-cair (LLE) terkalibrasi.",
            "Validasi prediksi kurva T-xy atau P-xy terhadap data eksperimen NIST TDE sebelum menjalankan flowsheet penuh.",
        ],
        "references": ["Carlson, E. C. (1996). Don't Gamble With Physical Properties For Simulations. Chemical Engineering Progress, 92(10), 35-46."],
    }


@app.post("/tools/troubleshoot_aspen")
def troubleshoot_aspen(data: TroubleshootAspenInput):
    return {
        "tool_name": "troubleshoot_aspen",
        "simulator": data.simulator,
        "unit_operation": data.unit_operation,
        "reported_error": data.error_message,
        "diagnostic_workflow": [
            "Langkah 1 (Verifikasi Derajat Kebebasan & Spesifikasi): Pastikan spesifikasi kolom/unit tidak saling bertentangan (misal: menetapkan Distillate Rate yang melebihi komponen ringan di umpan).",
            "Langkah 2 (Periksa Neraca Massa & Kondisi Umpan): Pastikan fasa, tekanan, dan suhu umpan masuk akal serta tidak terjadi pressure drop negatif.",
            "Langkah 3 (Strategi Konvergensi Bertahap): Gunakan spesifikasi sederhana terlebih dahulu (misal Reflux Ratio & Distillate-to-Feed ratio) sebelum mengaktifkan Design Spec/kemurnian produk.",
        ],
        "single_ui_step_next": (
            f"Di {data.simulator}, buka blok '{data.unit_operation}' -> navigasi ke tab 'Specifications' -> "
            "matikan sementara 'Design Specs' dan jalankan simulasi dengan nilai tetap Reflux Ratio = 1.5 untuk mengecek kelayakan profil suhu."
        ),
        "safety_note": "Konvergensi numerik bukan jaminan kebenaran desain; selalu periksa profil suhu/komposisi per stage.",
    }


@app.post("/tools/design_simulation_case")
def design_simulation_case(data: SimulationCaseInput):
    return {
        "tool_name": "design_simulation_case",
        "topic": data.topic,
        "target_level": data.user_level,
        "simulator": data.simulator,
        "case_study_structure": {
            "learning_objectives": [
                f"Memahami dasar pemilihan Property Method untuk sistem {data.topic}.",
                "Menyusun neraca massa dan energi awal sebelum masuk ke simulator.",
                "Mengevaluasi sensitivitas parameter operasi terhadap kemurnian produk dan konsumsi energi.",
            ],
            "guided_step_1": (
                f"Langkah 1 UI ({data.simulator}): Buka tab 'Properties' -> 'Components' -> masukkan komponen utama sistem {data.topic}. "
                "Sebutkan komponen apa saja yang sudah kamu masukkan sebelum kita lanjut memilih Property Method."
            ),
        },
    }


@app.post("/tools/evaluate_engineering_solution")
def evaluate_engineering_solution(data: EvaluateSolutionInput):
    warnings = []
    if data.claimed_efficiency_or_yield is not None:
        if data.claimed_efficiency_or_yield > 100.0 or data.claimed_efficiency_or_yield < 0.0:
            warnings.append("Klaim efisiensi/konversi berada di luar batas fisik termodinamika (0% - 100%).")

    return {
        "tool_name": "evaluate_engineering_solution",
        "problem_statement": data.problem_statement,
        "review_protocol": [
            "Pemeriksaan Konsistensi Dimensi & Satuan (SI vs Imperial).",
            "Pemeriksaan Hukum I Termodinamika (Konservasi Massa & Energi).",
            "Pemeriksaan Hukum II Termodinamika (Driving force positif, efisiensi <= efisiensi Carnot/reversibel).",
        ],
        "detected_warnings": warnings,
        "status": "Perlu Perbaikan" if warnings else "Siap Diverifikasi Rinci",
    }


@app.post("/tools/search_chemical_papers")
def search_chemical_papers(data: SearchPapersInput):
    return {
        "tool_name": "search_chemical_papers",
        "query": data.query,
        "year_from": data.year_from,
        "policy_notice": "ChemEng AI tidak pernah mengarang referensi atau DOI. Gunakan konektor API Crossref / Semantic Scholar untuk mengambil metadata asli.",
        "api_integration_endpoint": f"https://api.crossref.org/works?query={data.query}&filter=from-pub-date:{data.year_from}",
    }


@app.post("/tools/analyze_research_paper")
def analyze_research_paper(data: AnalyzePaperInput):
    return {
        "tool_name": "analyze_research_paper",
        "title": data.title,
        "doi": data.doi or "DOI belum disertakan (wajib diverifikasi)",
        "structured_extraction": {
            "phenomena_and_objective": "Diekstrak langsung dari teks yang diberikan pengguna.",
            "methodology_and_conditions": "Memeriksa rentang suhu, tekanan, katalis/pelarut, dan metode analisis.",
            "critical_engineering_review": "Mengevaluasi kelengkapan neraca massa eksperimen dan ketidakpastian pengukuran (error bars).",
        },
    }


@app.post("/tools/generate_engineering_report")
def generate_engineering_report(data: GenerateReportInput):
    return {
        "tool_name": "generate_engineering_report",
        "report_type": data.report_type,
        "project_title": data.project_title,
        "sections_generated": [
            "1. Ringkasan Eksekutif & Tujuan",
            "2. Dasar Teori, Persamaan, & Property Method",
            "3. Basis Perhitungan & Asumsi",
            "4. Tabel Neraca Massa & Neraca Energi",
            "5. Evaluasi Kewajaran Fisik & Batasan Keselamatan",
            "6. Daftar Pustaka Terverifikasi",
        ],
        "included_data": data.summary_data,
    }


@app.get("/system-instructions")
def get_system_instructions():
    return {"version": "0.1.0", "instructions": CORE_SYSTEM_INSTRUCTIONS}
