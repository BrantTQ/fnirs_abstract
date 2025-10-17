# run_enem_blocks.py
# PsychoPy >= 2022.2 recommended

from psychopy import visual, core, event, gui, data, logging
from psychopy.hardware import keyboard
import csv, os, time, random, sys, json
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

prefs.general['measureFrameRate'] = False

# Markers
TRIGGER_MAP = {
    "Q_TEXT_ON": 11,      # When question text appears
    "Q_FULL_ON": 12,      # When full question + options appear
    "BUTTON_CLICK": 13,   # When "show question" button clicked
    "ANS_A": 21,
    "ANS_B": 22,
    "ANS_C": 23,
    "ANS_D": 24,
    "ANS_E": 25,
    "BLK_ON": 91,
    "BLK_OFF": 92,
    "ITI": 99,
    "BLOCK_REST": 93,     # 30-second rest between blocks
    "QUESTIONNAIRE_ON": 71,
    "QUESTIONNAIRE_OFF": 72,
}

# Timing & display
MIN_ITI_SECS = 3.0             # Minimum inter-trial interval
MAX_ITI_SECS = 5.0             # Maximum inter-trial interval
BLOCK_REST_SECS = 30.0         # Rest between blocks
FULLSCREEN = True
WIN_SIZE = [1920, 1080]        # ignored if FULLSCREEN=True
FPS = 60                       # for simple frame-based waits

# Paths
QUESTIONS_JSON = r"C:\Users\thiago-ext\Documents\FNIRS\psychopy\filtered_questions.json"
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Block configuration
N_BLOCKS = 5                   # Number of blocks
QUESTIONS_PER_BLOCK = 4        # Questions per block
CONCRETE_PER_BLOCK = 2         # Concrete questions per block
ABSTRACT_PER_BLOCK = 2         # Abstract questions per block

# UI
STEM_TEXT_HEIGHT = 28
GEN_TEXT_HEIGHT = 26
OPTION_TEXT_HEIGHT = 24
WRAP_FRAC = 0.9        # wrap width as a fraction of current window width

# Questionnaire placement
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
    # checkTiming=False
    
)
win.recordFrameIntervals = False   # don't collect interval stats

kb = keyboard.Keyboard()
mouse = event.Mouse(win=win)
wrap_w = int(WRAP_FRAC * win.size[0])

# Basic text elements
question_text = visual.TextStim(win, text="", color="white", height=STEM_TEXT_HEIGHT, wrapWidth=wrap_w, alignText='left', pos=(0, 100))
question_itself = visual.TextStim(win, text="", color="white", height=GEN_TEXT_HEIGHT, wrapWidth=wrap_w, alignText='left', pos=(0, 200))
msg_text = visual.TextStim(win, text="", color="white", height=GEN_TEXT_HEIGHT, pos=(0, 0))

# Button to reveal full question
button_show = visual.Rect(win, width=320, height=70, fillColor=[-0.2, -0.2, -0.2], lineColor="white", pos=(0, -200))
button_show_lbl = visual.TextStim(win, text="Show question", color="white", height=GEN_TEXT_HEIGHT, pos=(0, -200))

# Option elements
opt_texts = []
opt_positions = [(0, 50), (0, -20), (0, -90), (0, -160), (0, -230)]
for i in range(5):
    opt = visual.TextStim(win, text="", color="white", height=OPTION_TEXT_HEIGHT, 
                          pos=opt_positions[i], wrapWidth=wrap_w*0.9, alignText='left')
    opt_texts.append(opt)

# Option buttons for clicking
opt_boxes = []
box_width = 60
box_positions = [(-wrap_w//2 + 30, pos[1]) for pos in opt_positions]
for i in range(5):
    box = visual.Rect(win, width=box_width, height=50, fillColor=[-0.2,-0.2,-0.2], 
                     lineColor="white", pos=box_positions[i])
    opt_boxes.append(box)

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

# Enhanced logging headers
log_writer.writerow([
    "t_abs", "phase", "block", "trial_idx_in_block", "question_number", "question_year", 
    "question_type", "question_field", "marker_name", "marker_code",
    "rt_from_phase", "choice", "correct", "button_click_time", "option_view_time", "note"
])
logging.console.setLevel(logging.WARNING)

def log_event(phase, block_label, trial_idx, q_data, marker_name, code, t_phase_start, 
              choice="", correct="", button_click_t="", opt_view_t="", note=""):
    t_abs = global_clock.getTime()
    rt = t_abs - t_phase_start if t_phase_start is not None else ""
    
    # Extract question metadata if available
    q_num = q_data.get("question_number", "") if isinstance(q_data, dict) else ""
    q_year = q_data.get("year", "") if isinstance(q_data, dict) else ""
    q_type = q_data.get("type", "") if isinstance(q_data, dict) else ""
    q_field = q_data.get("field", "") if isinstance(q_data, dict) else ""
    
    log_writer.writerow([
        f"{t_abs:.6f}", phase, block_label, trial_idx, q_num, q_year,
        q_type, q_field, marker_name, code, f"{rt}", choice, correct, 
        button_click_t, opt_view_t, note
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
        win.flip()
        core.wait(0.001)

def show_message(text, key_to_continue="space"):
    msg_text.text = text
    kb.clearEvents()
    while True:
        msg_text.draw()
        win.flip()
        core.wait(0.001)
        keys = kb.getKeys([key_to_continue, 'escape'], waitRelease=False)
        if keys:
            if keys[0].name == 'escape':
                cleanup_and_quit()
            break

def block_rest(block_num):
    """30-second rest between blocks with countdown"""
    if block_num >= N_BLOCKS:  # Don't rest after last block
        return
    
    mname, mcode, _ = send_marker("BLOCK_REST")
    log_event("block_rest", f"B{block_num}", -1, {}, mname, mcode, None, 
              note=f"30s rest after block {block_num}")
    
    rest_clock = core.Clock()
    while rest_clock.getTime() < BLOCK_REST_SECS:
        remaining = BLOCK_REST_SECS - rest_clock.getTime()
        msg_text.text = f"Rest\n\nNext block in {int(remaining)} seconds..."
        msg_text.draw()
        win.flip()
        
        keys = kb.getKeys(['escape'], waitRelease=False)
        if keys:
            cleanup_and_quit()

def cleanup_and_quit():
    log_f.close()
    win.close()
    core.quit()

# =========================
# == LOAD QUESTIONS =======
# =========================

def load_questions():
    """Load questions from JSON file"""
    if not os.path.exists(QUESTIONS_JSON):
        print(f"ERROR: Questions file not found: {QUESTIONS_JSON}")
        cleanup_and_quit()
    
    with open(QUESTIONS_JSON, 'r', encoding='utf-8') as f:
        all_questions = json.load(f)
    
    # Separate by type
    concrete_questions = [q for q in all_questions if q.get("type") == "concrete"]
    abstract_questions = [q for q in all_questions if q.get("type") == "abstract"]
    
    # Shuffle both pools
    random.shuffle(concrete_questions)
    random.shuffle(abstract_questions)
    
    return concrete_questions, abstract_questions

def create_blocks(concrete_questions, abstract_questions):
    """Create blocks with proper distribution of question types"""
    blocks = []
    
    for block_idx in range(N_BLOCKS):
        block_questions = []
        
        # Add concrete questions
        for _ in range(CONCRETE_PER_BLOCK):
            if concrete_questions:
                block_questions.append(concrete_questions.pop(0))
        
        # Add abstract questions
        for _ in range(ABSTRACT_PER_BLOCK):
            if abstract_questions:
                block_questions.append(abstract_questions.pop(0))
        
        # Shuffle within block
        random.shuffle(block_questions)
        blocks.append(block_questions)
    
    return blocks

# =========================
# == QUESTIONNAIRE ========
# =========================

SOCIO_INLINE = [
    {"qid": "age", "text": "What is your age?", "type": "text", "required": "yes"},
    {"qid": "gender", "text": "What is your gender?", "type": "choice",
     "options": "Woman,Man,Other", "required": "yes"},
    {"qid": "country_birth", "text": "Country of birth:", "type": "text", "required": "no"},
    {"qid": "home_language", "text": "Which language do you most often speak at home?", "type": "text", "required": "yes"},
]

def run_questionnaire(block_label="QNR"):
    """Run socio-economic questionnaire"""
    socio_questions = SOCIO_INLINE
    
    if not socio_questions:
        return
    
    mname, mcode, _ = send_marker("QUESTIONNAIRE_ON")
    log_event("questionnaire", block_label, -1, {}, mname, mcode, None, note="Questionnaire start")
    
    show_message("QUESTIONNAIRE\n\nAnswer the following questions.\nPress SPACE to continue.")
    
    input_box = visual.Rect(win, width=wrap_w, height=60, fillColor=[-0.2,-0.2,-0.2], 
                           lineColor="white", pos=(0, -150))
    input_text = visual.TextStim(win, text="", color="white", height=GEN_TEXT_HEIGHT, 
                                pos=(0, -150), wrapWidth=wrap_w*0.95)
    
    for q in socio_questions:
        qid = q.get("qid", "").strip()
        text = q.get("text", "").strip()
        qtype = q.get("type", "text").strip().lower()
        opts = [o.strip() for o in q.get("options", "").split(",") if o.strip()]
        req = (q.get("required", "no").strip().lower() == "yes")
        
        answer = None
        t_start = global_clock.getTime()
        
        if qtype == "choice" and opts:
            # Choice question implementation
            choice_boxes = []
            choice_labels = []
            
            for i, opt in enumerate(opts):
                y_pos = 100 - (i * 80)
                b = visual.Rect(win, width=400, height=60, fillColor=[-0.2,-0.2,-0.2], 
                              lineColor="white", pos=(0, y_pos))
                t = visual.TextStim(win, text=f"{i+1}) {opt}", color="white", 
                                   height=OPTION_TEXT_HEIGHT, pos=(0, y_pos))
                choice_boxes.append(b)
                choice_labels.append(t)
            
            prompt = visual.TextStim(win, text=text, color="white", height=GEN_TEXT_HEIGHT, 
                                    wrapWidth=wrap_w, pos=(0, 200))
            
            while answer is None:
                prompt.draw()
                for b, t in zip(choice_boxes, choice_labels):
                    b.draw()
                    t.draw()
                win.flip()
                
                if mouse.getPressed()[0]:
                    for i, b in enumerate(choice_boxes):
                        if b.contains(mouse):
                            answer = opts[i]
                            break
                
                keys = kb.getKeys([str(i+1) for i in range(len(opts))] + ['escape','space'], 
                                 waitRelease=False)
                if keys:
                    name = keys[0].name
                    if name == 'escape':
                        cleanup_and_quit()
                    elif name.isdigit():
                        idx = int(name) - 1
                        if 0 <= idx < len(opts):
                            answer = opts[idx]
        
        else:
            # Text input implementation
            prompt = visual.TextStim(win, text=f"{text}\n(Type your answer. ENTER to confirm.)", 
                                    color="white", height=GEN_TEXT_HEIGHT, wrapWidth=wrap_w, pos=(0, 60))
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
            phase="questionnaire_item", block_label=block_label, trial_idx=-1, 
            q_data={"qid": qid}, marker_name="QNR_ITEM", code=0, t_phase_start=t_start,
            choice=answer if answer is not None else "", correct="", note=f"type={qtype}"
        )
    
    mname, mcode, _ = send_marker("QUESTIONNAIRE_OFF")
    log_event("questionnaire", block_label, -1, {}, mname, mcode, None, note="Questionnaire end")

# =========================
# ===== TRIAL ROUTINE =====
# =========================

def run_trial(block_label, idx_in_block, question_data):
    """Run a single trial with two-phase presentation"""
    
    # Random ITI between 3-5 seconds
    iti_duration = random.uniform(MIN_ITI_SECS, MAX_ITI_SECS)
    iti_start = global_clock.getTime()
    msg_text.text = "+"
    wait_secs_draw(iti_duration, [msg_text])
    mname, mcode, _ = send_marker("ITI")
    log_event("iti", block_label, idx_in_block, question_data, mname, mcode, iti_start,
              note=f"ITI duration: {iti_duration:.2f}s")
    
    # PHASE 1: Question text only
    question_text.text = question_data["question_text_translated"]
    text_on = global_clock.getTime()
    mname, mcode, _ = send_marker("Q_TEXT_ON")
    log_event("question_text", block_label, idx_in_block, question_data, mname, mcode, text_on)
    
    show_full_question = False
    mouse.clickReset()
    kb.clearEvents()
    
    while not show_full_question:
        question_text.draw()
        button_show.draw()
        button_show_lbl.draw()
        win.flip()
        core.wait(0.001)
        
        # Check for button click
        if mouse.getPressed()[0] and button_show.contains(mouse):
            button_click_time = global_clock.getTime()
            mname, mcode, _ = send_marker("BUTTON_CLICK")
            show_full_question = True
        
        # Check for keyboard
        keys = kb.getKeys(['space', 'escape'], waitRelease=False)
        if keys:
            if keys[0].name == 'escape':
                cleanup_and_quit()
            button_click_time = global_clock.getTime()
            mname, mcode, _ = send_marker("BUTTON_CLICK")
            show_full_question = True
    
    # PHASE 2: Full question with options
    full_on = global_clock.getTime()
    mname, mcode, _ = send_marker("Q_FULL_ON")
    log_event("question_full", block_label, idx_in_block, question_data, mname, mcode, full_on,
              button_click_t=f"{button_click_time:.6f}")
    
    # Set up question and options
    question_itself.text = question_data["question_itself_translated"]
    
    option_fields = ["question_option_A_translated", "question_option_B_translated",
                    "question_option_C_translated", "question_option_D_translated",
                    "question_option_E_translated"]
    
    for i, field in enumerate(option_fields):
        letter = chr(65 + i)  # A, B, C, D, E
        opt_texts[i].text = f"{letter}) {question_data[field]}"
    
    # Wait for answer
    chosen = None
    mouse.clickReset()
    kb.clearEvents()
    
    while chosen is None:
        question_itself.draw()
        
        for i in range(5):
            opt_texts[i].draw()
            opt_boxes[i].draw()
        
        win.flip()
        core.wait(0.001)
        
        # Check mouse clicks on option boxes
        if mouse.getPressed()[0]:
            for i, box in enumerate(opt_boxes):
                if box.contains(mouse):
                    chosen = chr(65 + i)  # A, B, C, D, E
                    break
        
        # Check keyboard
        keys = kb.getKeys(['a','b','c','d','e','1','2','3','4','5','escape'], waitRelease=True)
        if keys:
            if keys[0].name == 'escape':
                cleanup_and_quit()
            elif keys[0].name in ['a','b','c','d','e']:
                chosen = keys[0].name.upper()
            elif keys[0].name in ['1','2','3','4','5']:
                chosen = chr(64 + int(keys[0].name))  # Convert 1->A, 2->B, etc.
    
    # Log answer
    ans_marker = f"ANS_{chosen}"
    mname, mcode, _ = send_marker(ans_marker)
    answer_time = global_clock.getTime()
    
    log_event("answer", block_label, idx_in_block, question_data, mname, mcode, full_on,
              choice=chosen, opt_view_t=f"{answer_time - full_on:.6f}")
    
    # Brief feedback
    msg_text.text = "Response recorded"
    wait_secs_draw(0.5, [msg_text])

# =========================
# ========= MAIN ==========
# =========================

# Experiment start
log_event("experiment", "START", -1, {}, "EXP_START", 0, None, 
          note=f"Experiment started at {time.strftime('%Y-%m-%d %H:%M:%S')}")

show_message("Welcome!\n\nPress SPACE to begin.")

# Run pre-experiment questionnaire if configured
if RUN_QUESTIONNAIRE_BEFORE:
    run_questionnaire(block_label="PRE")

# Load and organize questions
concrete_q, abstract_q = load_questions()
blocks = create_blocks(concrete_q, abstract_q)

# Run blocks
for block_idx, block_questions in enumerate(blocks, start=1):
    # Block start
    mname, mcode, _ = send_marker("BLK_ON")
    log_event("block_start", f"B{block_idx}", -1, {}, mname, mcode, None,
              note=f"Block {block_idx} of {N_BLOCKS}")
    
    show_message(f"BLOCK {block_idx} of {N_BLOCKS}\n\nPress SPACE to continue.")
    
    # Run trials in block
    for trial_idx, question in enumerate(block_questions, start=1):
        run_trial(f"B{block_idx}", trial_idx, question)
    
    # Block end
    mname, mcode, _ = send_marker("BLK_OFF")
    log_event("block_end", f"B{block_idx}", -1, {}, mname, mcode, None,
              note=f"Block {block_idx} completed")
    
    # Rest between blocks (except after last block)
    if block_idx < N_BLOCKS:
        block_rest(block_idx)

# Experiment end
log_event("experiment", "END", -1, {}, "EXP_END", 0, None,
          note=f"Experiment ended at {time.strftime('%Y-%m-%d %H:%M:%S')}")

show_message("Thank you for participating!\n\nPress SPACE to finish.")
cleanup_and_quit()
