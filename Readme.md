setup one-time

pip install ollama
ollama pull gemma4        # or gemma3:12b if gemma4 not available yet
ollama serve              # run in a separate terminal


Your furnace has 4 ultrasonic waveguide segments. Rio-Tinto.py continuously reads A-scan CSV files and tracks 5 acoustic echo peaks to calculate temperature. agent.py is the AI safety net that activates when that tracking goes wrong.

The 3 Components

1. auto_select_peaks() — Runs ONCE at startup
Opens first CSV → raw waveform (140,000 data points)
  ↓
Scans for peaks above threshold (0.3V)
  ↓
If not enough found → Auto-lowers threshold and tries again
  ↓
Picks the 5 most prominent echoes (by amplitude)
  ↓
Returns their sample indices → Rio-Tinto.py uses these to set gate windows
Replaces the old interactive_code() where you had to manually click peaks on a plot every time.

2. Watchdog.check() — Runs on EVERY A-scan (every file)
After Rio-Tinto.py calculates temperatures...
  ↓
Did any gate window shift > 200 samples? → ANOMALY
Did any echo amplitude drop below 0.1V?  → ANOMALY  (transducer uncoupled?)
Did any temperature go outside -50~1500°C? → ANOMALY (bad physics = wrong echo)
  ↓
All OK? → continue normally

3. agent_reselect() — Runs ONLY when Watchdog fires 🚨
This is where Gemma 4 takes over:

Watchdog detects anomaly on file 1(847).csv
  ↓
agent_reselect() called → Gemma 4 wakes up via Ollama
  ↓
┌─────────────────────────────────────────────────────────┐
│  GEMMA 4 AGENTIC LOOP                                   │
│                                                         │
│  Gemma: "Let me check the current state..."             │
│    → calls get_tracking_state()                         │
│    ← learns: peaks were at [12000, 25000, 38000, ...]   │
│                                                         │
│  Gemma: "Let me scan what echoes are visible now..."    │
│    → calls scan_candidates()                            │
│    ← gets list of 23 candidate echo positions           │
│                                                         │
│  Gemma: "Let me test if indices [11800, 24900...] fit"  │
│    → calls evaluate_layout([11800, 24900, 37800, ...])  │
│    ← score: 0.003 = EXCELLENT                           │
│                                                         │
│  Gemma: "That fits well. I'll commit this."             │
│    → calls commit_peaks([11800, 24900, 37800, ...])     │
└─────────────────────────────────────────────────────────┘
  ↓
New gate windows returned to Rio-Tinto.py
  ↓
Tracking continues from corrected positions
  ↓
Bad file is skipped (not written to DB)
  ↓
Next A-scan runs with correct gates ✅


Key Design Decisions


Decision	Why
Gemma 4 never sees raw float arrays	Would blow the token limit (140k floats)
Gemma only reads JSON summaries from tools	Keeps it fast and within context size
Fallback to pure math if Ollama is down	System never crashes because of the AI
Watchdog runs every scan (no LLM)	LLM is expensive — only call it when needed
Want me to also add logging so every anomaly and Gemma's recovery decision gets written to a log file for later review?