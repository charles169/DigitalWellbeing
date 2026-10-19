# 📱 Digital Wellbeing Analytics

A professional desktop application for tracking and analyzing digital wellbeing habits across individuals and populations. Built with Python and Tkinter, it connects to a MySQL database and delivers rich analytics, personalized insights, and actionable recommendations based on WHO-aligned healthy usage standards.

---

## 🖥️ Screenshots

> Admin Dashboard — Population Overview with risk distribution and score analytics  
> User Dashboard — Personal wellbeing score, metric cards, and daily insights  
> User Analysis — Per-metric breakdown with severity badges and action steps  
> Action Plan — Prioritized steps to improve your wellbeing score

---

## ✨ Features

### 🔐 Login System
- Secure role-based login — **Admin** and **User** modes
- Admin account unlocks the full population dashboard
- Regular users log in with their unique User ID to access personal data
- Animated left panel with floating dots and fade-in transition

### 📊 Admin Dashboard (4 tabs)

**Overview**
- Population KPIs: total users, high risk count, healthy count, average screen time, average score
- Risk distribution bar chart (Healthy / Moderate / High Risk)
- Wellbeing score histogram with average line and threshold markers
- Key population insights: percentage exceeding screen limits, sleep deficit, notification overload, best-performing age group

**User Lookup**
- Search any user by ID or pick from a random sample dropdown
- Opens a complete personal wellbeing report inside the admin view

**All Users**
- Full scrollable/sortable table of all 7,505 users
- Filter by risk level (High Risk / Moderate / Healthy) and gender
- Live search across all fields
- Double-click any row to open a detailed individual report in a popup
- Export filtered results to CSV

**Compare**
- Side-by-side comparison of two users across all key metrics
- Or compare age groups (18–24, 25–34, 35–44, 45+) with bar charts
- Winner highlighted per metric based on healthy thresholds

### 👤 User Dashboard (3 tabs)

**Dashboard**
- Personalized greeting with today's date
- Wellbeing score (0–100) with grade (A+ to F) and risk label
- Progress bar showing percentile rank vs all users
- Color-coded daily metric cards: Screen Time, Social Media, Gaming, Sleep, Notifications, Work/Study
- 3 key personal insights with context and comparisons

**My Analysis**
- Detailed per-metric analysis cards with:
  - Severity badge (HEALTHY / WARNING / CRITICAL)
  - Color-coded left stripe
  - Current value vs healthy limit
  - Explanation of impact on health
  - Specific action step to improve
- Metrics covered: Screen Time, Sleep, Social Media, Notifications, Gaming, Work/Study
- Percentile ranking for each metric vs the full user population

**Action Plan**
- Prioritized list of improvement actions ranked by score impact
- Each action shows: points to gain, current vs target value, step-by-step instructions
- Today's 6 daily goals with contextual tips
- 30-day trend charts (if daily log data exists): screen time, sleep, and social media over time

---

## 🧮 Wellbeing Score Algorithm

Each user gets a score from **0 to 100** calculated from 6 metrics:

| Metric | Healthy Limit | Max Penalty |
|--------|--------------|-------------|
| Screen Time | ≤ 6h/day | −30 pts |
| Sleep | ≥ 7h/night | −25 pts |
| Social Media | ≤ 2h/day | −20 pts |
| Notifications | ≤ 50/day | −15 pts |
| Gaming | ≤ 1.5h/day | −10 pts |
| Work/Study | ≥ 1h/day | −5 pts |

**Grade scale:**

| Score | Grade | Label |
|-------|-------|-------|
| 90–100 | A+ | Excellent |
| 80–89 | A | Very Good |
| 70–79 | B+ | Good |
| 60–69 | B | Fair |
| 50–59 | C | Average |
| 40–49 | D | Poor |
| 0–39 | F | Critical |

---

## 🗄️ Database Schema

The app uses a MySQL database (`digital_wellbeing`) with 3 tables:

**`wellbeing_data`** — Core user metrics  
- `user_id`, `age`, `gender`, `daily_screen_time_hours`, `social_media_hours`, `gaming_hours`, `work_study_hours`, `sleep_hours`, `notifications_per_day`

**`users`** — User profile info  
- `user_id`, `name`, `city`, `occupation`

**`daily_log`** — 30-day daily history per user  
- `user_id`, `log_date`, `screen_time_hours`, `social_media_hours`, `gaming_hours`, `work_study_hours`, `sleep_hours`, `notifications_per_day`, `mood`

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| GUI Framework | Python Tkinter + ttk |
| Charts | Matplotlib (TkAgg backend) |
| Data Processing | Pandas, NumPy |
| Database | MySQL via PyMySQL |
| Config | python-dotenv |
| Python Version | 3.10+ |

---

## ⚙️ Setup

### 1. Clone the repo
```bash
git clone https://github.com/charles169/Digital-Wellbeing-Analytics.git
cd Digital-Wellbeing-Analytics
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Set up MySQL
- Create a database named `digital_wellbeing`
- Import your schema and data

### 4. Configure environment
Copy `.env.example` to `.env` and fill in your credentials:
```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password_here
DB_NAME=digital_wellbeing
```

### 5. Run
```bash
python app.py
```

---

## 🔑 Login Credentials

| Role | User ID | Password |
|------|---------|----------|
| Admin | `admin` | `admin123` |
| User | e.g. `U009` | `wellbeing` |

---

## 📁 Project Structure

```
DigitalWellbeing/
├── app.py              # Main application (all UI, logic, DB queries)
├── requirements.txt    # Python dependencies
├── .env                # Your DB credentials (not committed)
├── .env.example        # Credentials template
├── .gitignore
└── README.md
```

---

## 📌 Notes

- If MySQL is unavailable, the app falls back to `wellbeing_data.csv` (if present)
- Charts can be saved as PNG or PDF using the ↓ Save button on each chart
- The All Users table supports live filtering and CSV export
- User IDs in the database follow the format `U001`, `U002`, etc.
