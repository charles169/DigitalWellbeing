# Digital Wellbeing Analytics

A professional desktop application for individual digital wellbeing tracking and insights, built with Python and Tkinter.

## Features
- Admin dashboard with population-level analytics
- Individual user wellbeing scoring and analysis
- Screen time, sleep, social media, and notification tracking
- Personalized recommendations based on WHO standards
- Dark themed UI with charts and visualizations

## Setup

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Configure database
Copy `.env.example` to `.env` and fill in your MySQL credentials:
```
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password_here
DB_NAME=digital_wellbeing
```

### 3. Run
```
python app.py
```

## Login
- **Admin:** `admin` / `admin123`
- **User:** `<user_id>` / `wellbeing`
