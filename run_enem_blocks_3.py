# run_enem_blocks.py
# PsychoPy >= 2022.2 recommended

# ---- prefs BEFORE imports that create windows ----
from psychopy import prefs
prefs.general['measureFrameRate'] = False
prefs.general['shutdownKey'] = 'escape'
prefs.general['autoLog'] = False

from psychopy import visual, core, event, gui, data, logging
from psychopy.hardware import keyboard
import csv, os, time, random, sys, json

logging.console.setLevel(logging.ERROR)

# ===== paths =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

# ===== config =====
USE_FNIRS = False
USE_LSL = True
USE_TTL = False
LSL_STREAM_NAME = "psychopy_markers"
LSL_STREAM_TYPE = "Markers"
PARALLEL_PORT_ADDR = 0x0378

TRIGGER_MAP = {
    "Q_TEXT_ON": 11,
    "Q_FULL_ON": 12,     # kept for compatibility (unused here)
    "BUTTON_CLICK": 13,
    "Q_STEM_ON": 14,     # question (stem) is shown
    "Q_OPTIONS_ON": 15,  # options are shown
    "ANS_A": 21, "ANS_B": 22, "ANS_C": 23, "ANS_D": 24, "ANS_E": 25,
    "BLK_ON": 91, "BLK_OFF": 92, "ITI": 99, "BLOCK_REST": 93,
    "QUESTIONNAIRE_ON": 71, "QUESTIONNAIRE_OFF": 72,
}

MIN_ITI_SECS = 3.0
MAX_ITI_SECS = 5.0
FULLSCREEN = False
WIN_SIZE = [1920, 1100]
BLOCK_DURATION_SECS = 7 * 60

QUESTIONS_JSON = r"C:\Users\thiago-ext\Documents\FNIRS\psychopy\filtered_questions.json"

BLOCKS_PER_TYPE = 5
QUESTIONS_PER_BLOCK = 3
N_BLOCKS = BLOCKS_PER_TYPE * 2

STEM_TEXT_HEIGHT = 28
GEN_TEXT_HEIGHT = 26
OPTION_TEXT_HEIGHT = 24

RUN_QUESTIONNAIRE_BEFORE = True
INSERT_QUESTIONNAIRE_AFTER_BLOCK = None

# ===== core/window =====
global_clock = core.MonotonicClock()

print("Initializing window (this may take a moment)...")
try:
    win = visual.Window(
        size=WIN_SIZE, fullscr=FULLSCREEN, color=[1, 1, 1], units="pix",
        waitBlanking=False, autoLog=False
    )
    win.recordFrameIntervals = False
    print("Window created successfully!")
except Exception as e:
    print(f"ERROR creating window: {e}")
    print("Trying alternative window creation...")
    try:
        win = visual.Window(size=WIN_SIZE, fullscr=False, color=[-1,-1,-1], units="pix")
        print("Window created with fallback method!")
    except Exception as e2:
        print(f"FATAL ERROR: Could not create window: {e2}")
        sys.exit(1)

kb = keyboard.Keyboard()
mouse = event.Mouse(win=win)

# ===== layout (fixed left margin; no overlap) =====
SCREEN_W, SCREEN_H = win.size
LEFT_X = -SCREEN_W//2 + 60   # visible left margin
WRAP_PIX = int(SCREEN_W * 0.86)

TEXT_Y     = 320
QUESTION_Y = 160
OPTIONS_Y0 =  40
OPTION_STEP = -70
BUTTON_Y   = -320

question_text = visual.TextStim(
    win, text="", color="black", height=STEM_TEXT_HEIGHT,
    wrapWidth=WRAP_PIX, alignText='left', pos=(LEFT_X, TEXT_Y),
    anchorHoriz='left', anchorVert='center'
)
question_itself = visual.TextStim(
    win, text="", color="black", height=GEN_TEXT_HEIGHT,
    wrapWidth=WRAP_PIX, alignText='left', pos=(LEFT_X, QUESTION_Y),
    anchorHoriz='left', anchorVert='center'
)
msg_text = visual.TextStim(win, text="", color="black", height=GEN_TEXT_HEIGHT, pos=(0, 0))

button_show = visual.Rect(
    win, width=360, height=64, fillColor=[-0.2,-0.2,-0.2],
    lineColor="black", pos=(0, BUTTON_Y)
)
button_show_lbl = visual.TextStim(
    win, text="Show question", color="black", height=GEN_TEXT_HEIGHT, pos=(0, BUTTON_Y)
)

opt_texts, opt_boxes = [], []
for i in range(5):
    y = OPTIONS_Y0 + i*OPTION_STEP
    t = visual.TextStim(
        win, text="", color="black", height=OPTION_TEXT_HEIGHT,
        wrapWidth=WRAP_PIX, alignText='left', pos=(LEFT_X + 44, y),
        anchorHoriz='left', anchorVert='center'
    )
    opt_texts.append(t)
    b = visual.Rect(
        win, width=46, height=46, fillColor=[-0.2,-0.2,-0.2],
        lineColor="black", pos=(LEFT_X + 18, y)
    )
    opt_boxes.append(b)

# ===== markers I/O =====
class NoMarkerOutlet:
    def push_sample(self, *args, **kwargs): pass

outlet = NoMarkerOutlet()
pport = None
if USE_FNIRS:
    if USE_LSL:
        try:
            from pylsl import StreamInfo, StreamOutlet
            info = StreamInfo(LSL_STREAM_NAME, LSL_STREAM_TYPE, 1, 0, 'string', f'psychopy_{int(time.time())}')
            outlet = StreamOutlet(info)
            print("[LSL] Marker stream created.")
        except Exception as e:
            print("[LSL] ERROR:", e); USE_LSL = False
    if USE_TTL:
        try:
            from psychopy import parallel
            pport = parallel.ParallelPort(address=PARALLEL_PORT_ADDR)
            pport.setData(0); print("[TTL] Parallel port ready at", hex(PARALLEL_PORT_ADDR))
        except Exception as e:
            print("[TTL] ERROR:", e); USE_TTL = False

def send_marker(code_name: str):
    t = global_clock.getTime()
    code_int = TRIGGER_MAP.get(code_name, 0)
    if USE_FNIRS and USE_LSL:
        try:
            outlet.push_sample([code_name], timestamp=core.getTime())
        except Exception as e:
            print("[LSL] send error:", e)
    if USE_FNIRS and USE_TTL and pport is not None and code_int > 0:
        try:
            pport.setData(code_int); core.wait(0.005); pport.setData(0)
        except Exception as e:
            print("[TTL] send error:", e)
    return code_name, code_int, t

# ===== logging =====
exp_info = {"participant": "", "session": "001"}
dlg = gui.DlgFromDict(exp_info, title="ENEM fNIRS (Blocks)")
if not dlg.OK: core.quit()

timestamp = time.strftime("%Y%m%d_%H%M%S")
log_path = os.path.join(LOG_DIR, f"enem_blocks_{exp_info['participant']}_{timestamp}.csv")
try:
    log_f = open(log_path, "w", newline="", encoding="utf-8")
except Exception as e:
    print(f"[LOG] Could not open log file: {e}")
    try:
        msg_text.text = "Error: cannot open log file. Check write permissions."
        msg_text.draw(); win.flip(); core.wait(2.0)
    except Exception: pass
    sys.exit(1)

print(f"[LOG] Writing to: {os.path.abspath(log_path)}")
log_writer = csv.writer(log_f)
log_writer.writerow([
    "t_abs","phase","block","trial_idx_in_block","question_number","question_year",
    "question_type","question_field","marker_name","marker_code",
    "rt_from_phase","choice","correct","button_click_time","option_view_time","note"
])
log_f.flush()

def log_event(phase, block_label, trial_idx, q_data, marker_name, code, t_phase_start,
              choice="", correct="", button_click_t="", opt_view_t="", note=""):
    t_abs = global_clock.getTime()
    rt = (t_abs - t_phase_start) if t_phase_start is not None else ""
    if isinstance(q_data, dict):
        q_num=q_data.get("question_number",""); q_year=q_data.get("year","")
        q_type=q_data.get("type",""); q_field=q_data.get("field","")
    else:
        q_num=q_year=q_type=q_field=""
    log_writer.writerow([
        f"{t_abs:.6f}", phase, block_label, trial_idx, q_num, q_year, q_type, q_field,
        marker_name, code, f"{rt}", choice, correct, button_click_t, opt_view_t, note
    ])
    log_f.flush()

# ===== helpers =====
def wait_secs_draw(secs, drawlist=None):
    if secs <= 0: return
    t0 = core.Clock()
    while t0.getTime() < secs:
        if drawlist:
            for stim in drawlist: stim.draw()
        win.flip(); core.wait(0.001)

def show_message(text, key_to_continue="space"):
    msg_text.text = text
    kb.clearEvents()
    while True:
        msg_text.draw(); win.flip(); core.wait(0.001)
        keys = kb.getKeys([key_to_continue,'escape'], waitRelease=False)
        if keys:
            if keys[0].name == 'escape': cleanup_and_quit()
            break

def wait_for_mouse_release():
    # Debounce: wait until all mouse buttons are released
    while any(mouse.getPressed()):
        win.flip(); core.wait(0.01)

def debounce_after_trigger():
    # Short refractory period after a reveal to avoid double-advance with held keys
    event.clearEvents(); kb.clearEvents(); mouse.clickReset()
    wait_for_mouse_release()
    core.wait(0.12)

def cleanup_and_quit():
    try:
        if not log_f.closed: log_f.flush(); log_f.close()
    except Exception: pass
    try: win.close()
    except Exception: pass
    core.quit()

# ===== data load =====
def load_questions():
    if not os.path.exists(QUESTIONS_JSON):
        print(f"ERROR: Questions file not found: {QUESTIONS_JSON}"); cleanup_and_quit()
    with open(QUESTIONS_JSON,'r',encoding='utf-8') as f:
        all_questions = json.load(f)
    concrete = [q for q in all_questions if q.get("type")=="concrete"]
    abstract = [q for q in all_questions if q.get("type")=="abstract"]
    random.shuffle(concrete); random.shuffle(abstract)
    return concrete, abstract

def build_block_list(concrete_questions, abstract_questions):
    need_per_type = BLOCKS_PER_TYPE * QUESTIONS_PER_BLOCK  # 15
    if len(concrete_questions) < need_per_type:
        print(f"[WARN] Not enough CONCRETE ({len(concrete_questions)}) for {need_per_type}. Truncating.")
    if len(abstract_questions) < need_per_type:
        print(f"[WARN] Not enough ABSTRACT ({len(abstract_questions)}) for {need_per_type}. Truncating.")
    conc_pool = concrete_questions[:need_per_type]
    abst_pool = abstract_questions[:need_per_type]
    concrete_blocks, abstract_blocks = [], []
    for i in range(BLOCKS_PER_TYPE):
        concrete_blocks.append(conc_pool[i*QUESTIONS_PER_BLOCK:(i+1)*QUESTIONS_PER_BLOCK])
        abstract_blocks.append(abst_pool[i*QUESTIONS_PER_BLOCK:(i+1)*QUESTIONS_PER_BLOCK])
    order = ['concrete','abstract']; random.shuffle(order)
    if order[0]=='concrete':
        blocks = [('C',i+1,blk) for i,blk in enumerate(concrete_blocks)] + \
                 [('A',i+1,blk) for i,blk in enumerate(abstract_blocks)]
        first_part = "concrete"
    else:
        blocks = [('A',i+1,blk) for i,blk in enumerate(abstract_blocks)] + \
                 [('C',i+1,blk) for i,blk in enumerate(concrete_blocks)]
        first_part = "abstract"
    print(f"[PLAN] Block order: first {first_part} (5 blocks), then the other type (5 blocks).")
    return blocks

# ===== questionnaire =====
SOCIO_INLINE = [
    {"qid":"age","text":"What is your age?","type":"text","required":"yes"},
    {"qid":"gender","text":"What is your gender?","type":"choice","options":"Woman,Man","required":"yes"},
    {"qid":"country_birth","text":"Country of birth:","type":"text","required":"no"},
    {"qid":"home_language","text":"Which language do you most often speak at home?","type":"text","required":"yes"},
]

def run_questionnaire(block_label="QNR"):
    socio_questions = SOCIO_INLINE
    if not socio_questions: return
    mname, mcode, _ = send_marker("QUESTIONNAIRE_ON")
    log_event("questionnaire", block_label, -1, {}, mname, mcode, None, note="Questionnaire start")
    show_message("QUESTIONNAIRE\n\nAnswer the following questions.\nPress SPACE to continue.")
    input_box = visual.Rect(win, width=WRAP_PIX, height=60, fillColor=[-0.2,-0.2,-0.2],
                            lineColor="black", pos=(0,-150))
    input_text = visual.TextStim(win, text="", color="black", height=GEN_TEXT_HEIGHT,
                                 pos=(0,-150), wrapWidth=WRAP_PIX*0.95)
    for q in socio_questions:
        qid=q.get("qid","").strip(); text=q.get("text","").strip()
        qtype=q.get("type","text").strip().lower()
        opts=[o.strip() for o in q.get("options","").split(",") if o.strip()]
        req=(q.get("required","no").strip().lower()=="yes")
        answer=None; t_start=global_clock.getTime()
        if qtype=="choice" and opts:
            choice_boxes, choice_labels = [], []
            for i,opt in enumerate(opts):
                y = 100 - i*80
                b = visual.Rect(win, width=400, height=60, fillColor=[-0.2,-0.2,-0.2],
                                lineColor="black", pos=(0,y))
                t = visual.TextStim(win, text=f"{i+1}) {opt}", color="black",
                                    height=OPTION_TEXT_HEIGHT, pos=(0,y))
                choice_boxes.append(b); choice_labels.append(t)
            prompt = visual.TextStim(win, text=text, color="black", height=GEN_TEXT_HEIGHT,
                                     wrapWidth=WRAP_PIX, pos=(0,200))
            while answer is None:
                prompt.draw()
                for b,t in zip(choice_boxes, choice_labels): b.draw(); t.draw()
                win.flip()
                if mouse.getPressed()[0]:
                    for i,b in enumerate(choice_boxes):
                        if b.contains(mouse): answer=opts[i]; break
                keys = kb.getKeys([str(i+1) for i in range(len(opts))]+['escape','space'], waitRelease=False)
                if keys:
                    if keys[0].name=='escape': cleanup_and_quit()
                    if keys[0].name.isdigit():
                        idx=int(keys[0].name)-1
                        if 0<=idx<len(opts): answer=opts[idx]
        else:
            prompt = visual.TextStim(win, text=f"{text}\n(Type your answer. ENTER to confirm.)",
                                     color="black", height=GEN_TEXT_HEIGHT, wrapWidth=WRAP_PIX, pos=(0,60))
            typed=""
            while True:
                prompt.draw(); input_box.draw(); input_text.text=typed; input_text.draw()
                win.flip()
                keys=kb.getKeys(waitRelease=False)
                for k in keys:
                    if k.name=='escape': cleanup_and_quit()
                    elif k.name=='backspace': typed=typed[:-1]
                    elif k.name in ('return','num_enter'):
                        if not(req and len(typed.strip())==0): answer=typed; break
                    elif len(k.name)==1: typed+=k.name
                if answer is not None: break
        log_event("questionnaire_item", block_label,-1, {"qid":qid}, "QNR_ITEM",0,t_start,
                  choice=answer if answer is not None else "", note=f"type={qtype}")
    mname, mcode, _ = send_marker("QUESTIONNAIRE_OFF")
    log_event("questionnaire", block_label, -1, {}, mname, mcode, None, note="Questionnaire end")

# ===== trial =====
def run_trial(block_label, idx_in_block, question_data):
    """
    Three-phase cumulative presentation with debounce:
      1) Show TEXT only.
      2) On click/space (released), add QUESTION (stem).
      3) On next click/space (released), add OPTIONS.
      Then wait for answer.
    """
    # ITI
    iti_duration = random.uniform(MIN_ITI_SECS, MAX_ITI_SECS)
    iti_start = global_clock.getTime()
    msg_text.text = "+"
    wait_secs_draw(iti_duration, [msg_text])
    send_marker("ITI")
    log_event("iti", block_label, idx_in_block, question_data, "ITI", 99, iti_start,
              note=f"ITI duration: {iti_duration:.2f}s")

    # Content
    stem_text  = question_data["question_text_translated"]
    question_t = question_data["question_itself_translated"]
    option_keys = [
        "question_option_A_translated","question_option_B_translated",
        "question_option_C_translated","question_option_D_translated",
        "question_option_E_translated"
    ]

    # reset states
    event.clearEvents(); kb.clearEvents(); mouse.clickReset(); wait_for_mouse_release()

    # PHASE 1: TEXT only
    question_text.text = stem_text
    question_itself.text = ""
    for i in range(5): opt_texts[i].text = ""

    t_on = global_clock.getTime()
    send_marker("Q_TEXT_ON")
    log_event("q_text_on", block_label, idx_in_block, question_data, "Q_TEXT_ON", 11, t_on)

    button_show_lbl.text = "Show question"

    # --- wait for first (debounced) reveal ---
    while True:
        question_text.draw()
        button_show.draw(); button_show_lbl.draw()
        win.flip(); core.wait(0.001)

        # mouse (press-and-release)
        if mouse.isPressedIn(button_show, buttons=[0]):
            wait_for_mouse_release()
            send_marker("BUTTON_CLICK")
            debounce_after_trigger()
            break

        # keyboard (space released)
        keys = kb.getKeys(['space','escape'], waitRelease=True)
        if keys:
            if keys[0].name=='escape': cleanup_and_quit()
            send_marker("BUTTON_CLICK")
            debounce_after_trigger()
            break

    # PHASE 2: add QUESTION
    question_itself.text = question_t
    stem_on = global_clock.getTime()
    send_marker("Q_STEM_ON")
    log_event("q_stem_on", block_label, idx_in_block, question_data, "Q_STEM_ON", 14, stem_on)

    button_show_lbl.text = "Show options"

    # --- wait for second (debounced) reveal ---
    while True:
        question_text.draw()
        question_itself.draw()
        button_show.draw(); button_show_lbl.draw()
        win.flip(); core.wait(0.001)

        if mouse.isPressedIn(button_show, buttons=[0]):
            wait_for_mouse_release()
            send_marker("BUTTON_CLICK")
            debounce_after_trigger()
            break

        keys = kb.getKeys(['space','escape'], waitRelease=True)
        if keys:
            if keys[0].name=='escape': cleanup_and_quit()
            send_marker("BUTTON_CLICK")
            debounce_after_trigger()
            break

    # PHASE 3: add OPTIONS
    for i,k in enumerate(option_keys):
        letter = chr(65+i)
        opt_texts[i].text = f"{letter}) {question_data[k]}"

    options_on = global_clock.getTime()
    send_marker("Q_OPTIONS_ON")
    log_event("q_options_on", block_label, idx_in_block, question_data, "Q_OPTIONS_ON", 15, options_on)

    # Wait for answer
    chosen = None
    event.clearEvents(); kb.clearEvents(); mouse.clickReset(); wait_for_mouse_release()

    while chosen is None:
        question_text.draw(); question_itself.draw()
        for i in range(5):
            opt_boxes[i].draw(); opt_texts[i].draw()
        win.flip(); core.wait(0.001)

        if any(mouse.getPressed()):
            for i,box in enumerate(opt_boxes):
                if box.contains(mouse):
                    wait_for_mouse_release()
                    chosen = chr(65+i); break

        keys = kb.getKeys(['a','b','c','d','e','1','2','3','4','5','escape'], waitRelease=True)
        if keys:
            name = keys[0].name
            if name=='escape': cleanup_and_quit()
            elif name in list('abcde'): chosen = name.upper()
            elif name in ['1','2','3','4','5']: chosen = chr(64+int(name))

    # Log answer
    ans_marker = f"ANS_{chosen}"
    send_marker(ans_marker)
    answer_time = global_clock.getTime()
    log_event("answer", block_label, idx_in_block, question_data, ans_marker, TRIGGER_MAP.get(ans_marker,0),
              options_on, choice=chosen, opt_view_t=f"{answer_time - options_on:.6f}")
    msg_text.text = "Response recorded"
    wait_secs_draw(0.5, [msg_text])

# ===== block runner =====
def run_block(block_label, questions_in_block):
    send_marker("BLK_ON")
    log_event("block_start", block_label, -1, {}, "BLK_ON", 91, None,
              note=f"{block_label} start (target {BLOCK_DURATION_SECS}s)")
    block_clock = core.Clock(); block_clock.reset()
    trial_idx = 0

    for q in questions_in_block:
        trial_idx += 1
        run_trial(block_label, trial_idx, q)
        if block_clock.getTime() >= BLOCK_DURATION_SECS:
            break

    remaining = BLOCK_DURATION_SECS - block_clock.getTime()
    if remaining > 0:
        send_marker("BLOCK_REST")
        log_event("block_rest_wait", block_label, -1, {}, "BLOCK_REST", 93, None,
                  note=f"Waiting {remaining:.1f}s to complete 7-min block")
        rest_clock = core.Clock()
        while rest_clock.getTime() < remaining:
            left = remaining - rest_clock.getTime()
            msg_text.text = f"Rest\n\nNext block in {int(left)} seconds..."
            msg_text.draw(); win.flip()
            keys = kb.getKeys(['escape'], waitRelease=False)
            if keys: cleanup_and_quit()

    send_marker("BLK_OFF")
    log_event("block_end", block_label, -1, {}, "BLK_OFF", 92, None,
              note=f"{block_label} end (actual {block_clock.getTime():.1f}s)")

# ===== main =====
log_event("experiment", "START", -1, {}, "EXP_START", 0, None,
          note=f"Experiment started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
show_message("Welcome!\n\nPress SPACE to begin.")

if RUN_QUESTIONNAIRE_BEFORE:
    run_questionnaire(block_label="PRE")

concrete_q, abstract_q = load_questions()
plan = build_block_list(concrete_q, abstract_q)  # list of (type_tag, within_idx, [questions])

for type_tag, within_idx, questions in plan:
    label_prefix = "C" if type_tag == "C" else "A"
    block_label = f"{label_prefix}{within_idx}"
    show_message(f"BLOCK {block_label}\n\nPress SPACE to continue.")
    run_block(block_label, questions)

log_event("experiment", "END", -1, {}, "EXP_END", 0, None,
          note=f"Experiment ended at {time.strftime('%Y-%m-%d %H:%M:%S')}")
show_message("Thank you for participating!\n\nPress SPACE to finish.")
cleanup_and_quit()
