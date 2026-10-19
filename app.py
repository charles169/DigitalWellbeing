"""
Digital Wellbeing Analytics
Professional desktop application for individual user tracking and insights.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
import os, time, random as _rnd
from datetime import datetime

try:
    import pymysql
    HAS_DB = True
except ImportError:
    HAS_DB = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ── Database ──────────────────────────────────────────────────
DB  = dict(host=os.environ.get("DB_HOST","localhost"),
           port=int(os.environ.get("DB_PORT",3306)),
           user=os.environ.get("DB_USER","root"),
           password=os.environ.get("DB_PASSWORD",""),
           database=os.environ.get("DB_NAME","digital_wellbeing"),
           connect_timeout=3, read_timeout=3, write_timeout=3)
CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wellbeing_data.csv")

# ── ONE Consistent Dark Theme ─────────────────────────────────
BG      = "#0e1117"   # darkest — page bg
CARD    = "#1a1d2e"   # card bg
CARD2   = "#1e2235"   # slightly lighter card
BORDER  = "#2a2d42"   # card borders
ACCENT  = "#4361ee"   # primary blue — buttons, active states
ACCENT2 = "#3a54d4"   # darker blue on hover
ACCENT3 = "#5a7af5"   # lighter blue — highlights
TXT     = "#e8eaf6"   # primary text — near white
TXT2    = "#8892b0"   # secondary text — muted
TXT3    = "#4a5280"   # very muted
SEP     = "#252841"   # separator lines

# Status colors — used only for data meaning, not backgrounds
OK      = "#43d9ad"   # good/healthy indicator
WARN    = "#ffc800"   # warning indicator
CRIT    = "#ff6b6b"   # critical indicator
INFO    = "#74b9ff"   # info indicator

matplotlib.rcParams.update({
    "axes.facecolor":    CARD,
    "figure.facecolor":  CARD,
    "axes.edgecolor":    BORDER,
    "axes.labelcolor":   TXT2,
    "xtick.color":       TXT2,
    "ytick.color":       TXT2,
    "text.color":        TXT,
    "grid.color":        BORDER,
    "axes.grid":         True,
    "grid.linewidth":    0.4,
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "font.family":       "sans-serif",
    "font.size":         9,
})

# ── Healthy limits (WHO / research-based) ─────────────────────
LIMITS = {
    "daily_screen_time_hours": 6.0,
    "social_media_hours":      2.0,
    "gaming_hours":            1.5,
    "sleep_hours":             7.0,
    "notifications_per_day":   50,
    "work_study_hours":        4.0,
}

MALE_NAMES   = ["Aarav","Rahul","Vikram","Arjun","Karan","Dev","Amit","Rohan","Nikhil","Aditya"]
FEMALE_NAMES = ["Priya","Sneha","Ananya","Kavya","Pooja","Riya","Meera","Divya","Nisha","Tara"]
OTHER_NAMES  = ["Alex","Sam","Jordan","Taylor","Morgan"]
_rnd.seed(42)

# ── Database helpers ──────────────────────────────────────────
def db_conn():
    if not HAS_DB: return None
    import threading
    result = [None]
    def _connect():
        try: result[0] = pymysql.connect(**DB)
        except: result[0] = None
    t = threading.Thread(target=_connect, daemon=True)
    t.start(); t.join(timeout=4)
    return result[0]

def db_query(sql, cols):
    c = db_conn()
    if not c: return pd.DataFrame(columns=cols)
    try:
        with c.cursor() as cur:
            cur.execute(sql); rows = cur.fetchall()
        c.close()
        return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
    except:
        try: c.close()
        except: pass
        return pd.DataFrame(columns=cols)

def db_exec(sql, params=()):
    c = db_conn()
    if not c: return False
    try:
        with c.cursor() as cur: cur.execute(sql, params)
        c.commit(); c.close(); return True
    except: c.close(); return False

def load_data():
    df = db_query("""
        SELECT w.user_id,
               COALESCE(u.name, CONCAT('User_',RIGHT(w.user_id,4))) AS name,
               w.age, w.gender,
               COALESCE(u.city,'Unknown') AS city,
               COALESCE(u.occupation,'Unknown') AS occupation,
               w.daily_screen_time_hours, w.social_media_hours,
               w.gaming_hours, w.work_study_hours,
               w.sleep_hours, w.notifications_per_day
        FROM wellbeing_data w
        LEFT JOIN users u ON w.user_id = u.user_id
        WHERE w.user_id LIKE 'U0%'
        ORDER BY w.user_id
    """, ["user_id","name","age","gender","city","occupation",
          "daily_screen_time_hours","social_media_hours","gaming_hours",
          "work_study_hours","sleep_hours","notifications_per_day"])

    if df.empty:
        try:
            df = pd.read_csv(CSV); df.columns = [c.strip() for c in df.columns]
            for col in ["name","city","occupation"]:
                if col not in df.columns: df[col] = "Unknown"
        except Exception as e:
            messagebox.showerror("Error", f"Cannot load data:\n{e}")
            return pd.DataFrame()

    for col in ["daily_screen_time_hours","social_media_hours","gaming_hours",
                "work_study_hours","sleep_hours","notifications_per_day","age"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["age","notifications_per_day"]:
        if col in df.columns: df[col] = df[col].astype(int)

    def fix_name(row):
        n = str(row["name"]).strip()
        if n and n not in ("Unknown","") and not n.startswith("User_"): return n
        g = row["gender"]
        if g == "Male":   return _rnd.choice(MALE_NAMES)
        if g == "Female": return _rnd.choice(FEMALE_NAMES)
        return _rnd.choice(OTHER_NAMES)
    df["name"] = df.apply(fix_name, axis=1)

    df["age_group"] = pd.cut(df["age"], bins=[17,24,34,44,200],
        labels=["18-24","25-34","35-44","45+"]).astype(str)
    df["entertainment_hours"] = df["social_media_hours"] + df["gaming_hours"]

    def calc_score(row):
        s = 100
        sc = float(row["daily_screen_time_hours"])
        sl = float(row["sleep_hours"])
        so = float(row["social_media_hours"])
        no = float(row["notifications_per_day"])
        ga = float(row["gaming_hours"])
        wo = float(row["work_study_hours"])

        # Screen time — biggest factor
        if sc > 8:   s -= 30
        elif sc > 6: s -= int((sc-6) * 10)

        # Sleep — second biggest
        if sl < 5:   s -= 25
        elif sl < 6: s -= 18
        elif sl < 7: s -= int((7-sl) * 10)

        # Social media
        if so > 4:   s -= 20
        elif so > 2: s -= int((so-2) * 7)

        # Notifications
        if no > 150: s -= 15
        elif no > 100: s -= 10
        elif no > 50:  s -= int((no-50) * 0.08)

        # Gaming
        if ga > 3:   s -= 10
        elif ga > 1.5: s -= int((ga-1.5) * 4)

        # Low productivity bonus/penalty
        if wo < 1:   s -= 5

        return max(0, min(100, round(s)))

    df["score"] = df.apply(calc_score, axis=1)
    df["risk"]  = df["score"].apply(
        lambda s: "Healthy" if s>=70 else ("Moderate" if s>=40 else "High Risk"))
    return df


def load_user_trend(uid):
    """Load 30-day daily log for a specific user."""
    return db_query("""
        SELECT log_date, screen_time_hours, social_media_hours,
               gaming_hours, work_study_hours, sleep_hours,
               notifications_per_day, mood
        FROM daily_log
        WHERE user_id = %s
        ORDER BY log_date ASC
        LIMIT 30
    """.replace("%s", f"'{uid}'"),
    ["date","screen","social","gaming","work","sleep","notifs","mood"])

# ── Individual analysis functions ─────────────────────────────
def get_score_label(score):
    if score >= 90: return "A+", "Excellent"
    if score >= 80: return "A",  "Very Good"
    if score >= 70: return "B+", "Good"
    if score >= 60: return "B",  "Fair"
    if score >= 50: return "C",  "Average"
    if score >= 40: return "D",  "Poor"
    return "F", "Critical"

def get_status_color(score):
    if score >= 70: return OK
    if score >= 40: return WARN
    return CRIT

def analyze_user(row):
    """
    Returns list of (metric, value, limit, status, severity, message, action)
    for each tracked metric.
    """
    sc = float(row["daily_screen_time_hours"])
    so = float(row["social_media_hours"])
    ga = float(row["gaming_hours"])
    sl = float(row["sleep_hours"])
    no = float(row["notifications_per_day"])
    wo = float(row["work_study_hours"])

    results = []

    # Screen Time
    if sc > 10:
        results.append(("📱 Screen Time", f"{sc:.1f}h/day", "6h limit", CRIT, "CRITICAL",
            f"Your screen time of {sc:.1f}h is {sc-6:.1f}h above the healthy limit.",
            "Enable screen time limits on your phone. Set app timers. Put phone in another room after 9pm."))
    elif sc > 6:
        results.append(("📱 Screen Time", f"{sc:.1f}h/day", "6h limit", WARN, "WARNING",
            f"Your screen time of {sc:.1f}h exceeds the recommended 6h daily limit.",
            "Set a daily 6h screen time goal. Use grayscale mode. Keep phone away during meals."))
    else:
        results.append(("📱 Screen Time", f"{sc:.1f}h/day", "6h limit", OK, "HEALTHY",
            f"Your screen time of {sc:.1f}h is within the healthy range. Well done!",
            "Keep monitoring weekly to maintain this healthy habit."))

    # Sleep
    if sl < 5:
        results.append(("😴 Sleep", f"{sl:.1f}h/night", "7h minimum", CRIT, "CRITICAL",
            f"Only {sl:.1f}h sleep is dangerously low. This seriously impacts health.",
            "Set a strict 10:30pm bedtime. Stop all screens 1 hour before bed. Prioritise sleep."))
    elif sl < 7:
        results.append(("😴 Sleep", f"{sl:.1f}h/night", "7h minimum", WARN, "WARNING",
            f"{sl:.1f}h sleep is below the recommended 7h. You're accumulating sleep debt.",
            "Go to bed 30 minutes earlier tonight. Avoid gaming or social media after 10pm."))
    else:
        results.append(("😴 Sleep", f"{sl:.1f}h/night", "7h minimum", OK, "HEALTHY",
            f"Excellent! {sl:.1f}h of sleep is within the healthy range.",
            "Keep your bedtime consistent every night including weekends."))

    # Social Media
    if so > 4:
        results.append(("📲 Social Media", f"{so:.1f}h/day", "2h limit", CRIT, "CRITICAL",
            f"{so:.1f}h of social media is excessive and linked to anxiety and poor sleep.",
            "Delete social media apps from your home screen. Set strict 45-min daily timer."))
    elif so > 2:
        results.append(("📲 Social Media", f"{so:.1f}h/day", "2h limit", WARN, "WARNING",
            f"{so:.1f}h of social media exceeds the 2h healthy limit.",
            "Replace one social session with a 30-min walk. Turn off push notifications."))
    else:
        results.append(("📲 Social Media", f"{so:.1f}h/day", "2h limit", OK, "HEALTHY",
            f"Good discipline! Only {so:.1f}h of social media use.",
            "Check weekly to ensure it does not gradually increase."))

    # Notifications
    if no > 150:
        results.append(("🔔 Notifications", f"{int(no)}/day", "50 limit", CRIT, "CRITICAL",
            f"{int(no)} notifications/day is severely disruptive. Each one costs ~23 min of focus.",
            "Disable ALL non-essential notifications now. Keep only calls and urgent messages."))
    elif no > 50:
        results.append(("🔔 Notifications", f"{int(no)}/day", "50 limit", WARN, "WARNING",
            f"{int(no)} notifications/day is high. This significantly reduces focus and productivity.",
            "Audit all apps. Disable social, shopping and news notifications. Use Do Not Disturb."))
    else:
        results.append(("🔔 Notifications", f"{int(no)}/day", "50 limit", OK, "HEALTHY",
            f"Only {int(no)} notifications/day — well managed!",
            "Keep checking notification settings monthly as apps tend to re-enable them."))

    # Gaming
    if ga > 3:
        results.append(("🎮 Gaming", f"{ga:.1f}h/day", "1.5h limit", WARN, "WARNING",
            f"{ga:.1f}h of gaming per day exceeds healthy limits.",
            "Set max 1.5h per session. Avoid gaming after 9pm to protect sleep quality."))
    elif ga > 1.5:
        results.append(("🎮 Gaming", f"{ga:.1f}h/day", "1.5h limit", WARN, "WARNING",
            f"{ga:.1f}h of gaming is slightly above recommended.",
            "Take 10-min breaks every hour. Set a session end alarm."))

    # Work/Study
    if wo >= 4:
        results.append(("💼 Work/Study", f"{wo:.1f}h/day", "productive", OK, "HEALTHY",
            f"Good productivity — {wo:.1f}h of work/study per day.",
            "Balance productivity with proper breaks. Try the Pomodoro technique."))
    elif wo < 1:
        results.append(("💼 Work/Study", f"{wo:.1f}h/day", "aim 4h", WARN, "LOW",
            f"Only {wo:.1f}h of work/study — consider increasing productive screen time.",
            "Dedicate 4h daily to productive activities. Replace entertainment time with study."))

    return results

def get_daily_goals(row):
    sc = float(row["daily_screen_time_hours"])
    sl = float(row["sleep_hours"])
    so = float(row["social_media_hours"])
    no = float(row["notifications_per_day"])
    goals = []
    goals.append(("📱", f"Screen time goal: {min(sc, max(5.0, sc-1)):.0f}h today",
                  f"Currently {sc:.1f}h — {'reduce by 1h' if sc > 6 else 'maintain this level'}"))
    goals.append(("😴", "Sleep by 10:30pm tonight",
                  f"Need {max(0, 7-sl):.1f}h more — set a bedtime alarm now"))
    goals.append(("📲", f"Social media: {'keep under 2h' if so <= 2 else 'reduce to 2h today'}",
                  f"Currently {so:.1f}h — {'great discipline' if so <= 2 else 'remove from home screen'}"))
    goals.append(("🔔", f"{'Reduce' if no > 50 else 'Maintain'} notifications",
                  f"{int(no)}/day — {'disable non-essential apps' if no > 50 else 'well managed'}"))
    goals.append(("🏃", "30-minute physical activity",
                  "Walk, exercise or sport — reduces screen urge significantly"))
    goals.append(("📖", "Read for 20 minutes",
                  "Replace one scroll session with reading — improves focus"))
    return goals

# ── ScrollFrame ───────────────────────────────────────────────
class SF(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.cv = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.cv.yview)
        self.cv.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.cv.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.cv, bg=BG)
        wid = self.cv.create_window((0,0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.cv.configure(scrollregion=self.cv.bbox("all")))
        self.cv.bind("<Configure>", lambda e: self.cv.itemconfig(wid, width=e.width))
        self.cv.bind("<Enter>", lambda e: self.cv.bind_all("<MouseWheel>", self._scroll))
        self.cv.bind("<Leave>", lambda e: self.cv.unbind_all("<MouseWheel>"))

    def _scroll(self, e):
        try: self.cv.yview_scroll(int(-1*(e.delta/120)), "units")
        except: pass

# ── UI Components ─────────────────────────────────────────────
def page_title(parent, title, sub=""):
    f = tk.Frame(parent, bg=BG); f.pack(fill="x", padx=24, pady=(20,6))
    tk.Label(f, text=title, bg=BG, fg=TXT,
             font=("Segoe UI",18,"bold")).pack(anchor="w")
    if sub:
        tk.Label(f, text=sub, bg=BG, fg=TXT2,
                 font=("Segoe UI",9)).pack(anchor="w", pady=(3,0))

def section_hdr(parent, title, color=ACCENT3):
    f = tk.Frame(parent, bg=BG); f.pack(fill="x", padx=24, pady=(16,6))
    tk.Frame(f, bg=color, width=3, height=16).pack(side="left", padx=(0,10))
    tk.Label(f, text=title, bg=BG, fg=TXT,
             font=("Segoe UI",11,"bold")).pack(side="left")

def sep(parent):
    tk.Frame(parent, bg=SEP, height=1).pack(fill="x", padx=24, pady=8)

def kpi_row(parent, items):
    """items = list of (icon, label, value, sub, dot_color)"""
    f = tk.Frame(parent, bg=BG); f.pack(fill="x", padx=16, pady=4)
    for i, (icon, label, value, sub, dot) in enumerate(items):
        f.grid_columnconfigure(i, weight=1)
        outer = tk.Frame(f, bg=BG)
        outer.grid(row=0, column=i, padx=5, pady=5, sticky="nsew")
        card = tk.Frame(outer, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="both", expand=True)
        inn = tk.Frame(card, bg=CARD); inn.pack(padx=16, pady=14, fill="both", expand=True)
        # Top: icon + dot color indicator
        top = tk.Frame(inn, bg=CARD); top.pack(fill="x", pady=(0,8))
        tk.Label(top, text=icon, bg=CARD, fg=TXT2,
                 font=("Segoe UI Emoji",16)).pack(side="left")
        # Small colored dot
        tk.Frame(top, bg=dot, width=8, height=8).pack(side="right", pady=4)
        # Value
        tk.Label(inn, text=str(value), bg=CARD, fg=TXT,
                 font=("Segoe UI",20,"bold"), anchor="w").pack(anchor="w")
        tk.Label(inn, text=label, bg=CARD, fg=TXT2,
                 font=("Segoe UI",9,"bold"), anchor="w").pack(anchor="w")
        tk.Label(inn, text=sub, bg=CARD, fg=TXT3,
                 font=("Segoe UI",8), anchor="w").pack(anchor="w", pady=(2,0))
        card.bind("<Enter>", lambda e, c=card: c.config(highlightbackground=ACCENT))
        card.bind("<Leave>", lambda e, c=card: c.config(highlightbackground=BORDER))

def analysis_card(parent, metric, value, limit, color, severity, message, action):
    """Professional analysis card for each tracked metric."""
    card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    card.pack(fill="x", padx=24, pady=5)

    # Left stripe — severity color
    tk.Frame(card, bg=color, width=4).pack(side="left", fill="y")

    body = tk.Frame(card, bg=CARD); body.pack(fill="x", padx=16, pady=14, side="left", expand=True)

    # Header row
    hdr = tk.Frame(body, bg=CARD); hdr.pack(fill="x", pady=(0,6))

    # Metric name
    tk.Label(hdr, text=metric, bg=CARD, fg=TXT,
             font=("Segoe UI",10,"bold")).pack(side="left")

    # Value chip
    chip = tk.Frame(hdr, bg=CARD2); chip.pack(side="left", padx=12)
    tk.Label(chip, text=f"  {value}  ", bg=CARD2, fg=TXT,
             font=("Segoe UI",9,"bold")).pack(pady=2)

    # Limit reference
    tk.Label(hdr, text=f"Limit: {limit}", bg=CARD, fg=TXT3,
             font=("Segoe UI",8)).pack(side="left")

    # Severity badge — right aligned
    badge_bg = CARD2
    tk.Label(hdr, text=f"  {severity}  ", bg=badge_bg, fg=color,
             font=("Segoe UI",8,"bold")).pack(side="right")

    # Message
    tk.Label(body, text=message, bg=CARD, fg=TXT2,
             font=("Segoe UI",9), anchor="w",
             wraplength=820, justify="left").pack(anchor="w", pady=(0,6))

    # Separator
    tk.Frame(body, bg=SEP, height=1).pack(fill="x", pady=(0,6))

    # Action
    af = tk.Frame(body, bg=CARD); af.pack(fill="x")
    tk.Label(af, text="→", bg=CARD, fg=ACCENT3,
             font=("Segoe UI",10,"bold")).pack(side="left", padx=(0,8))
    tk.Label(af, text=action, bg=CARD, fg=TXT2,
             font=("Segoe UI",9), anchor="w",
             wraplength=800, justify="left").pack(side="left", fill="x")

def chart_card(parent, fig_obj, title, full=False, r=0, c=0):
    if full:
        wrap = tk.Frame(parent, bg=BG); wrap.pack(fill="x", padx=20, pady=5)
    else:
        wrap = tk.Frame(parent, bg=BG)
        wrap.grid(row=r, column=c, padx=5, pady=5, sticky="nsew")
    card = tk.Frame(wrap, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    card.pack(fill="both", expand=True)
    tk.Frame(card, bg=ACCENT, height=2).pack(fill="x")
    hdr = tk.Frame(card, bg=CARD); hdr.pack(fill="x", padx=12, pady=(8,0))
    tk.Label(hdr, text=title, bg=CARD, fg=TXT,
             font=("Segoe UI",10,"bold"), anchor="w").pack(side="left")
    sv = tk.Label(hdr, text="↓ Save", bg=CARD, fg=TXT3,
                   font=("Segoe UI",8), cursor="hand2")
    sv.pack(side="right")
    ch = FigureCanvasTkAgg(fig_obj, card)
    ch.get_tk_widget().pack(fill="both", padx=8, pady=(4,10))
    ch.draw()
    sv.bind("<Button-1>", lambda e, fig=ch.figure, t=title: _save_chart(fig, t))
    plt.close(fig_obj)
    return wrap

def _save_chart(fig, title):
    p = filedialog.asksaveasfilename(defaultextension=".png",
        filetypes=[("PNG","*.png"),("PDF","*.pdf")],
        initialfile=title.replace(" ","_")+".png")
    if p: fig.savefig(p, dpi=150, bbox_inches="tight")

def make_tree(parent, df, height=8):
    s = ttk.Style(); s.theme_use("clam")
    s.configure("D.Treeview", background=CARD, foreground=TXT,
                 rowheight=28, fieldbackground=CARD,
                 borderwidth=0, font=("Segoe UI",9))
    s.configure("D.Treeview.Heading", background=CARD2, foreground=TXT2,
                 font=("Segoe UI",9,"bold"), borderwidth=0, relief="flat")
    s.map("D.Treeview", background=[("selected",ACCENT)],
          foreground=[("selected",TXT)])
    wrap = tk.Frame(parent, bg=BG); wrap.pack(fill="x", padx=24, pady=(0,10))
    cols = list(df.columns)
    tv = ttk.Treeview(wrap, columns=cols, show="headings",
                       height=min(len(df),height), style="D.Treeview")
    vs = ttk.Scrollbar(wrap, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=vs.set)
    vs.pack(side="right", fill="y"); tv.pack(fill="x")
    for col in cols:
        tv.heading(col, text=col.replace("_"," ").title())
        tv.column(col, width=110, anchor="center")
    for i, row in enumerate(df.itertuples(index=False)):
        tv.insert("","end",values=list(row),tags=("odd" if i%2==0 else "even",))
    tv.tag_configure("odd",  background=CARD)
    tv.tag_configure("even", background=CARD2)
    tv.bind("<MouseWheel>", lambda e: tv.yview_scroll(int(-1*(e.delta/120)),"units"))

def grid_row(parent, cols=2):
    f = tk.Frame(parent, bg=BG); f.pack(fill="x", padx=16)
    for i in range(cols): f.grid_columnconfigure(i, weight=1)
    return f

def toast(root, msg, color=OK):
    t = tk.Toplevel(root); t.overrideredirect(True)
    t.attributes("-topmost", True, "-alpha", 0.0)
    tk.Label(t, text=f"  {msg}  ", bg=CARD, fg=color,
             font=("Segoe UI",10,"bold"), padx=10, pady=8,
             highlightthickness=1, highlightbackground=color).pack()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    t.update_idletasks()
    t.geometry(f"+{sw-t.winfo_width()-20}+{sh-t.winfo_height()-60}")
    def fi(a=0.0):
        if a<1: t.attributes("-alpha",a); t.after(20,fi,a+0.1)
    def fo(a=1.0):
        if a>0: t.attributes("-alpha",a); t.after(20,fo,a-0.1)
        else:
            try: t.destroy()
            except: pass
    fi(); t.after(2500, fo)

# ═══════════════════════════════════════════════════════
# LOGIN
# ═══════════════════════════════════════════════════════
class Login(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Digital Wellbeing Analytics")
        self.configure(bg=BG)
        self.resizable(False, False)
        W, H = 880, 520
        self.geometry(f"{W}x{H}+{(self.winfo_screenwidth()-W)//2}+{(self.winfo_screenheight()-H)//2}")
        self.attributes("-alpha", 0.0)
        self._run = True
        self._pts = []
        self._build()
        self._fade()

    def _fade(self, a=0.0):
        if not self._run or not self.winfo_exists(): return
        if a < 1.0: self.attributes("-alpha", a); self.after(16, self._fade, a+0.08)

    def _build(self):
        # Left panel
        lp = tk.Frame(self, bg=CARD, width=400, height=520)
        lp.place(x=0, y=0); lp.pack_propagate(False)

        # Animated dots canvas
        self.lc = tk.Canvas(lp, width=400, height=520, bg=CARD, highlightthickness=0)
        self.lc.place(x=0, y=0)
        for _ in range(14):
            px, py = np.random.randint(20,380), np.random.randint(20,500)
            r2 = np.random.randint(2, 5)
            pid = self.lc.create_oval(px-r2,py-r2,px+r2,py+r2, fill=ACCENT3, outline="")
            self.lc.create_line(px-r2-4,py,px+r2+4,py, fill=SEP, width=1)
            self._pts.append([pid, np.random.uniform(-0.4,0.4), np.random.uniform(-0.4,0.4)])
        self._anim()

        # Content
        cf = tk.Frame(lp, bg=CARD); cf.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(cf, text="📱", bg=CARD, fg=ACCENT3,
                 font=("Segoe UI Emoji",44)).pack(pady=(0,16))
        tk.Label(cf, text="Digital Wellbeing", bg=CARD, fg=TXT,
                 font=("Segoe UI",22,"bold")).pack()
        tk.Label(cf, text="Analytics", bg=CARD, fg=TXT2,
                 font=("Segoe UI",14)).pack(pady=(0,28))

        # Stats chips
        sf = tk.Frame(cf, bg=CARD); sf.pack()
        for v, l in [("7,505","Users"),("6","Tables"),("WHO","Standards")]:
            chip = tk.Frame(sf, bg=CARD2, padx=12, pady=6)
            chip.pack(side="left", padx=4)
            tk.Label(chip, text=v, bg=CARD2, fg=TXT,
                     font=("Segoe UI",13,"bold")).pack()
            tk.Label(chip, text=l, bg=CARD2, fg=TXT2,
                     font=("Segoe UI",8)).pack()

        tk.Label(lp, text="Individual Tracking & Personalized Insights  ·  v3.0",
                 bg=CARD, fg=TXT3, font=("Segoe UI",8)).place(relx=0.5, rely=0.96, anchor="center")

        # Divider
        tk.Frame(self, bg=ACCENT, width=1, height=520).place(x=400, y=0)

        # Right panel — form
        rp = tk.Frame(self, bg=BG, width=480, height=520)
        rp.place(x=401, y=0); rp.pack_propagate(False)
        form = tk.Frame(rp, bg=BG)
        form.place(relx=0.5, rely=0.5, anchor="center", width=320)

        tk.Label(form, text="Sign In", bg=BG, fg=TXT,
                 font=("Segoe UI",26,"bold")).pack(anchor="w", pady=(0,4))
        tk.Label(form, text="Enter your credentials to continue",
                 bg=BG, fg=TXT2, font=("Segoe UI",10)).pack(anchor="w", pady=(0,24))

        # User ID field
        tk.Label(form, text="USER ID OR ADMIN", bg=BG, fg=TXT3,
                 font=("Segoe UI",8,"bold"), anchor="w").pack(fill="x", pady=(0,4))
        uw = tk.Frame(form, bg=BORDER, pady=1, padx=1)
        uw.pack(fill="x", pady=(0,14))
        self.ue = tk.Entry(uw, bg=CARD, fg=TXT, insertbackground=TXT,
                           font=("Segoe UI",11), bd=0, relief="flat")
        self.ue.pack(fill="x", ipady=10, padx=1, pady=1)
        self.ue.bind("<FocusIn>",  lambda e: uw.config(bg=ACCENT))
        self.ue.bind("<FocusOut>", lambda e: uw.config(bg=BORDER))

        # Password field
        tk.Label(form, text="PASSWORD", bg=BG, fg=TXT3,
                 font=("Segoe UI",8,"bold"), anchor="w").pack(fill="x", pady=(0,4))
        pw = tk.Frame(form, bg=BORDER, pady=1, padx=1)
        pw.pack(fill="x", pady=(0,14))
        self.pe = tk.Entry(pw, bg=CARD, fg=TXT, insertbackground=TXT,
                           font=("Segoe UI",11), bd=0, relief="flat", show="●")
        self.pe.pack(fill="x", ipady=10, padx=1, pady=1)
        self.pe.bind("<FocusIn>",  lambda e: pw.config(bg=ACCENT))
        self.pe.bind("<FocusOut>", lambda e: pw.config(bg=BORDER))

        self.err = tk.Label(form, text="", bg=BG, fg=CRIT, font=("Segoe UI",9))
        self.err.pack(anchor="w", pady=(0,10))

        self.btn = tk.Button(form, text="Sign In  →",
                              bg=ACCENT, fg=TXT,
                              font=("Segoe UI",11,"bold"),
                              bd=0, relief="flat", cursor="hand2",
                              activebackground=ACCENT2,
                              activeforeground=TXT,
                              command=self._login)
        self.btn.pack(fill="x", ipady=12)
        self.btn.bind("<Enter>", lambda e: self.btn.config(bg=ACCENT2))
        self.btn.bind("<Leave>", lambda e: self.btn.config(bg=ACCENT))


    def _anim(self):
        if not self._run: return
        try:
            for p in self._pts:
                pid, vx, vy = p[0], p[1], p[2]
                c = self.lc.coords(pid)
                if not c: continue
                cx=(c[0]+c[2])/2+vx; cy=(c[1]+c[3])/2+vy; r=(c[2]-c[0])/2
                if cx<0 or cx>400: vx*=-1; p[1]=vx
                if cy<0 or cy>520: vy*=-1; p[2]=vy
                self.lc.coords(pid, cx-r,cy-r,cx+r,cy+r)
            self.after(40, self._anim)
        except: pass

    def _login(self):
        self.btn.config(text="Signing in…", state="disabled")
        self.after(400, self._check)

    def _check(self):
        uid = self.ue.get().strip()
        pwd = self.pe.get().strip()
        if uid == "admin" and pwd == "admin123":
            self._run = False; self.destroy(); AdminApp().mainloop()
        else:
            exists = False
            # Try CSV first (fast), then DB
            try:
                df = pd.read_csv(CSV)
                exists = uid in df["user_id"].astype(str).values
            except: pass
            if not exists:
                try:
                    c = db_conn()
                    if c:
                        with c.cursor() as cur:
                            cur.execute("SELECT COUNT(*) FROM wellbeing_data WHERE user_id=%s",(uid,))
                            exists = cur.fetchone()[0] > 0
                        c.close()
                except: pass
            if exists and pwd == "wellbeing":
                self._run = False; self.destroy(); UserApp(uid).mainloop()
            else:
                self.btn.config(text="Sign In  →", state="normal")
                self.pe.delete(0, tk.END); self.pe.focus()
                self.err.config(text="✕  Admin: admin / admin123  |  User: <user_id> / wellbeing")
                ox = self.winfo_x()
                for dx in [10,-10,8,-8,5,-5,0]:
                    self.geometry(f"+{ox+dx}+{self.winfo_y()}")
                    self.update(); time.sleep(0.04)

# ═══════════════════════════════════════════════════════
# TOPBAR BUILDER
# ═══════════════════════════════════════════════════════
def build_topbar(win, title, sub="", logout_cmd=None):
    top = tk.Frame(win, bg=CARD, height=54)
    top.pack(fill="x"); top.pack_propagate(False)
    tk.Frame(top, bg=ACCENT, width=3).pack(side="left", fill="y")
    tf = tk.Frame(top, bg=CARD); tf.pack(side="left", padx=14)
    tk.Label(tf, text=title, bg=CARD, fg=TXT,
             font=("Segoe UI",13,"bold")).pack(anchor="w", pady=(8,0))
    if sub:
        tk.Label(tf, text=sub, bg=CARD, fg=TXT2,
                 font=("Segoe UI",8)).pack(anchor="w")
    if logout_cmd:
        lo = tk.Button(top, text="Sign Out", bg=CARD, fg=TXT2,
                        font=("Segoe UI",9), bd=0, relief="flat",
                        cursor="hand2", padx=14, command=logout_cmd)
        lo.pack(side="right", pady=10, padx=10)
        lo.bind("<Enter>", lambda e: lo.config(fg=CRIT))
        lo.bind("<Leave>", lambda e: lo.config(fg=TXT2))
    tk.Frame(top, bg=SEP, height=1).pack(side="bottom", fill="x")
    return top

def build_navtabs(win, bg_win, pages, go_fn):
    nav = tk.Frame(bg_win, bg=CARD, height=36)
    nav.pack(fill="x"); nav.pack_propagate(False)
    tabs = {}
    for lbl, clr in pages:
        f = tk.Frame(nav, bg=CARD); f.pack(side="left")
        b = tk.Label(f, text=lbl, bg=CARD, fg=TXT2,
                      font=("Segoe UI",9), cursor="hand2",
                      padx=16, pady=8)
        b.pack()
        b.bind("<Button-1>", lambda e, l=lbl: go_fn(l))
        b.bind("<Enter>", lambda e, btn=b, c=clr: btn.config(fg=c) if btn.cget("fg")==TXT2 else None)
        b.bind("<Leave>", lambda e, btn=b, l=lbl, gfn=go_fn: None)
        tabs[lbl] = (f, b, clr)
    tk.Frame(bg_win, bg=SEP, height=1).pack(fill="x")
    return tabs

def update_tabs(tabs, active):
    for lbl, (f, btn, clr) in tabs.items():
        if lbl == active:
            btn.config(fg=clr, font=("Segoe UI",9,"bold"))
            f.config(bg=CARD2); btn.config(bg=CARD2)
        else:
            btn.config(fg=TXT2, font=("Segoe UI",9))
            f.config(bg=CARD); btn.config(bg=CARD)

# ═══════════════════════════════════════════════════════
# ADMIN APP
# ═══════════════════════════════════════════════════════
class AdminApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Digital Wellbeing Analytics — Admin")
        self.configure(bg=BG)
        self.state("zoomed")
        self.attributes("-alpha", 0.0)
        self.df   = load_data()
        self.page = "Overview"
        self._build()
        self._go("Overview")
        self._fade()

    def _fade(self, a=0.0):
        if a<1.0: self.attributes("-alpha",a); self.after(18,self._fade,a+0.09)

    def _build(self):
        build_topbar(self, "📱  Digital Wellbeing Analytics", "Admin Dashboard",
                     logout_cmd=lambda: (self.destroy(), Login().mainloop()))

        self._tabs = build_navtabs(self, self, [
            ("Overview", ACCENT3),
            ("User Lookup", INFO),
            ("All Users", OK),
            ("Compare", WARN),
        ], self._go)

        # Status bar
        sb = tk.Frame(self, bg=CARD, height=24)
        sb.pack(fill="x", side="bottom"); sb.pack_propagate(False)
        tk.Frame(sb, bg=SEP, height=1).pack(side="top", fill="x")
        self.st = tk.Label(sb, text="", bg=CARD, fg=TXT3,
                            font=("Segoe UI",8), anchor="w")
        self.st.pack(side="left", padx=12)
        tk.Label(sb, text="Digital Wellbeing Analytics  v3.0",
                 bg=CARD, fg=TXT3, font=("Segoe UI",8)).pack(side="right", padx=14)

        self.content = tk.Frame(self, bg=BG)
        self.content.pack(fill="both", expand=True)

    def _go(self, name):
        self.page = name
        update_tabs(self._tabs, name)
        self.content.unbind_all("<MouseWheel>")
        for w in self.content.winfo_children(): w.destroy()
        self.st.config(text=f"Page: {name}  ·  Total: {len(self.df):,}  ·  "
                             f"High Risk: {len(self.df[self.df['risk']=='High Risk']):,}  ·  "
                             f"Healthy: {len(self.df[self.df['risk']=='Healthy']):,}")
        {"Overview":   self._pg_overview,
         "User Lookup":self._pg_lookup,
         "All Users":  self._pg_all,
         "Compare":    self._pg_compare}.get(name, self._pg_overview)()

    def _sf(self):
        sf = SF(self.content); sf.pack(fill="both", expand=True); return sf.inner

    # ── Overview ──────────────────────────────────────
    def _pg_overview(self):
        df = self.df; n = len(df)
        inner = self._sf()
        page_title(inner, "Population Overview",
                   f"Analytics across {n:,} users  ·  {datetime.now().strftime('%d %B %Y')}")

        # KPIs
        kpi_row(inner, [
            ("👥","Total Users",       f"{n:,}",          "in dataset",   ACCENT3),
            ("⚠️","High Risk",         f"{len(df[df['risk']=='High Risk']):,}", "score < 40", CRIT),
            ("⚡","Moderate",          f"{len(df[df['risk']=='Moderate']):,}",  "score 40-70",WARN),
            ("✓", "Healthy",          f"{len(df[df['risk']=='Healthy']):,}",   "score > 70", OK),
            ("📱","Avg Screen Time",   f"{df['daily_screen_time_hours'].mean():.1f}h","per day",INFO),
            ("🧠","Avg Score",         f"{df['score'].mean():.0f}/100",         "population",ACCENT3),
        ])

        # Charts
        section_hdr(inner, "Distribution Analysis")
        r = grid_row(inner, 2)
        r.grid_columnconfigure(0,weight=1); r.grid_columnconfigure(1,weight=1)

        # Risk distribution
        rc = df["risk"].value_counts().reindex(["Healthy","Moderate","High Risk"],fill_value=0)
        f1, a1 = plt.subplots(figsize=(5.2,3.2))
        clrs = [OK, WARN, CRIT]
        bars = a1.bar(rc.index, rc.values, color=clrs, width=0.5, edgecolor="none")
        for b in bars:
            a1.text(b.get_x()+b.get_width()/2, b.get_height()+10,
                    f"{int(b.get_height()):,}", ha="center", color=TXT, fontsize=9, fontweight="bold")
        a1.set_ylabel("Users", fontsize=8); plt.tight_layout()
        chart_card(r, f1, "Users by Risk Level", r=0, c=0)

        # Score distribution
        f2, a2 = plt.subplots(figsize=(5.2,3.2))
        a2.hist(df["score"], bins=20, color=ACCENT, edgecolor=CARD, alpha=0.9)
        a2.axvline(df["score"].mean(), color=WARN, lw=2, ls="--",
                   label=f"Avg: {df['score'].mean():.0f}")
        a2.axvline(70, color=OK,   lw=1.5, ls=":", label="Healthy (70)")
        a2.axvline(40, color=CRIT, lw=1.5, ls=":", label="High Risk (40)")
        a2.set_xlabel("Wellbeing Score", fontsize=8)
        a2.set_ylabel("Users", fontsize=8)
        a2.legend(fontsize=7); plt.tight_layout()
        chart_card(r, f2, "Score Distribution", r=0, c=1)

        # Key insights
        section_hdr(inner, "Key Insights")
        ins = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        ins.pack(fill="x", padx=24, pady=(0,16))

        high_r   = len(df[df['risk']=='High Risk'])/n*100
        above_sc = len(df[df['daily_screen_time_hours']>6])/n*100
        poor_sl  = len(df[df['sleep_hours']<6])/n*100
        hi_no    = len(df[df['notifications_per_day']>100])/n*100
        avg_sc   = df['score'].mean()
        best_age = df.groupby("age_group",observed=True)["score"].mean().idxmax() if n>0 else "N/A"

        insights = [
            (f"{high_r:.1f}% ({len(df[df['risk']=='High Risk']):,} users) are HIGH RISK — score below 40", CRIT),
            (f"{above_sc:.1f}% exceed the 6h screen limit — avg {df['daily_screen_time_hours'].mean():.1f}h vs 6h recommended", WARN),
            (f"{poor_sl:.1f}% sleep under 6h — directly linked to poor wellbeing scores", CRIT),
            (f"{hi_no:.1f}% receive 100+ notifications/day — disrupts focus and sleep", WARN),
            (f"Population avg score: {avg_sc:.0f}/100 — grade {get_score_label(int(avg_sc))[0]} ({get_score_label(int(avg_sc))[1]})", OK if avg_sc>=70 else WARN),
            (f"Best performing age group: {best_age} — highest average wellbeing score", INFO),
        ]
        for i, (txt, clr) in enumerate(insights):
            rf = tk.Frame(ins, bg=CARD); rf.pack(fill="x", padx=2)
            tk.Frame(rf, bg=clr, width=3).pack(side="left", fill="y")
            tk.Label(rf, text=f"  {txt}", bg=CARD, fg=TXT2,
                     font=("Segoe UI",9), anchor="w").pack(fill="x", padx=10, pady=7)
            if i < len(insights)-1:
                tk.Frame(ins, bg=SEP, height=1).pack(fill="x", padx=14)

    # ── User Lookup ───────────────────────────────────
    def _pg_lookup(self):
        inner = self._sf()
        page_title(inner, "User Lookup",
                   "Search any user to view their complete personal wellbeing analysis")

        sf2 = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        sf2.pack(fill="x", padx=24, pady=(0,14))
        si = tk.Frame(sf2, bg=CARD); si.pack(fill="x", padx=16, pady=14)

        tk.Label(si, text="User ID:", bg=CARD, fg=TXT2,
                 font=("Segoe UI",10)).pack(side="left", padx=(0,10))
        wrap = tk.Frame(si, bg=BORDER, pady=1, padx=1); wrap.pack(side="left", padx=(0,10))
        uid_v = tk.StringVar()
        uid_e = tk.Entry(wrap, textvariable=uid_v, bg=CARD, fg=TXT,
                          insertbackground=TXT, font=("Segoe UI",11),
                          bd=0, relief="flat", width=14)
        uid_e.pack(ipady=8, padx=1, pady=1)
        uid_e.bind("<FocusIn>",  lambda e: wrap.config(bg=ACCENT))
        uid_e.bind("<FocusOut>", lambda e: wrap.config(bg=BORDER))

        tk.Label(si, text="or:", bg=CARD, fg=TXT3,
                 font=("Segoe UI",9)).pack(side="left", padx=(6,6))
        sample = sorted(self.df["user_id"].sample(min(20,len(self.df))).tolist())
        pv = tk.StringVar(value="Pick a sample…")
        pcb = ttk.Combobox(si, textvariable=pv, values=sample,
                            state="readonly", width=14, font=("Segoe UI",9))
        pcb.pack(side="left", padx=(0,10))
        pcb.bind("<<ComboboxSelected>>", lambda e: uid_v.set(pv.get()))

        result = tk.Frame(inner, bg=BG); result.pack(fill="both", expand=True)

        def search():
            for w in result.winfo_children(): w.destroy()
            uid = uid_v.get().strip()
            if not uid:
                tk.Label(result, text="Enter a User ID above to search",
                         bg=BG, fg=TXT2, font=("Segoe UI",12)).pack(pady=30)
                return
            rows = self.df[self.df["user_id"].astype(str).str.upper()==uid.upper()]
            if rows.empty:
                tk.Label(result, text=f"User '{uid}' not found in database",
                         bg=BG, fg=CRIT, font=("Segoe UI",11)).pack(pady=30)
                return
            show_full_report(result, rows.iloc[0], self.df)

        sbtn = tk.Button(si, text="Search →",
                          bg=ACCENT, fg=TXT,
                          font=("Segoe UI",10,"bold"),
                          bd=0, relief="flat", cursor="hand2",
                          padx=16, pady=8, command=search)
        sbtn.pack(side="left")
        sbtn.bind("<Enter>", lambda e: sbtn.config(bg=ACCENT2))
        sbtn.bind("<Leave>", lambda e: sbtn.config(bg=ACCENT))
        uid_e.bind("<Return>", lambda e: search())

        tk.Label(result, text="Enter a User ID to see their full report",
                 bg=BG, fg=TXT3, font=("Segoe UI",11)).pack(pady=40)

    # ── All Users ─────────────────────────────────────
    def _pg_all(self):
        df = self.df
        page_title(self.content, "All Users",
                   "Complete user table. Double-click any row to open full report.")

        # Toolbar
        tb = tk.Frame(self.content, bg=CARD, height=44)
        tb.pack(fill="x"); tb.pack_propagate(False)
        tk.Frame(tb, bg=SEP, height=1).pack(side="bottom", fill="x")
        ti = tk.Frame(tb, bg=CARD); ti.pack(fill="x", padx=14, pady=6)

        sv = tk.StringVar(); rv = tk.StringVar(value="All"); gv = tk.StringVar(value="All")
        wrap = tk.Frame(ti, bg=BORDER, pady=1, padx=1); wrap.pack(side="left", padx=(0,8))
        se = tk.Entry(wrap, textvariable=sv, bg=CARD, fg=TXT,
                       insertbackground=TXT, font=("Segoe UI",9),
                       bd=0, relief="flat", width=20)
        se.pack(ipady=5, padx=1, pady=1)
        se.insert(0, "Search…")
        se.bind("<FocusIn>",  lambda e: (se.delete(0,tk.END) if se.get()=="Search…" else None,
                                          wrap.config(bg=ACCENT)))
        se.bind("<FocusOut>", lambda e: wrap.config(bg=BORDER))

        for lbl, var, vals in [("Risk:", rv, ["All","High Risk","Moderate","Healthy"]),
                                 ("Gender:", gv, ["All"]+sorted(df["gender"].unique().tolist()))]:
            tk.Label(ti, text=lbl, bg=CARD, fg=TXT2,
                     font=("Segoe UI",9)).pack(side="left", padx=(8,4))
            cb = ttk.Combobox(ti, textvariable=var, values=vals,
                               state="readonly", width=10, font=("Segoe UI",9))
            cb.pack(side="left", padx=(0,8))
            cb.bind("<<ComboboxSelected>>", lambda e: pop())

        cnt = tk.Label(ti, text="", bg=CARD, fg=TXT2, font=("Segoe UI",9))
        cnt.pack(side="left", padx=8)

        vdf = [df.copy()]

        def export():
            p = filedialog.asksaveasfilename(defaultextension=".csv",
                                              filetypes=[("CSV","*.csv")])
            if p: vdf[0].to_csv(p, index=False); toast(self, f"Exported {len(vdf[0]):,} rows")

        tk.Button(ti, text="Export CSV", bg=CARD2, fg=TXT2,
                   font=("Segoe UI",9), bd=0, relief="flat",
                   cursor="hand2", padx=12, pady=5,
                   command=export).pack(side="right")

        # Table
        tf = tk.Frame(self.content, bg=BG)
        tf.pack(fill="both", expand=True, padx=24, pady=(6,14))

        s = ttk.Style(); s.theme_use("clam")
        s.configure("D.Treeview", background=CARD, foreground=TXT,
                     rowheight=28, fieldbackground=CARD,
                     borderwidth=0, font=("Segoe UI",9))
        s.configure("D.Treeview.Heading", background=CARD2, foreground=TXT2,
                     font=("Segoe UI",9,"bold"), borderwidth=0, relief="flat")
        s.map("D.Treeview", background=[("selected",ACCENT)],
              foreground=[("selected",TXT)])

        cols = ["user_id","name","age","gender","city","occupation",
                "daily_screen_time_hours","sleep_hours","notifications_per_day","score","risk"]
        tv = ttk.Treeview(tf, columns=cols, show="headings",
                           selectmode="browse", style="D.Treeview")
        vs = ttk.Scrollbar(tf, orient="vertical",   command=tv.yview)
        hs = ttk.Scrollbar(tf, orient="horizontal", command=tv.xview)
        tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        vs.grid(row=0,column=1,sticky="ns"); hs.grid(row=1,column=0,sticky="ew")
        tv.grid(row=0,column=0,sticky="nsew")
        tf.grid_rowconfigure(0,weight=1); tf.grid_columnconfigure(0,weight=1)

        widths = {"user_id":80,"name":90,"age":40,"gender":65,"city":80,"occupation":90,
                  "daily_screen_time_hours":80,"sleep_hours":65,"notifications_per_day":80,
                  "score":60,"risk":80}
        for col in cols:
            tv.heading(col, text=col.replace("_"," ").title())
            tv.column(col, width=widths.get(col,80), anchor="center", minwidth=50)

        def pop():
            view = df.copy()
            if rv.get()!="All": view = view[view["risk"]==rv.get()]
            if gv.get()!="All": view = view[view["gender"]==gv.get()]
            q = sv.get().strip().lower()
            if q and q!="search…":
                view = view[view.apply(lambda r: r.astype(str).str.lower().str.contains(q).any(),axis=1)]
            vdf[0] = view
            tv.delete(*tv.get_children())
            for i, row in enumerate(view[cols].itertuples(index=False)):
                tv.insert("","end",values=list(row),
                           tags=("odd" if i%2==0 else "even",))
            tv.tag_configure("odd",  background=CARD)
            tv.tag_configure("even", background=CARD2)
            cnt.config(text=f"{len(view):,} users")

        pop()
        sv.trace_add("write", lambda *_: pop())
        tv.bind("<MouseWheel>", lambda e: tv.yview_scroll(int(-1*(e.delta/120)),"units"))

        def on_dbl(e):
            sel = tv.selection()
            if not sel: return
            uid = str(tv.item(sel[0])["values"][0])
            rows = self.df[self.df["user_id"].astype(str)==uid]
            if rows.empty: return
            win = tk.Toplevel(self)
            win.title(f"Report — {uid}")
            win.configure(bg=BG)
            win.geometry(f"900x640+{(self.winfo_screenwidth()-900)//2}+{(self.winfo_screenheight()-640)//2}")
            win.grab_set()
            sf3 = SF(win); sf3.pack(fill="both", expand=True)
            show_full_report(sf3.inner, rows.iloc[0], self.df)
            tk.Button(win, text="Close", bg=ACCENT, fg=TXT,
                       font=("Segoe UI",10,"bold"), bd=0, relief="flat",
                       cursor="hand2", padx=20, pady=8,
                       command=win.destroy).pack(pady=10)
        tv.bind("<Double-Button-1>", on_dbl)

        tk.Label(self.content, text="Double-click any row to open full individual report",
                 bg=BG, fg=TXT3, font=("Segoe UI",8)).pack(pady=(0,4))

    # ── Compare ───────────────────────────────────────
    def _pg_compare(self):
        inner = self._sf()
        page_title(inner, "Compare Users or Groups",
                   "Side-by-side comparison against healthy limits")

        cf = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        cf.pack(fill="x", padx=24, pady=(0,12))
        ci = tk.Frame(cf, bg=CARD); ci.pack(fill="x", padx=16, pady=12)

        all_ids = sorted(self.df["user_id"].tolist())
        av = tk.StringVar(value=all_ids[0] if all_ids else "")
        bv = tk.StringVar(value=all_ids[1] if len(all_ids)>1 else "")
        mode = tk.StringVar(value="users")

        for val, lbl in [("users","Compare 2 Users"),("groups","Compare Age Groups")]:
            tk.Radiobutton(ci, text=lbl, variable=mode, value=val,
                            bg=CARD, fg=TXT, selectcolor=CARD2,
                            font=("Segoe UI",10), cursor="hand2",
                            activebackground=CARD).pack(side="left", padx=12)

        tk.Label(ci, text="  User A:", bg=CARD, fg=TXT2,
                 font=("Segoe UI",10)).pack(side="left", padx=(16,4))
        ttk.Combobox(ci, textvariable=av, values=all_ids,
                      width=14, font=("Segoe UI",9)).pack(side="left", padx=(0,10))
        tk.Label(ci, text="User B:", bg=CARD, fg=TXT2,
                 font=("Segoe UI",10)).pack(side="left", padx=(0,4))
        ttk.Combobox(ci, textvariable=bv, values=all_ids,
                      width=14, font=("Segoe UI",9)).pack(side="left", padx=(0,10))

        res = tk.Frame(inner, bg=BG); res.pack(fill="both", expand=True, padx=4)

        def compare():
            for w in res.winfo_children(): w.destroy()
            if mode.get() == "users":
                ra = self.df[self.df["user_id"]==av.get()]
                rb2 = self.df[self.df["user_id"]==bv.get()]
                if ra.empty or rb2.empty:
                    tk.Label(res, text="User not found", bg=BG, fg=CRIT,
                             font=("Segoe UI",11)).pack(pady=20); return
                _compare_two_users(res, ra.iloc[0], rb2.iloc[0])
            else:
                _compare_age_groups(res, self.df)

        tk.Button(ci, text="Compare →",
                   bg=ACCENT, fg=TXT,
                   font=("Segoe UI",10,"bold"),
                   bd=0, relief="flat", cursor="hand2",
                   padx=16, pady=8, command=compare).pack(side="left", padx=10)

# ═══════════════════════════════════════════════════════
# FULL INDIVIDUAL REPORT (shared by admin + user app)
# ═══════════════════════════════════════════════════════
def show_full_report(parent, row, all_df):
    """Complete personal wellbeing report for one user."""
    wb   = int(row["score"])
    risk = row["risk"]
    sclr = get_status_color(wb)
    grade, glabel = get_score_label(wb)

    # ── Profile header ────────────────────────────────
    hdr = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    hdr.pack(fill="x", padx=24, pady=(12,0))
    hi = tk.Frame(hdr, bg=CARD); hi.pack(fill="x", padx=16, pady=14)

    tk.Frame(hdr, bg=sclr, height=2).pack(fill="x", side="top")

    # Name + details
    nf = tk.Frame(hi, bg=CARD); nf.pack(side="left", fill="x", expand=True)
    tk.Label(nf, text=f"{row['name']}",
             bg=CARD, fg=TXT, font=("Segoe UI",15,"bold"), anchor="w").pack(anchor="w")
    tk.Label(nf,
             text=f"ID: {row['user_id']}   ·   Age {int(row['age'])}   ·   {row['gender']}   ·   {row.get('city','Unknown')}   ·   {row.get('occupation','Unknown')}",
             bg=CARD, fg=TXT2, font=("Segoe UI",9), anchor="w").pack(anchor="w", pady=(3,0))

    # Score badge
    sf2 = tk.Frame(hi, bg=CARD2); sf2.pack(side="right")
    tk.Label(sf2, text=f"  {wb}  ", bg=CARD2, fg=sclr,
             font=("Segoe UI",28,"bold")).pack(padx=8)
    tk.Label(sf2, text=f"  / 100  Grade {grade} — {glabel}  {risk}  ",
             bg=CARD2, fg=TXT2, font=("Segoe UI",8)).pack(padx=8, pady=(0,8))

    # ── Metric KPIs ───────────────────────────────────
    sc = float(row["daily_screen_time_hours"])
    so = float(row["social_media_hours"])
    ga = float(row["gaming_hours"])
    sl = float(row["sleep_hours"])
    no = float(row["notifications_per_day"])
    wo = float(row["work_study_hours"])

    kpi_row(parent, [
        ("📱","Screen Time",  f"{sc:.1f}h","per day",   CRIT if sc>6 else OK),
        ("📲","Social Media", f"{so:.1f}h","per day",   CRIT if so>2 else OK),
        ("🎮","Gaming",       f"{ga:.1f}h","per day",   WARN if ga>1.5 else OK),
        ("😴","Sleep",        f"{sl:.1f}h","per night", CRIT if sl<6 else OK),
        ("🔔","Notifications",f"{int(no)}", "per day",  CRIT if no>100 else WARN if no>50 else OK),
        ("💼","Work/Study",   f"{wo:.1f}h","per day",   INFO),
    ])

    # ── Personal health summary ───────────────────────
    section_hdr(parent, "Personal Health Summary")

    # Calculate real impact numbers
    excess_sc   = max(0, sc - 6.0)
    sleep_debt  = max(0, 7.0 - sl)
    focus_lost  = max(0, (no - 50) * 23 / 60)
    prod_ratio  = (wo / sc * 100) if sc > 0 else 0

    summary_items = []

    # Screen time impact
    if excess_sc > 0:
        summary_items.append((CRIT,
            f"📱  {excess_sc:.1f}h excess screen time daily = {round(excess_sc*365/24)} extra days/year on phone",
            f"You use more screen time than {int((all_df['daily_screen_time_hours'] < sc).mean()*100)}% of users. Reduce to 6h to gain back {round(excess_sc*365/24)} days annually."))
    else:
        summary_items.append((OK,
            f"📱  Screen time {sc:.1f}h is within the 6h limit ✅",
            f"Better than {int((all_df['daily_screen_time_hours'] > sc).mean()*100)}% of users. Keep maintaining this."))

    # Sleep impact
    if sleep_debt > 0:
        summary_items.append((WARN,
            f"😴  Sleeping {sl:.1f}h instead of 7h = {round(sleep_debt*365/24)} days of sleep lost per year",
            f"Poor sleep increases phone usage. Your sleep is below {int((all_df['sleep_hours'] < sl).mean()*100)}% of users."))
    else:
        summary_items.append((OK,
            f"😴  Sleep {sl:.1f}h is healthy ✅  — better than {int((all_df['sleep_hours'] < sl).mean()*100)}% of users",
            "Good sleep reduces phone dependency and improves focus significantly."))

    # Notifications focus loss
    if focus_lost > 0.5:
        summary_items.append((WARN,
            f"🔔  {int(no)} notifications/day costs {focus_lost:.1f}h of focus daily = {round(focus_lost*5):.0f}h/week lost",
            "Each notification takes ~23 min to recover from. Turn off non-essential alerts now."))

    # Productivity insight
    summary_items.append((INFO,
        f"💼  {prod_ratio:.0f}% of your screen time is productive (work/study = {wo:.1f}h of {sc:.1f}h total)",
        f"{'Good balance!' if prod_ratio >= 40 else 'Consider increasing productive screen time and reducing entertainment.'}"))

    for clr, msg, tip in summary_items:
        card = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.pack(fill="x", padx=24, pady=4)
        tk.Frame(card, bg=clr, width=4).pack(side="left", fill="y")
        ci3 = tk.Frame(card, bg=CARD)
        ci3.pack(fill="x", padx=14, pady=12, side="left", expand=True)
        tk.Label(ci3, text=msg, bg=CARD, fg=TXT,
                 font=("Segoe UI",10,"bold"), anchor="w",
                 wraplength=820).pack(anchor="w")
        tk.Label(ci3, text=tip, bg=CARD, fg=TXT2,
                 font=("Segoe UI",9), anchor="w",
                 wraplength=820).pack(anchor="w", pady=(3,0))

    # ── Warnings & Recommendations ────────────────────
    section_hdr(parent, "Warnings & Recommendations")
    for metric, value, limit, color, severity, message, action in analyze_user(row):
        analysis_card(parent, metric, value, limit, color, severity, message, action)

    # ── Percentile comparison ─────────────────────────
    section_hdr(parent, "How You Compare to All Users")
    cf2 = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    cf2.pack(fill="x", padx=24, pady=(0,8))
    ci2 = tk.Frame(cf2, bg=CARD); ci2.pack(fill="x", padx=16, pady=14)

    for metric, val, col_name, better_low in [
        ("Screen Time",     sc, "daily_screen_time_hours", True),
        ("Sleep",           sl, "sleep_hours",             False),
        ("Social Media",    so, "social_media_hours",      True),
        ("Notifications",   no, "notifications_per_day",   True),
        ("Wellbeing Score", wb, "score",                   False),
    ]:
        pct = float((all_df[col_name]<=val).mean()*100)
        if better_low:
            status = f"Lower than {100-pct:.0f}% of users"
            clr = OK if pct<=50 else WARN if pct<=75 else CRIT
        else:
            status = f"Higher than {pct:.0f}% of users"
            clr = OK if pct>=60 else WARN if pct>=40 else CRIT

        rf = tk.Frame(ci2, bg=CARD); rf.pack(fill="x", pady=5)
        tk.Label(rf, text=metric, bg=CARD, fg=TXT2,
                 font=("Segoe UI",9), width=16, anchor="w").pack(side="left")
        tk.Label(rf, text=f"{val:.1f}  " if isinstance(val,float) else f"{val}  ",
                 bg=CARD, fg=TXT, font=("Segoe UI",9,"bold"), width=7).pack(side="left")
        bg3 = tk.Frame(rf, bg=BORDER, height=6, width=180)
        bg3.pack(side="left", padx=(8,10))
        tk.Frame(bg3, bg=clr, height=6, width=int(pct*1.8)).place(x=0,y=0)
        tk.Label(rf, text=status, bg=CARD, fg=clr,
                 font=("Segoe UI",8)).pack(side="left")

    # ── Daily goals ───────────────────────────────────
    section_hdr(parent, "Today's Goals")
    for icon, goal, tip in get_daily_goals(row):
        gf = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        gf.pack(fill="x", padx=24, pady=3)
        gi = tk.Frame(gf, bg=CARD); gi.pack(fill="x", padx=16, pady=10)
        tk.Label(gi, text=icon, bg=CARD, fg=TXT2,
                 font=("Segoe UI Emoji",14)).pack(side="left", padx=(0,12))
        tf3 = tk.Frame(gi, bg=CARD); tf3.pack(side="left", fill="x", expand=True)
        tk.Label(tf3, text=goal, bg=CARD, fg=TXT,
                 font=("Segoe UI",10,"bold"), anchor="w").pack(anchor="w")
        tk.Label(tf3, text=tip, bg=CARD, fg=TXT2,
                 font=("Segoe UI",8), anchor="w").pack(anchor="w", pady=(2,0))

# ═══════════════════════════════════════════════════════
# COMPARE HELPERS
# ═══════════════════════════════════════════════════════
def _compare_two_users(parent, r1, r2):
    metrics = ["daily_screen_time_hours","social_media_hours",
               "gaming_hours","sleep_hours","work_study_hours"]
    labels  = ["Screen","Social","Gaming","Sleep","Work"]
    limits  = [6.0, 2.0, 1.5, 7.0, 4.0]
    v1 = [float(r1[m]) for m in metrics]
    v2 = [float(r2[m]) for m in metrics]

    # Profile cards
    row = tk.Frame(parent, bg=BG); row.pack(fill="x", padx=16, pady=8)
    row.grid_columnconfigure(0,weight=1); row.grid_columnconfigure(1,weight=1)
    for ci, (r, side) in enumerate([(r1,"A"),(r2,"B")]):
        wb   = int(r["score"]); clr = get_status_color(wb)
        card = tk.Frame(row, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        card.grid(row=0, column=ci, padx=6, pady=6, sticky="nsew")
        tk.Frame(card, bg=clr, height=2).pack(fill="x")
        ci2 = tk.Frame(card, bg=CARD); ci2.pack(fill="x", padx=14, pady=12)
        tk.Label(ci2, text=f"User {side}: {r['name']}",
                 bg=CARD, fg=TXT, font=("Segoe UI",12,"bold"), anchor="w").pack(anchor="w")
        tk.Label(ci2, text=f"Score: {wb}/100  ·  {r['risk']}  ·  Age {int(r['age'])}  ·  {r['gender']}",
                 bg=CARD, fg=TXT2, font=("Segoe UI",9), anchor="w").pack(anchor="w", pady=(4,0))

    # Chart
    fig, ax = plt.subplots(figsize=(9, 3.2))
    x = np.arange(len(labels)); w = 0.28
    ax.bar(x-w, v1, w, color=ACCENT,  label=f"User A: {r1['name']}", edgecolor="none")
    ax.bar(x,   v2, w, color=ACCENT3, label=f"User B: {r2['name']}", edgecolor="none")
    ax.bar(x+w, limits, w, color=BORDER, label="Healthy Limit", edgecolor="none", alpha=0.6)
    ax.set_xticks(x); ax.set_xticklabels(labels); ax.set_ylabel("Hours", fontsize=8)
    ax.legend(fontsize=8, facecolor=CARD, edgecolor=BORDER, labelcolor=TXT)
    for i, (a_v, b_v) in enumerate(zip(v1, v2)):
        ax.text(i-w,   a_v+0.05, f"{a_v:.1f}", ha="center", color=TXT, fontsize=7)
        ax.text(i,     b_v+0.05, f"{b_v:.1f}", ha="center", color=TXT, fontsize=7)
    plt.tight_layout()
    chart_card(parent, fig, "Side-by-Side vs Healthy Limits", full=True)

    # Winner summary
    wf = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
    wf.pack(fill="x", padx=24, pady=(0,12))
    wi = tk.Frame(wf, bg=CARD); wi.pack(fill="x", padx=16, pady=12)
    tk.Label(wi, text="Comparison Summary", bg=CARD, fg=TXT,
             font=("Segoe UI",11,"bold")).pack(anchor="w", pady=(0,8))
    for lbl, mv, hi in [("Screen Time","daily_screen_time_hours",False),
                          ("Sleep","sleep_hours",True),
                          ("Social Media","social_media_hours",False),
                          ("Wellbeing Score","score",True)]:
        a = float(r1[mv]); b = float(r2[mv])
        winner = "A" if (a>b)==hi else "B"
        rf2 = tk.Frame(wi, bg=CARD); rf2.pack(fill="x", pady=3)
        tk.Label(rf2, text=f"{lbl}:", bg=CARD, fg=TXT2,
                 font=("Segoe UI",9), width=16, anchor="w").pack(side="left")
        tk.Label(rf2, text=f"A: {a:.1f}  vs  B: {b:.1f}",
                 bg=CARD, fg=TXT, font=("Segoe UI",9)).pack(side="left", padx=8)
        tk.Label(rf2, text=f"→  User {winner} is better",
                 bg=CARD, fg=OK, font=("Segoe UI",9,"bold")).pack(side="left")

def _compare_age_groups(parent, df):
    agg = df.groupby("age_group", observed=True).agg(
        Users=("user_id","count"),
        Score=("score","mean"),
        Screen=("daily_screen_time_hours","mean"),
        Sleep=("sleep_hours","mean"),
    ).reindex(["18-24","25-34","35-44","45+"]).fillna(0).round(2).reset_index()

    fig, axes = plt.subplots(1, 3, figsize=(12,3.2))
    clrs = [ACCENT, ACCENT3, INFO, OK]
    for ax, col, title in zip(axes,
        ["Score","Screen","Sleep"],
        ["Avg Wellbeing Score","Avg Screen Time (h)","Avg Sleep (h)"]):
        bars = ax.bar(agg["age_group"], agg[col], color=clrs, edgecolor="none", width=0.55)
        for b in bars:
            ax.text(b.get_x()+b.get_width()/2, b.get_height()+0.3,
                    f"{b.get_height():.1f}", ha="center", color=TXT, fontsize=8, fontweight="bold")
        ax.set_title(title, fontsize=9, pad=6); ax.spines[:].set_visible(False)
    plt.tight_layout()
    chart_card(parent, fig, "Age Group Comparison", full=True)
    make_tree(parent, agg)

# ═══════════════════════════════════════════════════════
# USER APP (personal dashboard)
# ═══════════════════════════════════════════════════════
class UserApp(tk.Tk):
    """Simple personal dashboard for individual users."""
    def __init__(self, uid):
        super().__init__()
        self.df  = load_data()
        rows = self.df[self.df["user_id"].astype(str)==uid]
        if rows.empty:
            messagebox.showerror("Error", f"User {uid} not found")
            self.destroy(); return
        self.row  = rows.iloc[0]
        self.name = str(self.row["name"])
        wb   = int(self.row["score"])
        sclr = get_status_color(wb)
        grade, glabel = get_score_label(wb)
        self.title(f"My Wellbeing — {self.name}")
        self.configure(bg=BG)
        self.state("zoomed")
        self.attributes("-alpha", 0.0)
        self._build(wb, sclr, grade, glabel)
        self._fade()
    def _fade(self, a=0.0):
        if a<1.0: self.attributes("-alpha",a); self.after(18,self._fade,a+0.09)
    def _build(self, wb, sclr, grade, glabel):
        # Top bar
        top = tk.Frame(self, bg=CARD, height=54); top.pack(fill="x"); top.pack_propagate(False)
        tk.Frame(top, bg=sclr, width=4).pack(side="left", fill="y")
        tf = tk.Frame(top, bg=CARD); tf.pack(side="left", padx=14)
        tk.Label(tf, text=f"👤  {self.name}",
                 bg=CARD, fg=TXT, font=("Segoe UI",13,"bold")).pack(anchor="w", pady=(8,0))
        tk.Label(tf, text=f"Score: {wb}/100  ·  Grade {grade}  ·  {self.row['risk']}",
                 bg=CARD, fg=sclr, font=("Segoe UI",8)).pack(anchor="w")
        lo = tk.Button(top, text="Sign Out", bg=CARD, fg=TXT2,
                        font=("Segoe UI",9), bd=0, relief="flat", cursor="hand2",
                        padx=14, command=lambda:(self.destroy(), Login().mainloop()))
        lo.pack(side="right", pady=10, padx=10)
        tk.Frame(top, bg=SEP, height=1).pack(side="bottom", fill="x")
        # Nav tabs — just 3 simple ones
        nav = tk.Frame(self, bg=CARD, height=36); nav.pack(fill="x"); nav.pack_propagate(False)
        self._tabs = {}; self.page = "Dashboard"
        for lbl, clr in [("Dashboard", ACCENT3), ("My Analysis", INFO), ("Action Plan", OK)]:
            f = tk.Frame(nav, bg=CARD); f.pack(side="left")
            b = tk.Label(f, text=lbl, bg=CARD, fg=TXT2,
                          font=("Segoe UI",9), cursor="hand2", padx=16, pady=8)
            b.pack()
            b.bind("<Button-1>", lambda e, l=lbl: self._go(l))
            b.bind("<Enter>", lambda e, btn=b, c=clr: btn.config(fg=c) if btn.cget("fg")==TXT2 else None)
            b.bind("<Leave>", lambda e, btn=b, l=lbl: btn.config(fg=TXT2) if l!=self.page else None)
            self._tabs[lbl] = (f, b, clr)
        tk.Frame(self, bg=SEP, height=1).pack(fill="x")
        self.content = tk.Frame(self, bg=BG); self.content.pack(fill="both", expand=True)
        self._go("Dashboard")
    def _go(self, name):
        self.page = name
        update_tabs(self._tabs, name)
        self.content.unbind_all("<MouseWheel>")
        for w in self.content.winfo_children(): w.destroy()
        {"Dashboard":    self._pg_dash,
         "My Analysis":  self._pg_analysis,
         "Action Plan":  self._pg_plan}.get(name, self._pg_dash)()
    def _sf(self):
        sf = SF(self.content); sf.pack(fill="both", expand=True); return sf.inner
    def _pg_dash(self):
        """Simple personal dashboard — score, metrics, quick insights."""
        row = self.row
        df  = self.df
        sc  = float(row["daily_screen_time_hours"])
        so  = float(row["social_media_hours"])
        ga  = float(row["gaming_hours"])
        sl  = float(row["sleep_hours"])
        no  = float(row["notifications_per_day"])
        wo  = float(row["work_study_hours"])
        wb  = int(row["score"])
        sclr = get_status_color(wb)
        grade, glabel = get_score_label(wb)
        inner = self._sf()
        page_title(inner, f"Good to see you, {self.name}!",
                   datetime.now().strftime("%A, %d %B %Y"))
        # Score banner
        banner = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=sclr)
        banner.pack(fill="x", padx=24, pady=(0,14))
        tk.Frame(banner, bg=sclr, height=3).pack(fill="x")
        bi = tk.Frame(banner, bg=CARD); bi.pack(fill="x", padx=18, pady=14)
        left = tk.Frame(bi, bg=CARD); left.pack(side="left", fill="x", expand=True)
        tk.Label(left, text=f"Your Wellbeing Score",
                 bg=CARD, fg=TXT2, font=("Segoe UI",10), anchor="w").pack(anchor="w")
        tk.Label(left, text=f"{wb} / 100",
                 bg=CARD, fg=sclr, font=("Segoe UI",32,"bold"), anchor="w").pack(anchor="w")
        tk.Label(left, text=f"Grade {grade} — {glabel}  ·  {row['risk']}",
                 bg=CARD, fg=sclr, font=("Segoe UI",10,"bold"), anchor="w").pack(anchor="w")
        # Progress bar
        bar_bg = tk.Frame(left, bg=BORDER, height=6); bar_bg.pack(fill="x", pady=(10,4))
        tk.Frame(bar_bg, bg=sclr, height=6, width=int(wb*8.6)).place(x=0,y=0)
        tk.Label(left, text=f"You score better than {int((df['score']<wb).mean()*100)}% of users",
                 bg=CARD, fg=TXT2, font=("Segoe UI",8)).pack(anchor="w")
        right = tk.Frame(bi, bg=CARD); right.pack(side="right")
        tk.Label(right, text="Today's Status", bg=CARD, fg=TXT3,
                 font=("Segoe UI",8)).pack(anchor="e")
        status_items = [
            (f"📱 Screen: {sc:.1f}h",  sc > 6),
            (f"😴 Sleep:  {sl:.1f}h",  sl < 7),
            (f"📲 Social: {so:.1f}h",  so > 2),
            (f"🔔 Notifs: {int(no)}",   no > 50),
        ]
        for metric, is_bad in status_items:
            clr = CRIT if is_bad else OK
            tk.Label(right, text=metric, bg=CARD, fg=clr,
                     font=("Segoe UI",9,"bold"), anchor="e").pack(anchor="e", pady=1)
        # 6 metric cards
        section_hdr(inner, "Your Metrics Today")
        kpi_row(inner, [
            ("📱","Screen Time",  f"{sc:.1f}h","per day",   CRIT if sc>6 else OK),
            ("📲","Social Media", f"{so:.1f}h","per day",   CRIT if so>2 else OK),
            ("🎮","Gaming",       f"{ga:.1f}h","per day",   WARN if ga>1.5 else OK),
            ("😴","Sleep",        f"{sl:.1f}h","per night", CRIT if sl<6 else OK),
            ("🔔","Notifications",f"{int(no)}","per day",   CRIT if no>100 else WARN if no>50 else OK),
            ("💼","Work/Study",   f"{wo:.1f}h","per day",   INFO),
        ])
        # 3 key insights
        section_hdr(inner, "Key Insights")
        insights = []
        # Screen time
        if sc > 6:
            excess_hrs = sc - 6
            excess_days = round(excess_hrs * 365 / 24)
            insights.append((CRIT,
                f"📱  Screen time is {sc:.1f}h/day — {excess_hrs:.1f}h above limit",
                f"That equals {excess_days} extra days per year on screens. "
                f"You are using more screen time than {int((df['daily_screen_time_hours'] < sc).mean()*100)}% of users."))
        else:
            insights.append((OK,
                f"📱  Screen time {sc:.1f}h/day is within the 6h healthy limit ✅",
                f"You use less screen time than {int((df['daily_screen_time_hours'] > sc).mean()*100)}% of users. Keep it up!"))

        # Sleep
        if sl < 7:
            debt = round((7 - sl) * 365 / 24)
            insights.append((WARN,
                f"😴  Sleep {sl:.1f}h/night — {7-sl:.1f}h below the 7h minimum",
                f"This accumulates to {debt} days of lost sleep per year. "
                f"Poor sleep is directly linked to higher screen time and lower focus."))
        else:
            insights.append((OK,
                f"😴  Sleep {sl:.1f}h/night is healthy ✅",
                f"Good sleep improves focus, mood and reduces phone dependency."))

        # Best and worst metric
        metrics_check = {
            "Screen Time": (sc, 6.0, True),
            "Social Media": (so, 2.0, True),
            "Sleep": (sl, 7.0, False),
            "Notifications": (no, 50, True),
        }
        worst_name, worst_gap = max(
            [(k, abs(v-l) if bad else max(0, l-v))
             for k,(v,l,bad) in metrics_check.items()],
            key=lambda x: x[1])
        insights.append((INFO,
            f"💡  Your biggest area to improve: {worst_name}",
            f"Fixing {worst_name} first will have the highest impact on your wellbeing score."))

        for clr, msg, tip in insights[:3]:
            card = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
            card.pack(fill="x", padx=24, pady=4)
            tk.Frame(card, bg=clr, width=4).pack(side="left", fill="y")
            ci2 = tk.Frame(card, bg=CARD)
            ci2.pack(fill="x", padx=14, pady=12, side="left", expand=True)
            tk.Label(ci2, text=msg, bg=CARD, fg=TXT,
                     font=("Segoe UI",10,"bold"), anchor="w",
                     wraplength=800).pack(anchor="w")
            tk.Label(ci2, text=tip, bg=CARD, fg=TXT2,
                     font=("Segoe UI",9), anchor="w",
                     wraplength=800).pack(anchor="w", pady=(4,0))

        # Simple bar chart — today's usage vs limits
        section_hdr(inner, "How You Spend Your Day")

        # Donut chart — 24h time allocation
        sleep_h  = sl
        work_h   = wo
        social_h = so
        gaming_h = ga
        other_sc = max(0, sc - so - ga)
        free_h   = max(0, 24 - sc - sleep_h - work_h)

        sizes  = [social_h, gaming_h, other_sc, work_h, sleep_h, free_h]
        labels = [f"Social\n{social_h:.1f}h", f"Gaming\n{gaming_h:.1f}h",
                  f"Other Screen\n{other_sc:.1f}h", f"Work/Study\n{work_h:.1f}h",
                  f"Sleep\n{sleep_h:.1f}h", f"Free Time\n{free_h:.1f}h"]
        colors = [CRIT, WARN, ACCENT, OK, ACCENT3, BORDER]

        fig, ax = plt.subplots(figsize=(7, 3.8))
        wedges, texts, autos = ax.pie(
            [max(0.01, s) for s in sizes],
            labels=labels, colors=colors,
            autopct="%1.0f%%", startangle=90,
            wedgeprops=dict(edgecolor=CARD, linewidth=2),
            textprops={"color": TXT2, "fontsize": 7},
            pctdistance=0.78)
        for at in autos:
            at.set_color(TXT); at.set_fontweight("bold"); at.set_fontsize(7)
        ax.add_artist(plt.Circle((0,0), 0.5, color=CARD))
        ax.text(0, 0, "24h", ha="center", va="center",
                color=TXT, fontsize=14, fontweight="bold")
        plt.tight_layout()
        chart_card(inner, fig, "How You Spend Your 24 Hours", full=True)
    def _pg_analysis(self):
        """Detailed analysis with chart and metric-by-metric breakdown."""
        row  = self.row
        df   = self.df
        sc   = float(row["daily_screen_time_hours"])
        so   = float(row["social_media_hours"])
        ga   = float(row["gaming_hours"])
        sl   = float(row["sleep_hours"])
        wo   = float(row["work_study_hours"])
        inner = self._sf()
        page_title(inner, "Your Detailed Analysis",
                   "See how your habits compare to healthy limits and other users")
        # Chart: you vs limits
        metrics = ["Screen","Social","Gaming","Sleep","Work"]
        uvals   = [sc, so, ga, sl, wo]
        lvals   = [6.0, 2.0, 1.5, 7.0, 4.0]
        # For sleep and work — higher is better. For others — lower is better.
        bclrs   = [
            CRIT if sc > 6.0 else OK,   # screen — lower is better
            CRIT if so > 2.0 else OK,   # social — lower is better
            CRIT if ga > 1.5 else OK,   # gaming — lower is better
            CRIT if sl < 7.0 else OK,   # sleep  — higher is better
            INFO  if wo < 4.0 else OK,  # work   — higher is better (never red)
        ]
        fig, ax = plt.subplots(figsize=(9, 3.0))
        x = np.arange(len(metrics)); w = 0.38
        ax.bar(x-w/2, uvals, w, color=bclrs, label="Your usage", edgecolor="none")
        ax.bar(x+w/2, lvals, w, color=BORDER, label="Healthy limit",
               edgecolor="none", alpha=0.8)
        ax.set_xticks(x); ax.set_xticklabels(metrics)
        ax.set_ylabel("Hours", fontsize=8)
        for i,(uv,cl) in enumerate(zip(uvals,bclrs)):
            ax.text(i-w/2, uv+0.05, f"{uv:.1f}", ha="center",
                    color=cl, fontsize=8, fontweight="bold")
        ax.legend(fontsize=8, facecolor=CARD, edgecolor=BORDER, labelcolor=TXT)
        plt.tight_layout()
        chart_card(inner, fig, "Your Usage vs Healthy Limits", full=True)
        # Metric-by-metric
        section_hdr(inner, "What Each Metric Means For You")
        for metric, value, limit, color, severity, message, action in analyze_user(row):
            analysis_card(inner, metric, value, limit, color, severity, message, action)
        # Percentile comparison
        section_hdr(inner, "How You Compare")
        cf = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        cf.pack(fill="x", padx=24, pady=(0,16))
        ci = tk.Frame(cf, bg=CARD); ci.pack(fill="x", padx=16, pady=14)
        for metric, val, col_name, better_low in [
            ("Screen Time",     sc, "daily_screen_time_hours", True),
            ("Sleep",           sl, "sleep_hours",             False),
            ("Social Media",    so, "social_media_hours",      True),
            ("Wellbeing Score", int(row["score"]), "score",    False),
        ]:
            pct = float((df[col_name]<=val).mean()*100)
            status = (f"Lower than {100-pct:.0f}% of users" if better_low
                      else f"Higher than {pct:.0f}% of users")
            clr = OK if (pct<=50 and better_low) or (pct>=60 and not better_low) else WARN if (pct<=75 and better_low) or (pct>=40 and not better_low) else CRIT
            rf = tk.Frame(ci, bg=CARD); rf.pack(fill="x", pady=5)
            tk.Label(rf, text=metric, bg=CARD, fg=TXT2,
                     font=("Segoe UI",9), width=16, anchor="w").pack(side="left")
            tk.Label(rf, text=f"{val:.1f}  ",
                     bg=CARD, fg=TXT, font=("Segoe UI",9,"bold"), width=7).pack(side="left")
            bg3 = tk.Frame(rf, bg=BORDER, height=6, width=180); bg3.pack(side="left", padx=(8,10))
            tk.Frame(bg3, bg=clr, height=6, width=int(pct*1.8)).place(x=0,y=0)
            tk.Label(rf, text=status, bg=CARD, fg=clr,
                     font=("Segoe UI",8)).pack(side="left")
    def _pg_plan(self):
        """Simple action plan — what to do to improve."""
        row = self.row
        sc  = float(row["daily_screen_time_hours"])
        so  = float(row["social_media_hours"])
        sl  = float(row["sleep_hours"])
        no  = float(row["notifications_per_day"])
        wb  = int(row["score"])
        inner = self._sf()
        page_title(inner, "Your Action Plan",
                   f"Follow these steps to improve your score from {wb} to {min(100, wb+20)}")
        # Score projection chips
        pf = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        pf.pack(fill="x", padx=24, pady=(0,14))
        tk.Frame(pf, bg=ACCENT, height=2).pack(fill="x")
        pi = tk.Frame(pf, bg=CARD); pi.pack(fill="x", padx=16, pady=14)
        tk.Label(pi, text="Your score could reach:",
                 bg=CARD, fg=TXT2, font=("Segoe UI",9)).pack(anchor="w", pady=(0,10))
        pg = tk.Frame(pi, bg=CARD); pg.pack(fill="x")
        if wb >= 90:
            tk.Label(pg,
                     text=f"✅  Your score is already {wb}/100 — excellent! Maintain these habits.",
                     bg=CARD, fg=OK, font=("Segoe UI",11,"bold")).pack(anchor="w")
        else:
            for label, score, note in [
                ("Now",     wb,                   "current"),
                ("7 days",  min(100, wb+8),  "fix sleep & screen"),
                ("30 days", min(100, wb+16), "consistent habits"),
                ("90 days", min(100, wb+25), "lifestyle change"),
            ]:
                clr = get_status_color(score)
                chip = tk.Frame(pg, bg=CARD2, padx=16, pady=10)
                chip.pack(side="left", padx=(0,12))
                tk.Label(chip, text=label, bg=CARD2, fg=TXT3, font=("Segoe UI",8)).pack()
                tk.Label(chip, text=str(score), bg=CARD2, fg=clr,
                         font=("Segoe UI",18,"bold")).pack()
                tk.Label(chip, text=note, bg=CARD2, fg=TXT3,
                         font=("Segoe UI",7), wraplength=100).pack()
        # Actions
        section_hdr(inner, "Steps to Take — Starting Today")
        actions = []
        if sc > 6:
            pts = min(30, round((sc-6)*6))
            actions.append((pts, "📱", "Reduce Screen Time",
                f"You use {sc:.1f}h/day. Reduce to 6h. This adds +{pts} points.",
                ["Open phone Settings → Screen Time or Digital Wellbeing",
                 "Set a daily 6-hour screen time limit",
                 "Enable Downtime from 10pm to 7am"]))
        if sl < 7:
            pts = min(25, round((7-sl)*8))
            actions.append((pts, "😴", "Get More Sleep",
                f"You sleep {sl:.1f}h/night. Aim for 7h. This adds +{pts} points.",
                ["Set a 10:30pm bedtime alarm on your phone tonight",
                 "Stop using screens 1 hour before bed",
                 "Charge your phone outside the bedroom"]))
        if so > 2:
            pts = min(20, round((so-2)*5))
            actions.append((pts, "📲", "Cut Social Media",
                f"You use {so:.1f}h/day. Limit to 2h. This adds +{pts} points.",
                ["Set a 2-hour daily timer for all social apps",
                 "Turn off all social media notifications",
                 "Only check social media at 12pm and 6pm"]))
        if no > 50:
            pts = min(15, round((no-50)*0.1))
            actions.append((pts, "🔔", "Fewer Notifications",
                f"You get {int(no)}/day. Target 50. This adds +{pts} points.",
                ["Go to Settings → Notifications",
                 "Turn off all except calls and essential messages",
                 "Use Do Not Disturb during work and sleep"]))
        if not actions:
            card = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=OK)
            card.pack(fill="x", padx=24, pady=5)
            tk.Frame(card, bg=OK, height=2).pack(fill="x")
            tk.Label(card, text="  ✅  You are already within healthy limits on all metrics!",
                     bg=CARD, fg=OK, font=("Segoe UI",11,"bold")).pack(anchor="w", padx=16, pady=14)
        else:
            actions.sort(key=lambda x: x[0], reverse=True)
            for rank, (pts, icon, title, summary, steps) in enumerate(actions, 1):
                af = tk.Frame(inner, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
                af.pack(fill="x", padx=24, pady=5)
                tk.Frame(af, bg=ACCENT, height=2).pack(fill="x")
                ai = tk.Frame(af, bg=CARD); ai.pack(fill="x", padx=16, pady=12)
                hr = tk.Frame(ai, bg=CARD); hr.pack(fill="x", pady=(0,6))
                rb = tk.Frame(hr, bg=CARD2, padx=8, pady=3); rb.pack(side="left", padx=(0,10))
                tk.Label(rb, text=f"#{rank}", bg=CARD2, fg=ACCENT3,
                         font=("Segoe UI",8,"bold")).pack()
                tk.Label(hr, text=f"{icon}  {title}",
                         bg=CARD, fg=TXT, font=("Segoe UI",11,"bold")).pack(side="left")
                ib = tk.Frame(hr, bg=CARD2, padx=10, pady=3); ib.pack(side="right")
                tk.Label(ib, text=f"+{pts} pts", bg=CARD2, fg=OK,
                         font=("Segoe UI",9,"bold")).pack()
                tk.Label(ai, text=summary, bg=CARD, fg=TXT2,
                         font=("Segoe UI",9)).pack(anchor="w", pady=(0,8))
                tk.Frame(ai, bg=SEP, height=1).pack(fill="x", pady=(0,8))
                for j, step in enumerate(steps, 1):
                    sf3 = tk.Frame(ai, bg=CARD); sf3.pack(fill="x", pady=2)
                    tk.Label(sf3, text=f"  {j}.", bg=CARD, fg=ACCENT3,
                             font=("Segoe UI",9,"bold"), width=3).pack(side="left")
                    tk.Label(sf3, text=step, bg=CARD, fg=TXT2,
                             font=("Segoe UI",9)).pack(side="left", padx=4)

# ── Entry ──────────────────────────────────────────────────────
if __name__ == "__main__":
    Login().mainloop()
