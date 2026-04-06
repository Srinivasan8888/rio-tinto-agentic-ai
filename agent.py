"""
agent.py — Agentic AI using Local Gemma 4 via Ollama (NO LangChain)
====================================================================
Uses the ollama Python SDK directly to run a tool-calling loop
with local Gemma 4. The LLM acts as the supervisor — it decides
which DSP tools to call and interprets results to recover tracking.

Requirements:
    pip install ollama
    ollama pull gemma4          (or: ollama pull gemma3:12b)
    ollama serve                (must be running in background)

Architecture:
    auto_select_peaks  →  Pure DSP  (no LLM, runs at startup)
    Watchdog           →  Pure DSP  (no LLM, runs on every A-scan)
    agent_reselect     →  Gemma 4 agentic tool-calling loop (runs on anomaly)
"""

import json
import numpy as np
from scipy.signal import find_peaks

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    print("[AGENT] ⚠️  ollama package not found. Run: pip install ollama")
    print("[AGENT]     Falling back to pure algorithmic recovery.\n")


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1: INITIALIZATION  (Pure DSP — no LLM needed here)
# ──────────────────────────────────────────────────────────────────────────────

def auto_select_peaks(waveform, num_peaks, sample_freq_mhz, gauge_lengths_um,
                      min_height=0.3, min_distance=500):
    """
    Autonomously scans the acoustic environment and picks the best initial 
    echo positions. Adapts its sensitivity if not enough peaks are visible.
    """
    print("\n[AGENT] 🤖 Scanning acoustic environment for initial echoes...")
    peaks, properties = find_peaks(waveform, height=min_height, distance=min_distance)

    if len(peaks) < num_peaks:
        print(f"[AGENT] ⚠️  Only {len(peaks)} peaks above {min_height}V. Lowering threshold...")
        peaks, properties = find_peaks(waveform, height=min_height / 3, distance=min_distance)

    if len(peaks) < num_peaks:
        raise ValueError("[AGENT] ❌ Cannot find enough echoes to initialise tracking.")

    # Pick the N most prominent peaks (by amplitude), sorted chronologically
    top_idx = np.argsort(properties['peak_heights'])[-num_peaks:]
    selected = peaks[top_idx]
    selected.sort()

    print(f"[AGENT] ✅ Locked onto echo indices: {selected.tolist()}")
    return selected


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2: WATCHDOG  (Pure DSP — runs on every A-scan, triggers LLM on fail)
# ──────────────────────────────────────────────────────────────────────────────

class Watchdog:
    """
    Validates every reading against physical reality.
    Triggers agent_reselect() ONLY when something genuinely breaks.
    """
    def __init__(self, gauge_lengths_um, sample_freq_mhz, velocity_coeffs,
                 max_gate_shift=200, min_amplitude=0.1, temp_range=(-50, 1500)):
        self.gauge_lengths   = gauge_lengths_um
        self.sample_freq_mhz = sample_freq_mhz
        self.max_gate_shift  = max_gate_shift
        self.min_amplitude   = min_amplitude
        self.temp_range      = temp_range
        self.anomaly_reason  = ""

    def check(self, gtofs, amplitudes, gate_shifts, temperatures):
        self.anomaly_reason = ""

        for i, shift in enumerate(gate_shifts):
            if abs(shift) > self.max_gate_shift:
                self.anomaly_reason = (
                    f"Gate {i+1} jumped {shift:.0f} samples — "
                    f"tracker likely locked onto wrong echo."
                )
                return False

        for i, amp in enumerate(amplitudes):
            if amp < self.min_amplitude:
                self.anomaly_reason = (
                    f"Peak {i+1} amplitude collapsed to {amp:.3f}V — "
                    f"possible transducer uncoupling."
                )
                return False

        for i, temp in enumerate(temperatures):
            if not (self.temp_range[0] <= temp <= self.temp_range[1]):
                self.anomaly_reason = (
                    f"Segment {i+1} temperature {temp:.1f}°C is physically "
                    f"impossible (range: {self.temp_range[0]}–{self.temp_range[1]}°C)."
                )
                return False

        return True


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3: TOOLS  (Python functions the Gemma agent can call)
#   The model NEVER sees raw float arrays.
#   It only reads JSON summaries and decides which tool to call next.
# ──────────────────────────────────────────────────────────────────────────────

# Shared context injected before the agent loop starts
_ctx = {}

def _tool_get_tracking_state() -> dict:
    """Returns current peak positions and waveguide geometry."""
    return {
        "current_peak_indices": [int(p) for p in _ctx["current_peaks"]],
        "gauge_lengths_um":     _ctx["gauge_lengths"],
        "gate_half_width":      _ctx["gate"],
        "num_peaks_required":   len(_ctx["current_peaks"]),
    }

def _tool_scan_candidates(min_height: float = 0.08, min_distance: int = 300) -> dict:
    """Finds all echo candidates in the waveform above a threshold."""
    wav = _ctx["waveform"]
    peaks, props = find_peaks(wav, height=min_height, distance=min_distance)
    candidates = [
        {"index": int(p), "amplitude": round(float(wav[p]), 4)}
        for p in peaks
    ]
    return {
        "total_found": len(peaks),
        "candidates": candidates[:40],   # Cap at 40 to keep tokens low
        "note": "Indices are sample numbers. Amplitudes are in volts."
    }

def _tool_evaluate_layout(peak_indices: list) -> dict:
    """
    Scores a proposed peak layout against waveguide physical geometry.
    The Time-of-Flight ratios between echoes must match gauge length ratios.
    Lower geometry_fit_score = better match with physical reality.
    """
    L = _ctx["gauge_lengths"]
    n = len(_ctx["current_peaks"])
    total_L = sum(L)
    expected = [l / total_L for l in L]  # Expected TOF ratios from geometry

    if len(peak_indices) < n:
        return {"error": f"Need {n} indices, got {len(peak_indices)}"}

    peaks = sorted([int(p) for p in peak_indices[:n]])
    tofs = [peaks[j+1] - peaks[j] for j in range(n - 1)]
    total_tof = sum(tofs)

    if total_tof == 0:
        return {"error": "Zero total TOF — peaks cannot all be at same position"}

    actual = [t / total_tof for t in tofs]
    error  = sum((a - e) ** 2 for a, e in zip(actual, expected))

    return {
        "proposed_peaks":       peaks,
        "expected_tof_ratios":  [round(r, 4) for r in expected],
        "actual_tof_ratios":    [round(r, 4) for r in actual],
        "geometry_fit_score":   round(error * 100, 5),
        "verdict": (
            "EXCELLENT"   if error < 0.005 else
            "GOOD"        if error < 0.02  else
            "ACCEPTABLE"  if error < 0.05  else
            "POOR — try a different candidate sequence"
        )
    }

def _tool_commit_peaks(peak_indices: list) -> dict:
    """Commits the final corrected peak positions. Call this last."""
    gate  = _ctx["gate"]
    peaks = sorted([int(p) for p in peak_indices])
    gates = [(p - gate, p + gate) for p in peaks]
    _ctx["final_peaks"] = peaks
    _ctx["final_gates"] = gates
    return {
        "status":    "committed",
        "new_peaks": peaks,
        "new_gates": gates,
    }

# Tool registry — maps name → (function, schema for Ollama)
TOOLS = {
    "get_tracking_state": {
        "fn": _tool_get_tracking_state,
        "schema": {
            "type": "function",
            "function": {
                "name":        "get_tracking_state",
                "description": (
                    "Returns the current peak tracking positions and waveguide "
                    "physical parameters. Always call this first."
                ),
                "parameters":  {"type": "object", "properties": {}},
            },
        },
    },
    "scan_candidates": {
        "fn": _tool_scan_candidates,
        "schema": {
            "type": "function",
            "function": {
                "name":        "scan_candidates",
                "description": "Scan the waveform for all visible echo candidates.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min_height":   {
                            "type": "number",
                            "description": "Minimum amplitude in volts (default 0.08)"
                        },
                        "min_distance": {
                            "type": "integer",
                            "description": "Minimum spacing between peaks in samples (default 300)"
                        },
                    },
                },
            },
        },
    },
    "evaluate_layout": {
        "fn": _tool_evaluate_layout,
        "schema": {
            "type": "function",
            "function": {
                "name":        "evaluate_layout",
                "description": (
                    "Score a proposed sequence of peak indices against the "
                    "physical waveguide geometry. Lower score = better fit."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "peak_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of sample indices to evaluate e.g. [12000, 25000, 38500, 51000, 64000]"
                        },
                    },
                    "required": ["peak_indices"],
                },
            },
        },
    },
    "commit_peaks": {
        "fn": _tool_commit_peaks,
        "schema": {
            "type": "function",
            "function": {
                "name":        "commit_peaks",
                "description": (
                    "Commit the final corrected peak indices. "
                    "Call this LAST after finding the best layout."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "peak_indices": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "The final corrected peak sample indices"
                        },
                    },
                    "required": ["peak_indices"],
                },
            },
        },
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4: GEMMA 4 AGENTIC LOOP  (Direct Ollama — no LangChain)
# ──────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert acoustic signal processing agent in a Rio Tinto 
furnace monitoring system. The naive tracking algorithm has lost the ultrasonic echoes.

Your mission: Recover the correct peak positions using the available tools.

STRATEGY:
1. Call get_tracking_state — understand current positions and geometry.
2. Call scan_candidates — observe what echoes are actually visible.
3. Identify candidate sequences of 5 consecutive echoes from the candidates list.
4. Call evaluate_layout for each promising sequence — pick the LOWEST geometry_fit_score.
5. Call commit_peaks with your best sequence to restore tracking.

RULES:
- The waveguide gauge_lengths_um define the PHYSICAL spacing between echoes.
- Time-of-Flight ratios MUST approximately match gauge length ratios.
- Always commit before finishing — do NOT stop without calling commit_peaks.
- Be methodical. Try at least 3 different candidate sequences."""


def agent_reselect(waveform: np.ndarray, current_peaks: list, anomaly_reason: str,
                   sample_freq_mhz: float, gauge_lengths_um: list,
                   gate: int, db_path: str,
                   model: str = "gemma4",
                   max_iterations: int = 10):
    """
    Agentic peak recovery using local Gemma 4 via Ollama.

    Args:
        model:          Ollama model name ("gemma4", "gemma3:12b", "llama3.1" etc.)
        max_iterations: Safety limit on agent tool-call iterations
    """
    print(f"\n[AGENT] 🚨 ANOMALY: {anomaly_reason}")

    # ── Fallback if ollama not installed ────────────────────────────────────
    if not OLLAMA_AVAILABLE:
        print("[AGENT] 🔧 ollama not installed — using algorithmic fallback.")
        return _algorithmic_fallback(waveform, current_peaks, gauge_lengths_um, gate)

    # ── Inject context so tools can access waveform data ────────────────────
    _ctx.clear()
    _ctx.update({
        "waveform":      waveform,
        "current_peaks": current_peaks,
        "gauge_lengths": gauge_lengths_um,
        "gate":          gate,
    })

    tool_schemas = [t["schema"] for t in TOOLS.values()]

    # ── Initial message to the agent ─────────────────────────────────────────
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"ANOMALY DETECTED: {anomaly_reason}\n\n"
                f"The tracker has failed. Use your tools to find the correct "
                f"acoustic echo positions and commit the corrected peak layout."
            ),
        },
    ]

    print(f"[AGENT] 🧠 Starting Gemma 4 agentic loop (model: {model})...")
    print(f"[AGENT]    Ensure Ollama is running: ollama serve\n")

    # ── Agentic Loop: Gemma calls tools until it commits ────────────────────
    try:
        for iteration in range(max_iterations):
            print(f"[AGENT] ── Iteration {iteration + 1} ──────────────────────────")

            response = ollama.chat(
                model=model,
                messages=messages,
                tools=tool_schemas,
            )

            msg = response["message"]
            messages.append(msg)

            # No tool calls → agent finished reasoning
            if not msg.get("tool_calls"):
                print(f"[AGENT] 💬 Gemma: {msg['content'][:200]}")
                break

            # Execute each tool call the model requested
            for call in msg["tool_calls"]:
                tool_name = call["function"]["name"]
                tool_args = call["function"].get("arguments", {})

                print(f"[AGENT] 🔧 Calling tool: {tool_name}({tool_args})")

                if tool_name not in TOOLS:
                    result = {"error": f"Unknown tool: {tool_name}"}
                else:
                    try:
                        fn = TOOLS[tool_name]["fn"]
                        result = fn(**tool_args) if tool_args else fn()
                    except Exception as e:
                        result = {"error": str(e)}

                print(f"[AGENT]    Result: {json.dumps(result)[:200]}")

                # Feed tool result back to the model
                messages.append({
                    "role":    "tool",
                    "content": json.dumps(result),
                })

            # Stop early if agent already committed
            if "final_gates" in _ctx:
                print("\n[AGENT] ✅ Agent committed new peak positions — exiting loop.")
                break

        else:
            print(f"[AGENT] ⚠️  Reached max iterations ({max_iterations}) without commit.")

    except Exception as e:
        print(f"[AGENT] ❌ Ollama error: {e}")
        print("[AGENT] 🔧 Falling back to algorithmic recovery...")
        return _algorithmic_fallback(waveform, current_peaks, gauge_lengths_um, gate)

    # ── Return committed result (or fall back if agent didn't commit) ────────
    if "final_gates" in _ctx:
        print(f"[AGENT] ✅ New peaks: {_ctx['final_peaks']}")
        print("[AGENT] 🔄 Returning control to naive tracker.\n")
        return {
            "new_gates":      _ctx["final_gates"],
            "selected_peaks": _ctx["final_peaks"],
        }

    print("[AGENT] ⚠️  No commit made — using algorithmic fallback.")
    return _algorithmic_fallback(waveform, current_peaks, gauge_lengths_um, gate)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5: ALGORITHMIC FALLBACK  (Physics-ratio search, no LLM)
# ──────────────────────────────────────────────────────────────────────────────

def _algorithmic_fallback(waveform, current_peaks, gauge_lengths_um, gate):
    """Deterministic physics-ratio search. Runs when Ollama is unavailable."""
    print("[AGENT] 🔧 Running algorithmic fallback...")

    candidates, _ = find_peaks(waveform, height=0.08, distance=300)
    if len(candidates) < len(current_peaks):
        print("[AGENT] ❌ Too few echoes visible. Holding last known positions.")
        return {"new_gates": [(p - gate, p + gate) for p in current_peaks]}

    L = gauge_lengths_um
    total_L = sum(L)
    ratios = [l / total_L for l in L]
    num_req = len(current_peaks)
    best, best_score = None, float("inf")

    for i in range(len(candidates) - num_req + 1):
        seq = candidates[i:i + num_req]
        tofs = [seq[j+1] - seq[j] for j in range(num_req - 1)]
        total_tof = sum(tofs)
        if total_tof == 0:
            continue
        seq_ratios = [t / total_tof for t in tofs]
        ratio_err = sum((sr - r) ** 2 for sr, r in zip(seq_ratios, ratios))
        drift_err = sum((s - c) ** 2 for s, c in zip(seq, current_peaks)) / 1e8
        score = (ratio_err * 100) + drift_err
        if score < best_score:
            best_score = score
            best = seq

    if best is None:
        best = current_peaks

    print(f"[AGENT] ✅ Fallback selected peaks: {[int(p) for p in best]}")
    return {
        "new_gates":      [(int(p) - gate, int(p) + gate) for p in best],
        "selected_peaks": [int(p) for p in best],
    }