# run_enem_blocks.py
# PsychoPy >= 2022.2 recommended

from psychopy import visual, core, event, gui, data, logging
from psychopy.hardware import keyboard
import csv, os, time, random, sys


from psychopy import visual, core, event, gui, data, logging, prefs





print("Creating window...")

# =========================
# ======== CONFIG =========
# =========================

# Master switch: if False, no LSL/TTL imports or sends happen at all
USE_FNIRS = False          # <- Set False to test on your laptop without anything plugged

# If USE_FNIRS is True, choose transports:
USE_LSL = True             # Lab Streaming Layer markers
USE_TTL = False            # Parallel port TTL markers

# LSL config (used only if USE_FNIRS and USE_LSL)
LSL_STREAM_NAME = "psychopy_markers"
LSL_STREAM_TYPE = "Markers"

# TTL config (used only if USE_FNIRS and USE_TTL)
PARALLEL_PORT_ADDR = 0x0378  # Windows only

prefs.general['shutdownKey'] = 'escape'   # (optional quality-of-life)
# Crucial bits to avoid FPS sync stalls:
prefs.general['winType'] = 'glfw'         # more stable on many GPUs (Win/Linux)

# Markers
TRIGGER_MAP = {
    "Q_ON": 11,
    "OPT_ON": 12,
    "ANS_A": 21,
    "ANS_B": 22,
    "ANS_C": 23,
    "ANS_D": 24,
    "ANS_E": 25,
    "BLK_ON": 91,
    "BLK_OFF": 92,
    "ITI": 99,
    "QUESTIONNAIRE_ON": 71,
    "QUESTIONNAIRE_OFF": 72,
}

# Timing & display
STEM_MIN_VIEW_SECS = 2.0   # minimum time before revealing options
ITI_SECS = 3.0             # rest/fixation between trials (can be 0.0)
FULLSCREEN = True
WIN_SIZE = [1920, 1080]     # ignored if FULLSCREEN=True
FPS = 60                   # for simple frame-based waits

# Paths
TRIALS_CSV = os.path.join("stimuli", "enem_questions.csv")
SOCIO_CSV  = os.path.join("stimuli", "socio_questions.csv")
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Block flow
RANDOMIZE_TRIALS_WITHIN_BLOCK = False    # keep order per block or shuffle inside each block
BLOCK_ORDER_RANDOM = False               # randomize block order
# INSERT_QUESTIONNAIRE_AFTER_BLOCK = 1     # set to a block label/number or None to skip
SHOW_BLOCK_COUNTDOWN_SECS = 3            # 0 to skip countdown

# UI
STEM_TEXT_HEIGHT = 28
GEN_TEXT_HEIGHT  = 26
OPTION_TEXT_HEIGHT = 24
WRAP_FRAC = 0.9        # wrap width as a fraction of current window width


# --- Questionnaire placement ---
RUN_QUESTIONNAIRE_BEFORE = True   # <- run at the very start
INSERT_QUESTIONNAIRE_AFTER_BLOCK = None  # don't also run it mid-experiment


# =========================
# ====== SETUP CORE =======
# =========================

global_clock = core.MonotonicClock()
win = visual.Window(
    size=WIN_SIZE,
    fullscr=FULLSCREEN,
    color=[-1, -1, -1],
    units="pix",
    # Remove these problematic settings:
    # waitBlanking=False,
    # checkTiming=False,
    # useFBO=False,
    # multiSample=False
)
win.recordFrameIntervals = False   # don't collect interval stats



kb = keyboard.Keyboard()
mouse = event.Mouse(win=win)
wrap_w = int(WRAP_FRAC * win.size[0])

# Basic text elements
stem_text   = visual.TextStim(win, text="", color="white", height=STEM_TEXT_HEIGHT, wrapWidth=wrap_w, alignText='left')
prompt_text = visual.TextStim(win, text="", color="white", height=OPTION_TEXT_HEIGHT, pos=(0, -0.4*win.size[1]))
msg_text    = visual.TextStim(win, text="", color="white", height=GEN_TEXT_HEIGHT, pos=(0, 0))

# Button to reveal options
button_show     = visual.Rect(win, width=320, height=70, fillColor=[-0.2, -0.2, -0.2], lineColor="white", pos=(0, -200))
button_show_lbl = visual.TextStim(win, text="Show options", color="white", height=GEN_TEXT_HEIGHT, pos=(0, -200))

# Option buttons (A-E)
opt_boxes = []
opt_labels = []
opt_positions = [(-350, 80), (350, 80), (-350, -40), (350, -40), (0, -160)]
for i in range(5):
    box = visual.Rect(win, width=100, height=80, fillColor=[-0.2,-0.2,-0.2], lineColor="white", pos=opt_positions[i])
    lbl = visual.TextStim(win, text="", color="white", height=OPTION_TEXT_HEIGHT, pos=opt_positions[i], wrapWidth=wrap_w*0.9)
    opt_boxes.append(box)
    opt_labels.append(lbl)

# =========================
# ====== MARKERS I/O ======
# =========================

# Default no-op marker sender
class NoMarkerOutlet:
    def push_sample(self, *args, **kwargs):
        pass

outlet = NoMarkerOutlet()
pport = None  # parallel port handle if used

if USE_FNIRS:
    if USE_LSL:
        try:
            from pylsl import StreamInfo, StreamOutlet
            info = StreamInfo(LSL_STREAM_NAME, LSL_STREAM_TYPE, 1, 0, 'string', f'psychopy_{int(time.time())}')
            outlet = StreamOutlet(info)
            print("[LSL] Marker stream created.")
        except Exception as e:
            print("[LSL] ERROR:", e)
            USE_LSL = False

    if USE_TTL:
        try:
            from psychopy import parallel
            pport = parallel.ParallelPort(address=PARALLEL_PORT_ADDR)
            pport.setData(0)
            print("[TTL] Parallel port ready at", hex(PARALLEL_PORT_ADDR))
        except Exception as e:
            print("[TTL] ERROR:", e)
            USE_TTL = False

def send_marker(code_name: str):
    """
    Send marker via LSL and/or TTL (if enabled) and return (name, numeric, abs_time).
    If USE_FNIRS is False, this is a safe no-op.
    """
    t = global_clock.getTime()
    code_int = TRIGGER_MAP.get(code_name, 0)

    if USE_FNIRS and USE_LSL:
        try:
            outlet.push_sample([code_name], timestamp=core.getTime())
        except Exception as e:
            print("[LSL] send error:", e)

    if USE_FNIRS and USE_TTL and pport is not None and code_int > 0:
        try:
            pport.setData(code_int)
            core.wait(0.005)  # 5 ms pulse
            pport.setData(0)
        except Exception as e:
            print("[TTL] send error:", e)

    return code_name, code_int, t

# =========================
# ======== LOGGING ========
# =========================

exp_info = {"participant": "", "session": "001"}
dlg = gui.DlgFromDict(exp_info, title="ENEM fNIRS (Blocks)")
if not dlg.OK:
    core.quit()

timestamp = time.strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOG_DIR, f"enem_blocks_{exp_info['participant']}_{timestamp}.csv")
log_f = open(log_path, "w", newline="", encoding="utf-8")
log_writer = csv.writer(log_f)

log_writer.writerow([
    "t_abs", "phase", "block", "trial_idx_in_block",
    "question_id", "marker_name", "marker_code",
    "rt_from_phase", "choice", "correct", "note"
])
logging.console.setLevel(logging.WARNING)

def log_event(phase, block_label, trial_idx, qid, marker_name, code, t_phase_start, choice="", correct="", note=""):
    t_abs = global_clock.getTime()
    rt = t_abs - t_phase_start if t_phase_start is not None else ""
    log_writer.writerow([
        f"{t_abs:.6f}", phase, block_label, trial_idx, qid,
        marker_name, code, f"{rt}", choice, correct, note
    ])
    log_f.flush()

# =========================
# ======= HELPERS =========
# =========================

def wait_secs_draw(secs, drawlist=None):
    if secs <= 0:
        return
    t0 = core.Clock()
    while t0.getTime() < secs:
        if drawlist:
            for stim in drawlist:
                stim.draw()
        win.flip()  # Remove clearBuffer=True
        core.wait(0.001)  # Add small wait to prevent CPU maxing



def show_message(text, key_to_continue="space"):
    msg_text.text = text
    kb.clearEvents()  # Clear old events
    while True:
        msg_text.draw()
        win.flip()
        core.wait(0.001)  # Add this line
        keys = kb.getKeys([key_to_continue, 'escape'], waitRelease=False)
        if keys:
            if keys[0].name == 'escape':
                cleanup_and_quit()
            break

def block_countdown(block_label, secs):
    if secs <= 0:
        return
    for t in range(secs, 0, -1):
        msg_text.text = f"Block {block_label} starting in {t}..."
        msg_text.draw()
        win.flip()
        core.wait(1.0)

def cleanup_and_quit():
    log_f.close()
    win.close()
    core.quit()












# =========================
# == LOAD TRIALS/BLOCKS ===
# =========================

if not os.path.exists(TRIALS_CSV):
    cleanup_and_quit()

trials_by_block = {}
with open(TRIALS_CSV, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        block = row.get("block", "1").strip()
        trials_by_block.setdefault(block, []).append(row)

# order blocks
block_order = list(trials_by_block.keys())
if BLOCK_ORDER_RANDOM:
    random.shuffle(block_order)
else:
    # try numeric sort if possible
    try:
        block_order = sorted(block_order, key=lambda x: float(x))
    except:
        block_order = sorted(block_order)

# shuffle within block if desired
if RANDOMIZE_TRIALS_WITHIN_BLOCK:
    for b in block_order:
        random.shuffle(trials_by_block[b])

# =========================
# == LOAD QUESTIONNAIRE ===
# =========================


# === Socio-economic questionnaire (inline) ===
USE_INLINE_SOCIO = True  # <- set True to use the questions below; set False to use CSV if present

SOCIO_INLINE = [
    # Demographics
    {"qid": "age", "text": "What is your age?", "type": "text", "required": "yes"},
    {"qid": "gender", "text": "What is your gender?", "type": "choice",
     "options": "Woman,Man,", "required": "yes"},
    {"qid": "country_birth", "text": "Country of birth:", "type": "text", "required": "no"},
    {"qid": "home_language", "text": "Which language do you most often speak at home?", "type": "text", "required": "yes"},

    # Education & employment
    {"qid": "education", "text": "Highest level of education completed:", "type": "choice",
     "options": "Primary,Lower secondary,Upper secondary,Technical/Vocational,Bachelor,Master,Doctorate,Other", "required": "yes"},
    {"qid": "employment", "text": "Current employment status:", "type": "choice",
     "options": "Employed full-time,Employed part-time,Unemployed,Student,Self-employed,Other", "required": "no"},
    {"qid": "hours_work", "text": "If employed: average weekly working hours:", "type": "choice",
     "options": "0-10,11-20,21-30,31-40,41-50,50+", "required": "no"},

    # Household & income (use broad brackets for privacy)
    {"qid": "household_size", "text": "How many people live in your household (including you)?", "type": "choice",
     "options": "1,2,3,4,5,6,7+", "required": "yes"},
    {"qid": "household_children", "text": "How many children (under 18) live in your household?", "type": "choice",
     "options": "0,1,2,3,4+", "required": "no"},
    {"qid": "income_bracket", "text": "Approximate monthly household income (after tax):", "type": "choice",
     "options": "Prefer not to say, <1000, 1000-1999, 2000-2999, 3000-3999, 4000-4999, 5000+", "required": "no"},

    # Digital access
    {"qid": "internet_access", "text": "Do you have reliable internet access at home?", "type": "choice",
     "options": "Yes,No,Prefer not to say", "required": "no"},
    {"qid": "device_access", "text": "Which devices do you regularly use? (choose the most important)", "type": "choice",
     "options": "Smartphone,Laptop,Desktop,Tablet,Public/Shared computers,Other", "required": "no"},

    

]





socio_questions = []

if 'USE_INLINE_SOCIO' in globals() and USE_INLINE_SOCIO:
    socio_questions = SOCIO_INLINE
elif os.path.exists(SOCIO_CSV):
    with open(SOCIO_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            socio_questions.append(row)
# else: socio_questions remains empty (questionnaire skipped)

# Simple widgets for questionnaire
input_box = visual.Rect(win, width=wrap_w, height=60, fillColor=[-0.2,-0.2,-0.2], lineColor="white", pos=(0, -150))
input_text = visual.TextStim(win, text="", color="white", height=GEN_TEXT_HEIGHT, pos=(0, -150), wrapWidth=wrap_w*0.95)

def run_questionnaire(block_label="QNR"):
    """Run socio-economic questionnaire if CSV exists; logs responses."""
    if not socio_questions:
        return
    # Markers
    mname, mcode, _ = send_marker("QUESTIONNAIRE_ON")
    log_event("questionnaire", block_label, -1, "", mname, mcode, None, note="Questionnaire start")

    show_message("QUESTIONNAIRE\n\nAnswer the following questions.\nPress SPACE to continue for each item.")

    for q in socio_questions:
        qid   = q.get("qid", "").strip()
        text  = q.get("text", "").strip()
        qtype = q.get("type", "text").strip().lower()
        opts  = [o.strip() for o in q.get("options", "").split(",") if o.strip()]
        req   = (q.get("required", "no").strip().lower() == "yes")
        smin  = q.get("scale_min", "").strip()
        smax  = q.get("scale_max", "").strip()
        slbls = q.get("scale_labels", "").strip()

        answer = None
        t_start = global_clock.getTime()

        if qtype == "choice" and opts:
            # Render options as buttons
            choice_boxes = []
            choice_labels = []
            # Layout: up to two columns
            maxw = min(700, int(0.85 * win.size[0]))
            x_left, x_right = -maxw//4, maxw//4
            y = 120
            col_positions = []
            for i, opt in enumerate(opts):
                x = x_left if i % 2 == 0 else x_right
                col_positions.append((x, y))
                if i % 2 == 1:
                    y -= 80

            for i, (x,y) in enumerate(col_positions):
                b = visual.Rect(win, width=600, height=60, fillColor=[-0.2,-0.2,-0.2], lineColor="white", pos=(x, y))
                t = visual.TextStim(win, text=f"{i+1}) {opts[i]}", color="white", height=OPTION_TEXT_HEIGHT, pos=(x, y), wrapWidth=wrap_w*0.9)
                choice_boxes.append(b)
                choice_labels.append(t)

            prompt = visual.TextStim(win, text=text, color="white", height=GEN_TEXT_HEIGHT, wrapWidth=wrap_w, pos=(0, 200))
            sub = visual.TextStim(win, text="Press number key 1..N or click an option. SPACE to continue (if optional).", color="white", height=OPTION_TEXT_HEIGHT, pos=(0, -260))
            while answer is None:
                prompt.draw()
                for b, t in zip(choice_boxes, choice_labels):
                    b.draw(); t.draw()
                sub.draw()
                win.flip()

                if mouse.getPressed()[0]:
                    for i, b in enumerate(choice_boxes):
                        if b.contains(mouse):
                            answer = opts[i]
                            break

                keys = kb.getKeys([str(i+1) for i in range(len(opts))] + ['escape','space'], waitRelease=False)
                if keys:
                    name = keys[0].name
                    if name == 'escape':
                        cleanup_and_quit()
                    if name == 'space' and not req:
                        answer = ""
                    elif name.isdigit():
                        idx = int(name) - 1
                        if 0 <= idx < len(opts):
                            answer = opts[idx]

        elif qtype == "scale" and smin and smax:
            try:
                lo, hi = int(smin), int(smax)
            except:
                lo, hi = 1, 7
            anchors = ("","")
            if "|" in slbls:
                parts = slbls.split("|")
                anchors = (parts[0].strip(), parts[1].strip())

            prompt = visual.TextStim(win, text=f"{text}\n\nUse number keys {lo}..{hi}.", color="white", height=GEN_TEXT_HEIGHT, wrapWidth=wrap_w, pos=(0, 120))
            left_lab  = visual.TextStim(win, text=anchors[0], color="white", height=OPTION_TEXT_HEIGHT, pos=(-300, 40))
            right_lab = visual.TextStim(win, text=anchors[1], color="white", height=OPTION_TEXT_HEIGHT, pos=(300, 40))
            scale_marks = [visual.TextStim(win, text=str(v), color="white", height=OPTION_TEXT_HEIGHT, pos=(-300 + (600*(v-lo)/(hi-lo)), 0)) for v in range(lo, hi+1)]

            while answer is None:
                prompt.draw()
                left_lab.draw(); right_lab.draw()
                for s in scale_marks: s.draw()
                win.flip()

                keys = kb.getKeys([str(v) for v in range(lo, hi+1)] + ['escape','space'], waitRelease=False)
                if keys:
                    name = keys[0].name
                    if name == 'escape':
                        cleanup_and_quit()
                    if name == 'space' and not req:
                        answer = ""
                    elif name.isdigit():
                        v = int(name)
                        if lo <= v <= hi:
                            answer = str(v)

        else:
            # Free text input
            prompt = visual.TextStim(win, text=f"{text}\n(Type your answer. ENTER to confirm.)", color="white", height=GEN_TEXT_HEIGHT, wrapWidth=wrap_w, pos=(0, 60))
            typed = ""
            while True:
                prompt.draw()
                input_box.draw()
                input_text.text = typed
                input_text.draw()
                win.flip()

                keys = kb.getKeys(waitRelease=False)
                for k in keys:
                    if k.name == 'escape':
                        cleanup_and_quit()
                    elif k.name == 'backspace':
                        typed = typed[:-1]
                    elif k.name in ('return','num_enter'):
                        if req and len(typed.strip()) == 0:
                            # require non-empty
                            pass
                        else:
                            answer = typed
                            break
                    elif len(k.name) == 1:
                        typed += k.name
                if answer is not None:
                    break

        # Log response
        log_event(
            phase="questionnaire_item", block_label=block_label, trial_idx=-1, qid=qid,
            marker_name="QNR_ITEM", code=0, t_phase_start=t_start,
            choice=answer if answer is not None else "", correct="", note=f"type={qtype}"
        )

    # Markers
    mname, mcode, _ = send_marker("QUESTIONNAIRE_OFF")
    log_event("questionnaire", block_label, -1, "", mname, mcode, None, note="Questionnaire end")



# =========================
# ===== TRIAL ROUTINE =====
# =========================

def run_trial(block_label, idx_in_block, tr):
    qid = tr.get("question_id", f"{block_label}_{idx_in_block:03d}")
    stem = tr["stem"].strip()
    options = [tr["optionA"], tr["optionB"], tr["optionC"], tr["optionD"], tr["optionE"]]
    correct = tr.get("correct", "").strip().upper()

    # ITI
    iti_start = global_clock.getTime()
    msg_text.text = "+"
    wait_secs_draw(ITI_SECS, [msg_text])
    mname, mcode, _ = send_marker("ITI")
    log_event("iti", block_label, idx_in_block, qid, mname, mcode, iti_start)

    # STEM PHASE
    stem_text.text = stem
    prompt_text.text = "Read the question. Press SPACE or click the button to show options."
    show_options = False
    mouse.clickReset(); kb.clearEvents()
    stem_on = global_clock.getTime()
    mname, mcode, _ = send_marker("Q_ON")
    log_event("stem", block_label, idx_in_block, qid, mname, mcode, stem_on)

    while not show_options:
        stem_text.draw()
        prompt_text.draw()
        button_show.draw()
        button_show_lbl.draw()
        win.flip()
        core.wait(0.001)

        if global_clock.getTime() - stem_on < STEM_MIN_VIEW_SECS:
            continue

        keys = kb.getKeys(['space','escape'], waitRelease=False)
        if keys:
            if keys[0].name == 'escape':
                cleanup_and_quit()
            show_options = True
            break

        if mouse.getPressed()[0] and button_show.contains(mouse):
            show_options = True
            break

    # OPTIONS PHASE
    opt_on = global_clock.getTime()
    mname, mcode, _ = send_marker("OPT_ON")
    log_event("options", block_label, idx_in_block, qid, mname, mcode, opt_on)

    for k, lbl in enumerate(opt_labels):
        lbl.text = f"{chr(65+k)}) {options[k]}"

    chosen = None
    while chosen is None:
        stem_text.draw()
        for box, lbl in zip(opt_boxes, opt_labels):
            box.draw(); lbl.draw()
        win.flip()
        core.wait(0.001)

        if mouse.getPressed()[0]:
            for k, box in enumerate(opt_boxes):
                if box.contains(mouse):
                    chosen = chr(65+k)
                    break

        keys = kb.getKeys(['a','b','c','d','e','escape'], waitRelease=True)
        if keys:
            if keys[0].name == 'escape':
                cleanup_and_quit()
            name = keys[0].name.upper()
            if name in ['A','B','C','D','E']:
                chosen = name

    # ANSWER PHASE
    ans_marker = f"ANS_{chosen}"
    mname, mcode, _ = send_marker(ans_marker)
    is_correct = (chosen == correct) if correct in list("ABCDE") else ""
    log_event("answer", block_label, idx_in_block, qid, mname, mcode, opt_on, choice=chosen, correct=is_correct)

    # Minimal feedback
    fb = "Recorded" if is_correct == "" else ("Correct!" if is_correct else "Recorded")
    msg_text.text = fb
    wait_secs_draw(0.5, [msg_text])

# =========================
# ========= FLOW ==========
# =========================

# Experiment start
mname, mcode, _ = send_marker("BLK_ON")
log_event("block", "ALL", -1, "", mname, mcode, None, note="Experiment start")


show_message("Welcome!\n\nPress SPACE to begin.")

if RUN_QUESTIONNAIRE_BEFORE:
    run_questionnaire(block_label="PRE")  # will emit QUESTIONNAIRE_ON/OFF + log all items


for b in block_order:
    # Block header
    if SHOW_BLOCK_COUNTDOWN_SECS > 0:
        block_countdown(b, SHOW_BLOCK_COUNTDOWN_SECS)

    # Optional marker for block start (use BLK_ON/BLK_OFF to wrap whole exp; we log here as note)
    log_event("block_start", b, -1, "", "BLK_START_NOTE", 0, None, note=f"Entering block {b}")

    # Run all trials in this block
    for idx, tr in enumerate(trials_by_block[b], start=1):
        run_trial(b, idx, tr)

    # Block end note
    log_event("block_end", b, -1, "", "BLK_END_NOTE", 0, None, note=f"Leaving block {b}")

    # Insert questionnaire after a specific block
    if INSERT_QUESTIONNAIRE_AFTER_BLOCK is not None and str(b) == str(INSERT_QUESTIONNAIRE_AFTER_BLOCK):
        run_questionnaire(block_label=f"{b}_QNR")

# Experiment end
mname, mcode, _ = send_marker("BLK_OFF")
log_event("block", "ALL", -1, "", mname, mcode, None, note="Experiment end")

show_message("Thank you! Press SPACE to finish.")
cleanup_and_quit()
