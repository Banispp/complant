# Complaint Management System

A role-based institutional Complaint Management System built with Django.

## Features
- **Multi-Role Access Control**: Students, Class Mentors, Heads of Department (HOD), Principals, and Administrators.
- **Complaint Lifecycle Management**: Submit, track, escalate, resolve, and close complaints.
- **Role Dashboards & Filtering**: Tailored views and metrics for each role.
- **Category & Class Management**: Academic classes and complaint categorization.
- **Demo Seeding Command**: Easily initialize demo data via `python manage.py seed_demo`.

## Tech Stack
- **Framework**: Django 4.2+
- **Database**: SQLite (default)
- **Frontend**: Bootstrap 5, Custom CSS & JavaScript

## Getting Started

### 1. Setup Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run Migrations
```bash
python manage.py migrate
```

### 4. Seed Demo Data (Optional)
```bash
python manage.py seed_demo
```

### 5. Start Development Server
```bash
python manage.py runserver
```
