#  STANDARD LIBRARY IMPORTS

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import csv
import re
import calendar
from datetime import date, datetime


#  CONSTANTS

FONT = "Segoe UI"          # gracefully degrades on Linux/macOS

MONTHS = [
    "", "January", "February", "March", "April",
    "May", "June", "July", "August", "September",
    "October", "November", "December",
]

DEPARTMENTS = [
    "Computer Science & Engineering",
    "Computer & Communication Engineering",
    "Electrical & Electronic Engineering",
    "Mechanical Engineering",
    "Civil Engineering",
    "Business Administration",
    "English",
    "Other",
]

NAV_ITEMS = [
    ("Dashboard",  "🏠", "dashboard"),
    ("Students",   "👥", "students"),
    ("Attendance", "✅", "attendance"),
    ("Records",    "📋", "records"),
    ("History",    "📅", "history"),
    ("Export",     "📊", "export"),
]

#  Dual colour palette
THEMES = {
    "dark": {
        "bg":        "#1a1d2e",
        "sidebar":   "#1e2140",
        "card":      "#252842",
        "card2":     "#2d3158",
        "accent":    "#6c63ff",
        "accent2":   "#ff6584",
        "success":   "#43b89c",
        "warning":   "#f5a623",
        "info":      "#38bdf8",
        "text":      "#e8e8f0",
        "subtext":   "#9b9ec8",
        "border":    "#3a3f6b",
        "entry_bg":  "#2d3158",
        "select":    "#3d4480",
        "tree_bg":   "#1e2140",
        "tree_alt":  "#252842",
        "status_bg": "#141627",
        "cal_head":  "#3d4480",
        "cal_today": "#6c63ff",
        "cal_p":     "#1e4a3a",
        "cal_a":     "#4a1e2a",
        "cal_empty": "#1e2140",
    },
    "light": {
        "bg":        "#f0f2f8",
        "sidebar":   "#ffffff",
        "card":      "#ffffff",
        "card2":     "#e8eaf6",
        "accent":    "#5c54e0",
        "accent2":   "#e8416a",
        "success":   "#2ba88d",
        "warning":   "#e5962b",
        "info":      "#0284c7",
        "text":      "#1a1d2e",
        "subtext":   "#6b7280",
        "border":    "#d1d5e8",
        "entry_bg":  "#f8f9ff",
        "select":    "#c7caff",
        "tree_bg":   "#ffffff",
        "tree_alt":  "#f5f6ff",
        "status_bg": "#e2e5f0",
        "cal_head":  "#e8eaf6",
        "cal_today": "#5c54e0",
        "cal_p":     "#d1fae5",
        "cal_a":     "#fee2e2",
        "cal_empty": "#f5f6ff",
    },
}


#  VALIDATION HELPERS

def validate_student_code(code: str) -> tuple[bool, str]:
    """
    Student code must:
      - Be 3–20 characters
      - Contain at least one letter (A-Z / a-z)
      - Contain at least one digit (0-9)
      - Only use letters, digits, or hyphens
    Examples: CCE001  CSE2024  EEE-042  CE2024050
    """
    code = code.strip().upper()
    if not code:
        return False, "Student ID is required."
    if len(code) < 3 or len(code) > 20:
        return False, "Student ID must be 3–20 characters."
    if not re.match(r'^[A-Z][A-Z0-9\-]{2,19}$', code):
        return False, "Student ID: start with a letter; use letters, digits, hyphens only."
    if not re.search(r'[0-9]', code):
        return False, "Student ID must contain at least one digit (e.g. CCE001)."
    return True, code   # returns normalised UPPERCASE code


def validate_contact(contact: str) -> tuple[bool, str]:
    """
    Contact is optional. If provided it must be 7–15 digits,
    optionally prefixed with + and country code.
    """
    contact = contact.strip()
    if not contact:
        return True, ""   # optional — empty is fine
    cleaned = re.sub(r'[\s\-\(\)]', '', contact)
    if not re.match(r'^\+?[0-9]{7,15}$', cleaned):
        return False, "Contact must be 7–15 digits (e.g. 01712345678 or +8801712345678)."
    return True, cleaned


def is_valid_date_str(s: str) -> bool:
    """Return True if s is a valid YYYY-MM-DD date string."""
    try:
        datetime.strptime(s.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


#  DATABASE MANAGER

class DatabaseManager:
    """
    Single class for ALL SQLite operations.
    Uses connection-level row_factory so rows behave like dicts.
    """

    def __init__(self, db_path: str = "attendance.db"):
        self.db_path = db_path
        self.conn    = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_tables()
        self._migrate()          # safely upgrades any existing v1 database

    #  Schema 
    def _create_tables(self):
        """Create tables for a fresh database. Existing tables are left untouched."""
        with self.conn:
            # Students table — student_code is the human-visible alphanumeric ID
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS students (
                    student_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_code TEXT    NOT NULL UNIQUE,
                    name         TEXT    NOT NULL,
                    department   TEXT    NOT NULL,
                    contact      TEXT    DEFAULT ''
                )
            """)
            # Attendance table — one row per (student, date)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS attendance (
                    attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id    INTEGER NOT NULL,
                    date          TEXT    NOT NULL,
                    status        TEXT    NOT NULL
                                  CHECK(status IN ('Present','Absent')),
                    FOREIGN KEY (student_id) REFERENCES students(student_id)
                                             ON DELETE CASCADE,
                    UNIQUE(student_id, date)
                )
            """)

    def _migrate(self):
        existing_cols = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info(students)").fetchall()
        }

        # Nothing to do if the schema is already current
        if "student_code" in existing_cols and "contact" in existing_cols:
            return

        with self.conn:
            #  Step 1: rename the old table 
            self.conn.execute(
                "ALTER TABLE students RENAME TO students_old"
            )

            #  Step 2: create the new table (full v2 schema) 
            self.conn.execute("""
                CREATE TABLE students (
                    student_id   INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_code TEXT    NOT NULL UNIQUE,
                    name         TEXT    NOT NULL,
                    department   TEXT    NOT NULL,
                    contact      TEXT    DEFAULT ''
                )
            """)

            #  Step 3: copy existing rows 
            # Determine which columns the old table actually has
            old_cols = {
                row[1]
                for row in self.conn.execute(
                    "PRAGMA table_info(students_old)"
                ).fetchall()
            }

            old_rows = self.conn.execute(
                "SELECT * FROM students_old ORDER BY student_id"
            ).fetchall()

            for row in old_rows:
                sid  = row["student_id"]
                name = row["name"]
                dept = row["department"]

                # Carry over contact if it existed in the old table
                contact = row["contact"] if "contact" in old_cols else ""

                # Auto-generate a student_code for migrated rows (STU0001, STU0002 …)
                # Users can edit these afterwards in the Students page.
                if "student_code" in old_cols and row["student_code"]:
                    code = row["student_code"]
                else:
                    code = f"STU{sid:04d}"

                self.conn.execute(
                    """INSERT INTO students
                           (student_id, student_code, name, department, contact)
                       VALUES (?, ?, ?, ?, ?)""",
                    (sid, code, name, dept, contact)
                )

            #  Step 4: drop the old table 
            self.conn.execute("DROP TABLE students_old")

    #  Student CRUD 
    def add_student(self, code: str, name: str,
                    dept: str, contact: str = "") -> tuple[bool, str]:
        try:
            with self.conn:
                self.conn.execute(
                    """INSERT INTO students (student_code, name, department, contact)
                       VALUES (?, ?, ?, ?)""",
                    (code, name.strip(), dept.strip(), contact.strip())
                )
            return True, "Student added successfully."
        except sqlite3.IntegrityError:
            return False, f"Student ID '{code}' already exists."
        except sqlite3.Error as e:
            return False, str(e)

    def get_all_students(self, search: str = "") -> list:
        """Return students with their overall attendance percentage."""
        pattern = f"%{search}%"
        return self.conn.execute("""
            SELECT s.student_id, s.student_code, s.name, s.department, s.contact,
                   COUNT(a.attendance_id)  AS total_days,
                   SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS present_days,
                   ROUND(100.0 *
                       SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)
                       / MAX(COUNT(a.attendance_id), 1), 1) AS pct
            FROM students s
            LEFT JOIN attendance a USING(student_id)
            WHERE s.student_code LIKE ?
               OR s.name         LIKE ?
               OR s.department   LIKE ?
            GROUP BY s.student_id
            ORDER BY s.student_code
        """, (pattern, pattern, pattern)).fetchall()

    def get_student_by_id(self, student_id: int):
        return self.conn.execute(
            "SELECT * FROM students WHERE student_id=?", (student_id,)
        ).fetchone()

    def update_student(self, student_id: int, code: str, name: str,
                       dept: str, contact: str) -> tuple[bool, str]:
        try:
            with self.conn:
                self.conn.execute(
                    """UPDATE students
                       SET student_code=?, name=?, department=?, contact=?
                       WHERE student_id=?""",
                    (code, name.strip(), dept.strip(), contact.strip(), student_id)
                )
            return True, "Student updated."
        except sqlite3.IntegrityError:
            return False, f"Student ID '{code}' already exists."
        except sqlite3.Error as e:
            return False, str(e)

    def delete_student(self, student_id: int) -> bool:
        try:
            with self.conn:
                # CASCADE handles attendance rows
                self.conn.execute(
                    "DELETE FROM students WHERE student_id=?", (student_id,)
                )
            return True
        except sqlite3.Error:
            return False

    #  Attendance 
    def mark_attendance(self, student_id: int, status: str,
                        att_date: str = None) -> bool:
        """Insert or replace attendance for (student, date)."""
        if att_date is None:
            att_date = date.today().isoformat()
        try:
            with self.conn:
                self.conn.execute("""
                    INSERT INTO attendance (student_id, date, status) VALUES (?,?,?)
                    ON CONFLICT(student_id, date) DO UPDATE SET status=excluded.status
                """, (student_id, att_date, status))
            return True
        except sqlite3.Error:
            return False

    def get_attendance_for_date(self, att_date: str) -> list:
        """All students with their status (or NULL) for a given date."""
        return self.conn.execute("""
            SELECT s.student_id, s.student_code, s.name, s.department, s.contact,
                   COALESCE(a.status, '') AS status,
                   a.attendance_id
            FROM students s
            LEFT JOIN attendance a
                   ON s.student_id = a.student_id AND a.date = ?
            ORDER BY s.student_code
        """, (att_date,)).fetchall()

    def get_status_map_for_date(self, att_date: str) -> dict:
        """Returns {student_id: status} for the given date."""
        rows = self.conn.execute(
            "SELECT student_id, status FROM attendance WHERE date=?", (att_date,)
        ).fetchall()
        return {r["student_id"]: r["status"] for r in rows}

    #  Filtered records (year / month / day / name)
    def get_records(self, year: str = "", month: str = "",
                    day: str = "", name: str = "") -> list:
        """
        Flexible attendance history query.
        All filter params are optional strings.
        """
        conds  = []
        params = []

        if year:
            conds.append("strftime('%Y', a.date) = ?")
            params.append(year.zfill(4))
        if month:
            conds.append("strftime('%m', a.date) = ?")
            params.append(month.zfill(2))
        if day:
            conds.append("strftime('%d', a.date) = ?")
            params.append(day.zfill(2))
        if name:
            conds.append("(s.name LIKE ? OR s.student_code LIKE ?)")
            params += [f"%{name}%", f"%{name}%"]

        where = ("WHERE " + " AND ".join(conds)) if conds else ""

        return self.conn.execute(f"""
            SELECT a.attendance_id,
                   s.student_code, s.name, s.department, s.contact,
                   a.date, a.status,
                   strftime('%Y', a.date) AS yr,
                   strftime('%m', a.date) AS mo,
                   strftime('%d', a.date) AS dy
            FROM attendance a
            JOIN students s USING(student_id)
            {where}
            ORDER BY a.date DESC, s.student_code
        """, params).fetchall()

    def update_attendance_status(self, attendance_id: int, status: str) -> bool:
        """Edit an existing attendance record."""
        try:
            with self.conn:
                self.conn.execute(
                    "UPDATE attendance SET status=? WHERE attendance_id=?",
                    (status, attendance_id)
                )
            return True
        except sqlite3.Error:
            return False

    def delete_attendance(self, attendance_id: int) -> bool:
        try:
            with self.conn:
                self.conn.execute(
                    "DELETE FROM attendance WHERE attendance_id=?", (attendance_id,)
                )
            return True
        except sqlite3.Error:
            return False

    #  Year / Month selectors (for dropdowns) 
    def get_available_years(self) -> list:
        rows = self.conn.execute(
            "SELECT DISTINCT strftime('%Y', date) AS yr "
            "FROM attendance ORDER BY yr DESC"
        ).fetchall()
        years = [r["yr"] for r in rows if r["yr"]]
        cur_y = str(date.today().year)
        if cur_y not in years:
            years.insert(0, cur_y)
        return years

    def get_available_months_in_year(self, year: str) -> list:
        rows = self.conn.execute(
            "SELECT DISTINCT strftime('%m', date) AS mo "
            "FROM attendance WHERE strftime('%Y',date)=? ORDER BY mo",
            (year,)
        ).fetchall()
        return [r["mo"] for r in rows]

    #  Dashboard stats 
    def get_dashboard_stats(self) -> dict:
        today = date.today().isoformat()
        total = self.conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        present = self.conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE date=? AND status='Present'",
            (today,)
        ).fetchone()[0]
        absent = self.conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE date=? AND status='Absent'",
            (today,)
        ).fetchone()[0]

        # This month's overall rate
        ym = date.today().strftime("%Y-%m")
        month_total = self.conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE date LIKE ?", (f"{ym}%",)
        ).fetchone()[0]
        month_present = self.conn.execute(
            "SELECT COUNT(*) FROM attendance WHERE date LIKE ? AND status='Present'",
            (f"{ym}%",)
        ).fetchone()[0]
        month_pct = round(100 * month_present / month_total, 1) if month_total else 0

        return {
            "total":      total,
            "present":    present,
            "absent":     absent,
            "not_marked": total - present - absent,
            "month_pct":  month_pct,
        }

    def get_recent_activity(self, limit: int = 10) -> list:
        return self.conn.execute("""
            SELECT s.student_code, s.name, s.department, a.date, a.status
            FROM attendance a JOIN students s USING(student_id)
            ORDER BY a.attendance_id DESC LIMIT ?
        """, (limit,)).fetchall()

    #  Calendar / monthly data 
    def get_monthly_summary(self, year: int, month: int) -> dict:
        """
        Returns {day_str: {"present": n, "absent": n}} for every
        day that has records in the given year-month.
        """
        ym = f"{year:04d}-{month:02d}"
        rows = self.conn.execute("""
            SELECT date,
                   SUM(CASE WHEN status='Present' THEN 1 ELSE 0 END) AS p,
                   SUM(CASE WHEN status='Absent'  THEN 1 ELSE 0 END) AS a
            FROM attendance
            WHERE date LIKE ?
            GROUP BY date
        """, (f"{ym}%",)).fetchall()
        return {r["date"]: {"present": r["p"], "absent": r["a"]} for r in rows}

    def close(self):
        self.conn.close()


#  TTK STYLE BUILDER

def apply_theme(style: ttk.Style, T: dict):
    """Configure all ttk widget styles for the active theme dict T."""
    style.theme_use("clam")

    style.configure("TFrame",     background=T["bg"])
    style.configure("TLabel",     background=T["bg"],    foreground=T["text"],
                    font=(FONT, 10))
    style.configure("Sidebar.TFrame",  background=T["sidebar"])
    style.configure("Card.TFrame",     background=T["card"])

    # Buttons
    for name, bg in [("Accent",  T["accent"]),
                     ("Danger",  T["accent2"]),
                     ("Success", T["success"]),
                     ("Warning", T["warning"]),
                     ("Info",    T["info"])]:
        style.configure(f"{name}.TButton",
                        background=bg, foreground="#ffffff",
                        font=(FONT, 10, "bold"),
                        borderwidth=0, focusthickness=0, padding=(12, 6))
        style.map(f"{name}.TButton",
                  background=[("active", bg), ("pressed", bg)])

    style.configure("Ghost.TButton",
                    background=T["card2"], foreground=T["text"],
                    font=(FONT, 10),
                    borderwidth=0, focusthickness=0, padding=(10, 5))
    style.map("Ghost.TButton",
              background=[("active", T["select"])])

    # Treeview
    style.configure("Treeview",
                    background=T["tree_bg"], foreground=T["text"],
                    fieldbackground=T["tree_bg"],
                    rowheight=28, font=(FONT, 9), borderwidth=0)
    style.configure("Treeview.Heading",
                    background=T["card2"], foreground=T["subtext"],
                    font=(FONT, 9, "bold"), borderwidth=0, relief="flat")
    style.map("Treeview",
              background=[("selected", T["select"])],
              foreground=[("selected", T["text"])])

    # Entry / Combobox
    style.configure("TEntry",
                    fieldbackground=T["entry_bg"], foreground=T["text"],
                    insertcolor=T["text"], borderwidth=1, font=(FONT, 10))
    style.configure("TCombobox",
                    fieldbackground=T["entry_bg"], foreground=T["text"],
                    background=T["entry_bg"], font=(FONT, 10))

    style.configure("TSeparator", background=T["border"])
    style.configure("TScrollbar",
                    background=T["card"], troughcolor=T["bg"],
                    borderwidth=0, arrowsize=12)


#  SMALL REUSABLE WIDGETS

class StatCard(tk.Frame):
    """Icon + big number + label — used on dashboard."""

    def __init__(self, parent, icon, label, value, color, T, **kw):
        super().__init__(parent, bg=T["card"],
                         highlightthickness=1,
                         highlightbackground=T["border"], **kw)
        tk.Label(self, text=icon, bg=color, fg="#fff",
                 font=(FONT, 16), padx=10, pady=10).pack(side="left")
        info = tk.Frame(self, bg=T["card"])
        info.pack(side="left", padx=10, pady=8)
        self._v = tk.StringVar(value=str(value))
        tk.Label(info, textvariable=self._v, bg=T["card"], fg=T["text"],
                 font=(FONT, 20, "bold")).pack(anchor="w")
        tk.Label(info, text=label, bg=T["card"], fg=T["subtext"],
                 font=(FONT, 9)).pack(anchor="w")

    def set(self, v):
        self._v.set(str(v))


def make_entry(parent, var, T, width=None, **kw):
    """Flat-style tk.Entry consistent with theme."""
    cfg = dict(textvariable=var,
               bg=T["entry_bg"], fg=T["text"],
               insertbackground=T["text"],
               relief="flat", bd=6, font=(FONT, 10))
    if width:
        cfg["width"] = width
    cfg.update(kw)
    return tk.Entry(parent, **cfg)


def make_combo(parent, var, values, T, width=18, state="readonly"):
    """ttk.Combobox styled with theme colours."""
    cb = ttk.Combobox(parent, textvariable=var, values=values,
                      state=state, font=(FONT, 10), width=width)
    return cb


def page_header(parent, title: str, T: dict) -> tk.Frame:
    """Standard page header with title + horizontal rule."""
    frm = tk.Frame(parent, bg=T["bg"])
    frm.pack(fill="x", padx=28, pady=(22, 0))
    tk.Label(frm, text=title, bg=T["bg"], fg=T["text"],
             font=(FONT, 19, "bold")).pack(side="left")
    ttk.Separator(parent).pack(fill="x", padx=28, pady=(6, 12))
    return frm


#  MODAL: ADD / EDIT STUDENT

class StudentDialog(tk.Toplevel):
    """
    Modal form for adding or editing a student.
    Fields: student_code (required, alphanumeric), name (required),
            department (required), contact (optional).
    """

    def __init__(self, parent, T: dict, db: DatabaseManager,
                 student=None, on_save=None):
        super().__init__(parent)
        self.T         = T
        self.db        = db
        self.student   = student     # None → add mode
        self.on_save   = on_save

        is_edit = student is not None
        self.title("Edit Student" if is_edit else "Add New Student")
        self.configure(bg=T["card"])
        self.resizable(False, False)
        self.grab_set()

        # ── Title ──
        tk.Label(self, text=("Edit Student" if is_edit else "Add New Student"),
                 bg=T["card"], fg=T["text"],
                 font=(FONT, 14, "bold")).pack(pady=(18, 8))

        body = tk.Frame(self, bg=T["card"])
        body.pack(padx=28, fill="x")

        # Field builder helper
        def field(label, var, is_combo=False, required=True):
            suffix = " *" if required else " (optional)"
            tk.Label(body, text=label + suffix,
                     bg=T["card"], fg=T["subtext"],
                     font=(FONT, 9)).pack(anchor="w", pady=(8, 1))
            if is_combo:
                w = make_combo(body, var, DEPARTMENTS, T, width=40, state="normal")
            else:
                w = make_entry(body, var, T)
            w.pack(fill="x", ipady=3)
            return w

        self._code_var  = tk.StringVar()
        self._name_var  = tk.StringVar()
        self._dept_var  = tk.StringVar()
        self._cont_var  = tk.StringVar()

        self._code_entry = field("Student ID  (e.g. CCE001)", self._code_var)
        self._name_entry = field("Full Name",   self._name_var)
        field("Department",  self._dept_var, is_combo=True)
        field("Contact Number", self._cont_var, required=False)

        # Hint label
        self._hint = tk.Label(body, text="",
                              bg=T["card"], fg=T["accent2"],
                              font=(FONT, 8), wraplength=340)
        self._hint.pack(anchor="w", pady=(4, 0))

        # Pre-fill for edit
        if is_edit:
            self._code_var.set(student["student_code"])
            self._name_var.set(student["name"])
            self._dept_var.set(student["department"])
            self._cont_var.set(student["contact"] or "")

        # ── Buttons ──
        btn_row = tk.Frame(self, bg=T["card"])
        btn_row.pack(fill="x", padx=28, pady=(14, 20))

        tk.Button(btn_row, text="Cancel",
                  bg=T["card2"], fg=T["text"], font=(FONT, 10),
                  relief="flat", padx=14, pady=6,
                  command=self.destroy).pack(side="left")

        tk.Button(btn_row, text="  💾 Save  ",
                  bg=T["accent"], fg="#fff",
                  font=(FONT, 10, "bold"),
                  relief="flat", padx=14, pady=6,
                  command=self._save).pack(side="right")

        # Centre on parent
        self.update_idletasks()
        w = self.winfo_width(); h = self.winfo_height()
        px = parent.winfo_x() + parent.winfo_width()  // 2 - w // 2
        py = parent.winfo_y() + parent.winfo_height() // 2 - h // 2
        self.geometry(f"+{px}+{py}")

    def _save(self):
        T = self.T
        raw_code = self._code_var.get()
        name     = self._name_var.get().strip()
        dept     = self._dept_var.get().strip()
        contact  = self._cont_var.get().strip()

        # Validate code 
        ok, result = validate_student_code(raw_code)
        if not ok:
            self._hint.config(text=result)
            return
        code = result   # normalised uppercase

        #  Validate name 
        if not name or len(name) < 2:
            self._hint.config(text="Name must be at least 2 characters.")
            return

        #  Validate dept 
        if not dept:
            self._hint.config(text="Please choose a department.")
            return

        #  Validate contact (optional) 
        ok2, contact = validate_contact(contact)
        if not ok2:
            self._hint.config(text=contact)   # contact holds error msg here
            return

        #  Save 
        if self.student:
            ok3, msg = self.db.update_student(
                self.student["student_id"], code, name, dept, contact)
        else:
            ok3, msg = self.db.add_student(code, name, dept, contact)

        if ok3:
            if self.on_save:
                self.on_save()
            self.destroy()
        else:
            self._hint.config(text=msg)


#  MODAL: EDIT SINGLE ATTENDANCE RECORD

class EditAttendanceDialog(tk.Toplevel):
    """Small modal to flip Present ↔ Absent for one record."""

    def __init__(self, parent, T, db, record, on_save):
        super().__init__(parent)
        self.T       = T
        self.db      = db
        self.record  = record
        self.on_save = on_save

        self.title("Edit Attendance")
        self.configure(bg=T["card"])
        self.resizable(False, False)
        self.grab_set()

        tk.Label(self, text="Edit Attendance Record",
                 bg=T["card"], fg=T["text"],
                 font=(FONT, 13, "bold")).pack(pady=(18, 4), padx=24)

        info = (f"Student : {record['student_code']}  —  {record['name']}\n"
                f"Date    : {record['date']}")
        tk.Label(self, text=info, bg=T["card"], fg=T["subtext"],
                 font=(FONT, 9), justify="left").pack(padx=24, pady=(0, 12))

        self._status_var = tk.StringVar(value=record["status"])

        row = tk.Frame(self, bg=T["card"])
        row.pack(padx=24, pady=4)
        for s, col in [("Present", T["success"]), ("Absent", T["accent2"])]:
            tk.Radiobutton(row, text=s, variable=self._status_var, value=s,
                           bg=T["card"], fg=col, activebackground=T["card"],
                           selectcolor=T["card"],
                           font=(FONT, 12, "bold")).pack(side="left", padx=16)

        btn_row = tk.Frame(self, bg=T["card"])
        btn_row.pack(fill="x", padx=24, pady=(14, 18))
        tk.Button(btn_row, text="Cancel", bg=T["card2"], fg=T["text"],
                  font=(FONT, 10), relief="flat", padx=12, pady=6,
                  command=self.destroy).pack(side="left")
        tk.Button(btn_row, text="Save", bg=T["accent"], fg="#fff",
                  font=(FONT, 10, "bold"), relief="flat", padx=12, pady=6,
                  command=self._save).pack(side="right")

        self.update_idletasks()
        w = self.winfo_width(); h = self.winfo_height()
        px = parent.winfo_x() + parent.winfo_width()  // 2 - w // 2
        py = parent.winfo_y() + parent.winfo_height() // 2 - h // 2
        self.geometry(f"+{px}+{py}")

    def _save(self):
        ok = self.db.update_attendance_status(
            self.record["attendance_id"], self._status_var.get())
        if ok:
            self.on_save()
            self.destroy()
        else:
            messagebox.showerror("Error", "Failed to update record.", parent=self)


#  FILTER TOOLBAR  (reusable — used in Records & History)

class FilterBar(tk.Frame):
    """
    Year / Month / Day + Name filter bar.
    Calls on_filter(year, month, day, name) whenever Search is clicked.
    Dropdowns are populated from the database.
    """

    def __init__(self, parent, T, db, on_filter, show_name=True, **kw):
        super().__init__(parent, bg=T["bg"], **kw)
        self.T         = T
        self.db        = db
        self.on_filter = on_filter

        self._year_var  = tk.StringVar(value="All")
        self._month_var = tk.StringVar(value="All")
        self._day_var   = tk.StringVar(value="")
        self._name_var  = tk.StringVar(value="")

        # Year
        tk.Label(self, text="Year:", bg=T["bg"], fg=T["subtext"],
                 font=(FONT, 9)).pack(side="left", padx=(0, 3))
        self._year_cb = make_combo(self, self._year_var, ["All"], T, width=7)
        self._year_cb.pack(side="left", padx=(0, 10))
        self._year_cb.bind("<<ComboboxSelected>>", self._year_changed)

        # Month
        tk.Label(self, text="Month:", bg=T["bg"], fg=T["subtext"],
                 font=(FONT, 9)).pack(side="left", padx=(0, 3))
        self._month_cb = make_combo(self, self._month_var, ["All"], T, width=11)
        self._month_cb.pack(side="left", padx=(0, 10))

        # Day
        tk.Label(self, text="Day:", bg=T["bg"], fg=T["subtext"],
                 font=(FONT, 9)).pack(side="left", padx=(0, 3))
        make_entry(self, self._day_var, T, width=4).pack(side="left", padx=(0, 10))

        # Name / Code search
        if show_name:
            tk.Label(self, text="Name/ID:", bg=T["bg"], fg=T["subtext"],
                     font=(FONT, 9)).pack(side="left", padx=(0, 3))
            make_entry(self, self._name_var, T, width=16).pack(
                side="left", padx=(0, 10))

        # Buttons
        tk.Button(self, text="🔍 Search",
                  bg=T["accent"], fg="#fff",
                  font=(FONT, 9, "bold"), relief="flat", padx=10, pady=4,
                  command=self._fire).pack(side="left", padx=(0, 6))

        tk.Button(self, text="↺ Clear",
                  bg=T["card2"], fg=T["text"],
                  font=(FONT, 9), relief="flat", padx=8, pady=4,
                  command=self._clear).pack(side="left")

        self.reload_years()

    def reload_years(self):
        years = ["All"] + self.db.get_available_years()
        self._year_cb["values"] = years
        self._year_var.set("All")
        self._month_cb["values"] = ["All"]
        self._month_var.set("All")

    def _year_changed(self, _event=None):
        yr = self._year_var.get()
        if yr == "All":
            self._month_cb["values"] = ["All"]
            self._month_var.set("All")
            return
        months = ["All"] + [
            f"{int(m):02d} – {MONTHS[int(m)]}"
            for m in self.db.get_available_months_in_year(yr)
        ]
        self._month_cb["values"] = months
        self._month_var.set("All")

    def _fire(self):
        yr   = self._year_var.get()
        mo   = self._month_var.get()
        day  = self._day_var.get().strip()
        name = self._name_var.get().strip()

        year_out  = "" if yr == "All"  else yr
        month_out = "" if mo == "All"  else mo[:2]   # "06 – June" → "06"
        day_out   = day.zfill(2) if day.isdigit() and 1 <= int(day) <= 31 else ""

        self.on_filter(year_out, month_out, day_out, name)

    def _clear(self):
        self._year_var.set("All")
        self._month_var.set("All")
        self._day_var.set("")
        self._name_var.set("")
        self._month_cb["values"] = ["All"]
        self.on_filter("", "", "", "")

    def set_date(self, year: str, month: str, day: str = ""):
        """Programmatically set filters (e.g. from calendar click)."""
        self._year_var.set(year)
        self._year_changed()
        mo_label = f"{int(month):02d} – {MONTHS[int(month)]}" if month else "All"
        if mo_label in self._month_cb["values"]:
            self._month_var.set(mo_label)
        self._day_var.set(day)
        self._fire()


#  PAGE: DASHBOARD

class DashboardPage(tk.Frame):
    def __init__(self, parent, T, db):
        super().__init__(parent, bg=T["bg"])
        self.T  = T
        self.db = db
        self._build()

    def _build(self):
        T  = self.T
        bg = T["bg"]

        hdr = page_header(self, "Dashboard", T)
        today_str = datetime.now().strftime("%A, %d %B %Y")
        tk.Label(hdr, text=today_str, bg=bg, fg=T["subtext"],
                 font=(FONT, 10)).pack(side="right", pady=4)

        # ── Stat cards ──
        grid = tk.Frame(self, bg=bg)
        grid.pack(fill="x", padx=28)
        grid.columnconfigure((0,1,2,3,4), weight=1, uniform="c")

        card_defs = [
            ("👥", "Total Students",   "total",      T["accent"]),
            ("✅", "Present Today",    "present",    T["success"]),
            ("❌", "Absent Today",     "absent",     T["accent2"]),
            ("⏳", "Not Marked Yet",  "not_marked", T["warning"]),
            ("📊", "This Month Rate",  "month_pct",  T["info"]),
        ]
        self._cards = {}
        for col, (icon, lbl, key, col_) in enumerate(card_defs):
            c = StatCard(grid, icon, lbl, "–", col_, T)
            c.grid(row=0, column=col, padx=5, pady=4, sticky="nsew", ipady=8)
            self._cards[key] = c

        #  Recent Activity 
        tk.Label(self, text="Recent Activity",
                 bg=bg, fg=T["text"],
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=28, pady=(18, 6))

        act_frame = tk.Frame(self, bg=T["card"],
                             highlightthickness=1,
                             highlightbackground=T["border"])
        act_frame.pack(fill="both", expand=True, padx=28, pady=(0, 18))

        cols = ("Code", "Name", "Department", "Date", "Status")
        self._tree = ttk.Treeview(act_frame, columns=cols,
                                  show="headings", height=9)
        ws = {"Code":80, "Name":180, "Department":200, "Date":100, "Status":80}
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=ws[c],
                              anchor="center" if c in ("Code","Date","Status") else "w")
        self._tree.pack(fill="both", expand=True, padx=1, pady=1)

        self.refresh()

    def refresh(self):
        T     = self.T
        stats = self.db.get_dashboard_stats()
        for key, card in self._cards.items():
            val = stats[key]
            card.set(f"{val}%" if key == "month_pct" else val)

        for r in self._tree.get_children():
            self._tree.delete(r)
        for i, rec in enumerate(self.db.get_recent_activity()):
            tag = "even" if i%2==0 else "odd"
            self._tree.insert("", "end",
                              values=(rec["student_code"], rec["name"],
                                      rec["department"], rec["date"], rec["status"]),
                              tags=(tag, rec["status"].lower()))
        self._tree.tag_configure("even",    background=T["tree_bg"])
        self._tree.tag_configure("odd",     background=T["tree_alt"])
        self._tree.tag_configure("present", foreground=T["success"])
        self._tree.tag_configure("absent",  foreground=T["accent2"])


#  PAGE: STUDENTS

class StudentsPage(tk.Frame):
    def __init__(self, parent, T, db):
        super().__init__(parent, bg=T["bg"])
        self.T  = T
        self.db = db
        self._build()

    def _build(self):
        T  = self.T
        bg = T["bg"]

        hdr = page_header(self, "Student Management", T)
        tk.Button(hdr, text="＋  Add Student",
                  bg=T["accent"], fg="#fff",
                  font=(FONT, 10, "bold"), relief="flat",
                  padx=14, pady=5,
                  command=self._add).pack(side="right")

        # ── Search ──
        search_row = tk.Frame(self, bg=bg)
        search_row.pack(fill="x", padx=28, pady=(0, 8))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self.refresh())
        make_entry(search_row, self._search_var, T).pack(
            side="left", fill="x", expand=True, ipady=5)
        tk.Label(search_row, text="  🔍 Search by ID / Name / Department",
                 bg=bg, fg=T["subtext"], font=(FONT, 9)).pack(side="left")

        # ── Treeview ──
        tf = tk.Frame(self, bg=T["card"],
                      highlightthickness=1, highlightbackground=T["border"])
        tf.pack(fill="both", expand=True, padx=28, pady=(0, 8))

        cols = ("Code", "Name", "Department", "Contact", "Attendance %")
        self._tree = ttk.Treeview(tf, columns=cols,
                                  show="headings", selectmode="browse")
        ws = {"Code":90, "Name":200, "Department":230,
              "Contact":130, "Attendance %":110}
        anchors = {"Code":"center","Attendance %":"center"}
        for c in cols:
            self._tree.heading(c, text=c,
                               command=lambda col=c: self._sort(col))
            self._tree.column(c, width=ws[c],
                              anchor=anchors.get(c, "w"))

        sb = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        #  Action buttons 
        btn_row = tk.Frame(self, bg=bg)
        btn_row.pack(fill="x", padx=28, pady=(0, 18))
        for txt, col_, cmd in [
            ("✏️ Edit",   T["warning"], self._edit),
            ("🗑️ Delete", T["accent2"], self._delete),
        ]:
            tk.Button(btn_row, text=txt, bg=col_, fg="#fff",
                      font=(FONT, 10, "bold"), relief="flat",
                      padx=14, pady=5, command=cmd).pack(side="left", padx=(0,8))

        self._count_var = tk.StringVar()
        tk.Label(btn_row, textvariable=self._count_var,
                 bg=bg, fg=T["subtext"], font=(FONT, 9)).pack(side="right")

        self._sort_col = None
        self._sort_rev = False
        self.refresh()

    def refresh(self, *_):
        T       = self.T
        search  = self._search_var.get().strip()
        rows    = self.db.get_all_students(search)

        for r in self._tree.get_children():
            self._tree.delete(r)
        for i, s in enumerate(rows):
            tag  = "even" if i%2==0 else "odd"
            pct  = f"{s['pct']}%" if s["pct"] is not None else "0%"
            cont = s["contact"] or "—"
            self._tree.insert("", "end",
                              iid=str(s["student_id"]),
                              values=(s["student_code"], s["name"],
                                      s["department"], cont, pct),
                              tags=(tag,))
        self._tree.tag_configure("even", background=T["tree_bg"])
        self._tree.tag_configure("odd",  background=T["tree_alt"])
        self._count_var.set(f"{len(rows)} student(s)")

    def _selected_id(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a student first.")
            return None
        return int(sel[0])

    def _add(self):
        StudentDialog(self.winfo_toplevel(), self.T, self.db,
                      on_save=self.refresh)

    def _edit(self):
        sid = self._selected_id()
        if sid is None: return
        student = self.db.get_student_by_id(sid)
        StudentDialog(self.winfo_toplevel(), self.T, self.db,
                      student=student, on_save=self.refresh)

    def _delete(self):
        sid = self._selected_id()
        if sid is None: return
        s   = self.db.get_student_by_id(sid)
        if messagebox.askyesno("Confirm Delete",
                               f"Delete '{s['name']} ({s['student_code']})' "
                               f"and ALL their attendance records?",
                               icon="warning"):
            if self.db.delete_student(sid):
                self.refresh()
            else:
                messagebox.showerror("Error", "Delete failed.")

    def _sort(self, col):
        rows = [(self._tree.set(k, col), k) for k in self._tree.get_children("")]
        self._sort_rev = (not self._sort_rev) if self._sort_col == col else False
        self._sort_col = col
        rows.sort(reverse=self._sort_rev,
                  key=lambda t: float(t[0].strip("%")) if "%" in t[0] else t[0].lower())
        for idx, (_, k) in enumerate(rows):
            self._tree.move(k, "", idx)


#  PAGE: ATTENDANCE  (mark any date, edit existing)

class AttendancePage(tk.Frame):
    """
    Mark / edit attendance for ANY date using Year/Month/Day
    dropdown selectors. Loads existing records automatically.
    """

    def __init__(self, parent, T, db):
        super().__init__(parent, bg=T["bg"])
        self.T     = T
        self.db    = db
        self._marks = {}   # student_id → tk.StringVar
        self._build()

    def _build(self):
        T  = self.T
        bg = T["bg"]

        page_header(self, "Mark Attendance", T)

        # ── Date selector row ──
        date_bar = tk.Frame(self, bg=T["card"],
                            highlightthickness=1,
                            highlightbackground=T["border"])
        date_bar.pack(fill="x", padx=28, pady=(0, 10))

        inner = tk.Frame(date_bar, bg=T["card"])
        inner.pack(padx=12, pady=10, anchor="w")

        tk.Label(inner, text="📅  Select Date:",
                 bg=T["card"], fg=T["subtext"],
                 font=(FONT, 10)).pack(side="left", padx=(0,10))

        today = date.today()

        # Year
        self._yr_var = tk.StringVar(value=str(today.year))
        yr_vals = [str(y) for y in range(today.year, today.year - 6, -1)]
        make_combo(inner, self._yr_var, yr_vals, T, width=6).pack(side="left")
        tk.Label(inner, text="Year", bg=T["card"], fg=T["subtext"],
                 font=(FONT, 8)).pack(side="left", padx=(2,10))

        # Month
        self._mo_var = tk.StringVar(value=str(today.month).zfill(2))
        mo_vals = [f"{m:02d} – {MONTHS[m]}" for m in range(1, 13)]
        self._mo_cb = make_combo(inner, self._mo_var, mo_vals, T, width=14)
        self._mo_cb.pack(side="left")
        self._mo_var.set(f"{today.month:02d} – {MONTHS[today.month]}")
        tk.Label(inner, text="Month", bg=T["card"], fg=T["subtext"],
                 font=(FONT, 8)).pack(side="left", padx=(2,10))

        # Day
        self._dy_var = tk.StringVar(value=str(today.day).zfill(2))
        day_vals = [f"{d:02d}" for d in range(1, 32)]
        make_combo(inner, self._dy_var, day_vals, T, width=4).pack(side="left")
        tk.Label(inner, text="Day", bg=T["card"], fg=T["subtext"],
                 font=(FONT, 8)).pack(side="left", padx=(2,12))

        tk.Button(inner, text="📂 Load",
                  bg=T["accent"], fg="#fff",
                  font=(FONT, 10, "bold"), relief="flat", padx=12, pady=4,
                  command=self._load).pack(side="left", padx=(0,6))

        tk.Button(inner, text="📅 Today",
                  bg=T["card2"], fg=T["text"],
                  font=(FONT, 10), relief="flat", padx=10, pady=4,
                  command=self._go_today).pack(side="left")

        self._date_label = tk.Label(inner, text="",
                                    bg=T["card"], fg=T["accent"],
                                    font=(FONT, 10, "bold"))
        self._date_label.pack(side="left", padx=14)

        # ── Quick action buttons ──
        qa = tk.Frame(self, bg=bg)
        qa.pack(fill="x", padx=28, pady=(0, 8))

        for txt, col_, val in [
            ("✅ All Present", T["success"], "Present"),
            ("❌ All Absent",  T["accent2"], "Absent"),
        ]:
            tk.Button(qa, text=txt, bg=col_, fg="#fff",
                      font=(FONT, 10, "bold"), relief="flat",
                      padx=12, pady=5,
                      command=lambda v=val: self._bulk(v)).pack(side="left", padx=(0,8))

        tk.Button(qa, text="↺ Reset All",
                  bg=T["card2"], fg=T["text"],
                  font=(FONT, 10), relief="flat", padx=10, pady=5,
                  command=self._reset_all).pack(side="left")

        self._summary_var = tk.StringVar(value="")
        tk.Label(qa, textvariable=self._summary_var,
                 bg=bg, fg=T["subtext"],
                 font=(FONT, 9)).pack(side="right")

        #  Scrollable student list 
        list_outer = tk.Frame(self, bg=T["card"],
                              highlightthickness=1,
                              highlightbackground=T["border"])
        list_outer.pack(fill="both", expand=True, padx=28, pady=(0, 8))

        self._canvas = tk.Canvas(list_outer, bg=T["card"], highlightthickness=0)
        vsb = ttk.Scrollbar(list_outer, orient="vertical",
                            command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=vsb.set)
        self._canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._inner = tk.Frame(self._canvas, bg=T["card"])
        self._cwin  = self._canvas.create_window((0,0),
                        window=self._inner, anchor="nw")

        self._inner.bind("<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")))
        self._canvas.bind("<Configure>",
            lambda e: self._canvas.itemconfig(self._cwin, width=e.width))
        self._canvas.bind_all("<MouseWheel>",
            lambda e: self._canvas.yview_scroll(
                -1 if e.delta > 0 else 1, "units"))

        #  Save bar 
        save_bar = tk.Frame(self, bg=bg)
        save_bar.pack(fill="x", padx=28, pady=(0, 18))

        tk.Button(save_bar, text="💾  Save Attendance",
                  bg=T["accent"], fg="#fff",
                  font=(FONT, 11, "bold"), relief="flat",
                  padx=18, pady=8,
                  command=self._save).pack(side="right")

        # Load today on startup
        self._load()

    def _get_selected_date(self) -> str | None:
        """Build YYYY-MM-DD from dropdowns, validate, return or None."""
        yr  = self._yr_var.get().strip()
        mo  = self._mo_var.get().strip()[:2]   # "06 – June" → "06"
        dy  = self._dy_var.get().strip()

        date_str = f"{yr}-{mo}-{dy}"
        if not is_valid_date_str(date_str):
            messagebox.showwarning("Invalid Date",
                                   f"'{date_str}' is not a valid date.")
            return None
        return date_str

    def _go_today(self):
        td = date.today()
        self._yr_var.set(str(td.year))
        self._mo_var.set(f"{td.month:02d} – {MONTHS[td.month]}")
        self._dy_var.set(f"{td.day:02d}")
        self._load()

    def _load(self):
        att_date = self._get_selected_date()
        if att_date is None:
            return

        T = self.T
        self._date_label.config(text=f"→ {att_date}")

        for w in self._inner.winfo_children():
            w.destroy()
        self._marks.clear()

        # Column header row
        hdr = tk.Frame(self._inner, bg=T["card2"])
        hdr.pack(fill="x")
        for txt, ww in [("#",30),("Code",90),("Name",200),
                        ("Department",200),("Contact",130),("Mark Attendance",220)]:
            tk.Label(hdr, text=txt, bg=T["card2"], fg=T["subtext"],
                     font=(FONT, 9, "bold"),
                     padx=8, pady=8, width=ww//8, anchor="w").pack(side="left")

        students = self.db.get_attendance_for_date(att_date)

        if not students:
            tk.Label(self._inner, text="No students yet. Add students first.",
                     bg=T["card"], fg=T["subtext"],
                     font=(FONT, 11), pady=30).pack()
            self._summary_var.set("No students.")
            return

        for i, s in enumerate(students):
            sid     = s["student_id"]
            mark    = tk.StringVar(value=s["status"])   # pre-loaded!
            self._marks[sid] = mark

            row_bg = T["tree_bg"] if i%2==0 else T["tree_alt"]
            row    = tk.Frame(self._inner, bg=row_bg)
            row.pack(fill="x")

            for txt, ww in [
                (str(i+1),         30),
                (s["student_code"],90),
                (s["name"],       200),
                (s["department"], 200),
                (s["contact"] or "—", 130),
            ]:
                tk.Label(row, text=txt, bg=row_bg, fg=T["text"],
                         font=(FONT, 9), padx=8, pady=9,
                         width=ww//8, anchor="w").pack(side="left")

            # Radio buttons
            rb_frame = tk.Frame(row, bg=row_bg)
            rb_frame.pack(side="left", padx=8)
            for status, col_ in [("Present", T["success"]),
                                  ("Absent",  T["accent2"])]:
                tk.Radiobutton(rb_frame, text=status,
                               variable=mark, value=status,
                               bg=row_bg, fg=col_,
                               activebackground=row_bg,
                               selectcolor=row_bg,
                               font=(FONT, 10, "bold"),
                               command=self._update_summary
                               ).pack(side="left", padx=6)

        self._update_summary()

    def _update_summary(self):
        p = sum(1 for v in self._marks.values() if v.get()=="Present")
        a = sum(1 for v in self._marks.values() if v.get()=="Absent")
        u = sum(1 for v in self._marks.values() if not v.get())
        self._summary_var.set(
            f"Total {len(self._marks)}  |  ✅ {p}  |  ❌ {a}  |  ⏳ {u}")

    def _bulk(self, status):
        for v in self._marks.values():
            v.set(status)
        self._update_summary()

    def _reset_all(self):
        for v in self._marks.values():
            v.set("")
        self._update_summary()

    def _save(self):
        att_date = self._get_selected_date()
        if att_date is None:
            return
        if not self._marks:
            messagebox.showinfo("Empty", "No students to save.")
            return

        saved = 0
        for sid, var in self._marks.items():
            status = var.get()
            if status:
                if self.db.mark_attendance(sid, status, att_date):
                    saved += 1

        if saved:
            messagebox.showinfo("Saved",
                                f"✅ Saved {saved} record(s) for {att_date}.")
        else:
            messagebox.showinfo("Nothing Saved",
                                "Mark at least one student before saving.")

    def refresh(self):
        """Called when switching to this page — reset to today."""
        self._go_today()


#  PAGE: RECORDS  (view + filter + edit history)

class RecordsPage(tk.Frame):
    """
    Full attendance history with Year / Month / Day / Name filters.
    Supports inline edit and delete of individual records.
    """

    def __init__(self, parent, T, db):
        super().__init__(parent, bg=T["bg"])
        self.T  = T
        self.db = db
        self._build()

    def _build(self):
        T  = self.T
        bg = T["bg"]

        page_header(self, "Attendance Records", T)

        #  Filter bar 
        self._filter = FilterBar(self, T, self.db, self._do_filter)
        self._filter.pack(fill="x", padx=28, pady=(0, 8))

        #  Summary bar 
        sum_bar = tk.Frame(self, bg=T["card2"],
                           highlightthickness=1,
                           highlightbackground=T["border"])
        sum_bar.pack(fill="x", padx=28, pady=(0, 8))
        self._sum_var = tk.StringVar(value="")
        tk.Label(sum_bar, textvariable=self._sum_var,
                 bg=T["card2"], fg=T["text"],
                 font=(FONT, 9), padx=12, pady=6).pack(side="left")

        #  Treeview 
        tf = tk.Frame(self, bg=T["card"],
                      highlightthickness=1, highlightbackground=T["border"])
        tf.pack(fill="both", expand=True, padx=28, pady=(0, 6))

        cols = ("ID", "Code", "Name", "Department",
                "Date", "Day", "Month", "Year", "Status")
        self._tree = ttk.Treeview(tf, columns=cols,
                                  show="headings", selectmode="browse")
        ws = {"ID":40, "Code":80, "Name":170, "Department":180,
              "Date":95, "Day":40, "Month":70, "Year":55, "Status":80}
        center = {"ID","Code","Date","Day","Month","Year","Status"}
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=ws[c],
                              anchor="center" if c in center else "w")

        vsb = ttk.Scrollbar(tf, orient="vertical",  command=self._tree.yview)
        hsb = ttk.Scrollbar(tf, orient="horizontal", command=self._tree.xview)
        self._tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Double-click to edit
        self._tree.bind("<Double-1>", lambda _: self._edit_selected())

        #  Action buttons 
        act = tk.Frame(self, bg=bg)
        act.pack(fill="x", padx=28, pady=(0, 18))

        for txt, col_, cmd in [
            ("✏️ Edit Record",   T["warning"],  self._edit_selected),
            ("🗑️ Delete Record", T["accent2"],  self._delete_selected),
        ]:
            tk.Button(act, text=txt, bg=col_, fg="#fff",
                      font=(FONT, 10, "bold"), relief="flat",
                      padx=14, pady=5, command=cmd).pack(side="left", padx=(0,8))

        tk.Label(act, text="Double-click a row to edit",
                 bg=bg, fg=T["subtext"], font=(FONT, 8)).pack(side="left")

        self._count_var = tk.StringVar()
        tk.Label(act, textvariable=self._count_var,
                 bg=bg, fg=T["subtext"],
                 font=(FONT, 9)).pack(side="right")

        self.refresh()

    def _do_filter(self, year, month, day, name):
        T    = self.T
        rows = self.db.get_records(year, month, day, name)

        for r in self._tree.get_children():
            self._tree.delete(r)

        p_cnt = a_cnt = 0
        for i, r in enumerate(rows):
            tag  = "even" if i%2==0 else "odd"
            stat = r["status"]
            if stat == "Present": p_cnt += 1
            else:                 a_cnt += 1
            self._tree.insert("", "end",
                              iid=str(r["attendance_id"]),
                              values=(r["attendance_id"],
                                      r["student_code"], r["name"],
                                      r["department"],
                                      r["date"], r["dy"], MONTHS[int(r["mo"])],
                                      r["yr"], stat),
                              tags=(tag, stat.lower()))

        self._tree.tag_configure("even",    background=T["tree_bg"])
        self._tree.tag_configure("odd",     background=T["tree_alt"])
        self._tree.tag_configure("present", foreground=T["success"])
        self._tree.tag_configure("absent",  foreground=T["accent2"])

        total = len(rows)
        rate  = round(100*p_cnt/total, 1) if total else 0
        self._sum_var.set(
            f"  Records: {total}  |  Present: {p_cnt}  "
            f"|  Absent: {a_cnt}  |  Rate: {rate}%")
        self._count_var.set(f"{total} record(s)")

    def _get_selected_record(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("Select", "Please select a record first.")
            return None
        att_id = int(sel[0])
        # build a minimal dict from the tree row
        vals = self._tree.item(sel[0])["values"]
        return {
            "attendance_id": vals[0],
            "student_code":  vals[1],
            "name":          vals[2],
            "date":          vals[4],
            "status":        vals[8],
        }

    def _edit_selected(self):
        rec = self._get_selected_record()
        if rec is None: return
        EditAttendanceDialog(self.winfo_toplevel(), self.T, self.db,
                             rec, on_save=self.refresh)

    def _delete_selected(self):
        rec = self._get_selected_record()
        if rec is None: return
        if messagebox.askyesno("Confirm",
                               f"Delete attendance record for "
                               f"'{rec['name']}' on {rec['date']}?",
                               icon="warning"):
            if self.db.delete_attendance(rec["attendance_id"]):
                self.refresh()

    def refresh(self):
        self._filter.reload_years()
        self._do_filter("", "", "", "")


#  PAGE: HISTORY  (monthly calendar view)

class HistoryPage(tk.Frame):
    """
    Calendar-style monthly view.
    Each day cell shows Present / Absent count.
    Click a day → filters Records page for that date.
    """

    def __init__(self, parent, T, db, on_jump_to_records=None):
        super().__init__(parent, bg=T["bg"])
        self.T                  = T
        self.db                 = db
        self.on_jump_to_records = on_jump_to_records

        today = date.today()
        self._year  = today.year
        self._month = today.month
        self._build()

    def _build(self):
        T  = self.T
        bg = T["bg"]

        page_header(self, "Monthly History", T)

        #  Navigation bar  
        nav = tk.Frame(self, bg=bg)
        nav.pack(fill="x", padx=28, pady=(0, 10))

        tk.Button(nav, text="◄  Prev",
                  bg=T["card2"], fg=T["text"],
                  font=(FONT, 10), relief="flat", padx=10, pady=4,
                  command=self._prev_month).pack(side="left")

        self._month_label = tk.Label(nav, text="",
                                     bg=bg, fg=T["text"],
                                     font=(FONT, 13, "bold"))
        self._month_label.pack(side="left", padx=20)

        tk.Button(nav, text="Next  ►",
                  bg=T["card2"], fg=T["text"],
                  font=(FONT, 10), relief="flat", padx=10, pady=4,
                  command=self._next_month).pack(side="left")

        tk.Button(nav, text="📅 This Month",
                  bg=T["accent"], fg="#fff",
                  font=(FONT, 10, "bold"), relief="flat", padx=10, pady=4,
                  command=self._this_month).pack(side="left", padx=12)

        #  Legend  
        legend = tk.Frame(nav, bg=bg)
        legend.pack(side="right")
        for text, col_ in [("■ Present", T["success"]),
                            ("■ Absent",  T["accent2"]),
                            ("■ No data", T["subtext"])]:
            tk.Label(legend, text=text, bg=bg, fg=col_,
                     font=(FONT, 9)).pack(side="left", padx=6)

        #  Monthly stats bar 
        self._stat_var = tk.StringVar()
        stat_bar = tk.Frame(self, bg=T["card2"],
                            highlightthickness=1,
                            highlightbackground=T["border"])
        stat_bar.pack(fill="x", padx=28, pady=(0, 10))
        tk.Label(stat_bar, textvariable=self._stat_var,
                 bg=T["card2"], fg=T["text"],
                 font=(FONT, 9), padx=12, pady=6).pack(side="left")

        #  Calendar grid 
        self._cal_frame = tk.Frame(self, bg=bg)
        self._cal_frame.pack(fill="both", expand=True, padx=28, pady=(0, 18))

        self._draw_calendar()

    def _draw_calendar(self):
        T     = self.T
        bg    = T["bg"]

        for w in self._cal_frame.winfo_children():
            w.destroy()

        yr, mo = self._year, self._month
        self._month_label.config(text=f"{MONTHS[mo]}  {yr}")

        # Day-of-week headers
        dow_row = tk.Frame(self._cal_frame, bg=T["cal_head"])
        dow_row.pack(fill="x")
        for day_name in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]:
            tk.Label(dow_row, text=day_name, bg=T["cal_head"], fg=T["subtext"],
                     font=(FONT, 9, "bold"),
                     width=8, anchor="center", pady=6).pack(side="left", expand=True)

        # Data
        data    = self.db.get_monthly_summary(yr, mo)
        cal_mat = calendar.monthcalendar(yr, mo)

        # Monthly totals
        total_p = sum(v["present"] for v in data.values())
        total_a = sum(v["absent"]  for v in data.values())
        total   = total_p + total_a
        rate    = round(100 * total_p / total, 1) if total else 0
        self._stat_var.set(
            f"  {MONTHS[mo]} {yr}  —  "
            f"Days with records: {len(data)}  |  "
            f"Total Present marks: {total_p}  |  "
            f"Total Absent marks: {total_a}  |  "
            f"Overall rate: {rate}%")

        for week in cal_mat:
            week_row = tk.Frame(self._cal_frame, bg=bg)
            week_row.pack(fill="x", expand=True)

            for day_num in week:
                cell = tk.Frame(week_row,
                                bg=T["cal_empty"],
                                highlightthickness=1,
                                highlightbackground=T["border"],
                                width=100, height=72)
                cell.pack(side="left", expand=True, fill="both",
                          padx=2, pady=2)
                cell.pack_propagate(False)

                if day_num == 0:
                    continue   # empty cell before/after month

                date_str = f"{yr:04d}-{mo:02d}-{day_num:02d}"
                is_today = (date_str == date.today().isoformat())

                # Day number
                day_lbl_bg = T["cal_today"] if is_today else T["cal_empty"]
                day_fg     = "#ffffff"  if is_today else T["subtext"]
                tk.Label(cell, text=str(day_num),
                         bg=day_lbl_bg, fg=day_fg,
                         font=(FONT, 9, "bold" if is_today else "normal"),
                         padx=4, pady=2).pack(anchor="ne")

                if date_str in data:
                    p = data[date_str]["present"]
                    a = data[date_str]["absent"]
                    tk.Label(cell, text=f"✅ {p}",
                             bg=T["cal_empty"], fg=T["success"],
                             font=(FONT, 9)).pack(anchor="w", padx=4)
                    tk.Label(cell, text=f"❌ {a}",
                             bg=T["cal_empty"], fg=T["accent2"],
                             font=(FONT, 9)).pack(anchor="w", padx=4)
                    # Clickable — jump to Records for that date
                    cell.bind("<Button-1>",
                              lambda e, ds=date_str: self._jump(ds))
                    for child in cell.winfo_children():
                        child.bind("<Button-1>",
                                   lambda e, ds=date_str: self._jump(ds))
                    cell.config(cursor="hand2")

        self._cal_frame.update_idletasks()

    def _jump(self, date_str: str):
        """Navigate to Records page filtered for the clicked date."""
        if self.on_jump_to_records:
            yr, mo, dy = date_str.split("-")
            self.on_jump_to_records(yr, mo, dy)

    def _prev_month(self):
        if self._month == 1:
            self._month = 12
            self._year -= 1
        else:
            self._month -= 1
        self._draw_calendar()

    def _next_month(self):
        if self._month == 12:
            self._month = 1
            self._year += 1
        else:
            self._month += 1
        self._draw_calendar()

    def _this_month(self):
        td = date.today()
        self._year  = td.year
        self._month = td.month
        self._draw_calendar()

    def refresh(self):
        self._draw_calendar()


#  PAGE: EXPORT

class ExportPage(tk.Frame):
    def __init__(self, parent, T, db):
        super().__init__(parent, bg=T["bg"])
        self.T  = T
        self.db = db
        self._build()

    def _build(self):
        T  = self.T
        bg = T["bg"]

        page_header(self, "Export & Reports", T)

        #  Filter + export 
        tk.Label(self, text="Filter before export (all optional):",
                 bg=bg, fg=T["subtext"],
                 font=(FONT, 9)).pack(anchor="w", padx=28, pady=(0, 4))

        self._filter = FilterBar(self, T, self.db, self._on_filter)
        self._filter.pack(fill="x", padx=28, pady=(0, 10))

        # Export buttons row
        exp_row = tk.Frame(self, bg=bg)
        exp_row.pack(fill="x", padx=28, pady=(0, 16))

        for txt, col_, cmd in [
            ("📄 Export Filtered Records", T["accent"],  self._export_records),
            ("📊 Export Summary Report",   T["success"], self._export_summary),
        ]:
            tk.Button(exp_row, text=txt, bg=col_, fg="#fff",
                      font=(FONT, 10, "bold"), relief="flat",
                      padx=14, pady=7, command=cmd).pack(side="left", padx=(0,10))

        #  Summary treeview 
        tk.Label(self, text="Student Summary",
                 bg=bg, fg=T["text"],
                 font=(FONT, 12, "bold")).pack(anchor="w", padx=28, pady=(0, 6))

        tf = tk.Frame(self, bg=T["card"],
                      highlightthickness=1, highlightbackground=T["border"])
        tf.pack(fill="both", expand=True, padx=28, pady=(0, 18))

        cols = ("Code", "Name", "Department",
                "Contact", "Present", "Absent", "Total", "Rate %")
        self._tree = ttk.Treeview(tf, columns=cols, show="headings", height=9)
        ws = {"Code":80, "Name":170, "Department":200,
              "Contact":120, "Present":70, "Absent":70,
              "Total":60, "Rate %":80}
        for c in cols:
            self._tree.heading(c, text=c)
            self._tree.column(c, width=ws[c],
                              anchor="center" if c not in ("Name","Department","Contact") else "w")
        self._tree.pack(fill="both", expand=True)

        self._records_cache = []
        self.refresh()

    def _on_filter(self, yr, mo, dy, name):
        self._records_cache = self.db.get_records(yr, mo, dy, name)

    def refresh(self):
        self._filter.reload_years()
        self._records_cache = self.db.get_records()
        self._load_summary()

    def _load_summary(self):
        T = self.T
        for r in self._tree.get_children():
            self._tree.delete(r)

        rows = self.db.conn.execute("""
            SELECT s.student_code, s.name, s.department, s.contact,
                   SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS p,
                   SUM(CASE WHEN a.status='Absent'  THEN 1 ELSE 0 END) AS ab,
                   COUNT(a.attendance_id) AS tot,
                   ROUND(100.0*SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)
                         /MAX(COUNT(a.attendance_id),1),1) AS rate
            FROM students s
            LEFT JOIN attendance a USING(student_id)
            GROUP BY s.student_id ORDER BY rate DESC
        """).fetchall()

        for i, r in enumerate(rows):
            tag  = "even" if i%2==0 else "odd"
            rate = r["rate"] if r["rate"] is not None else 0
            lvl  = "high" if rate>=75 else ("mid" if rate>=50 else "low")
            self._tree.insert("", "end",
                              values=(r["student_code"], r["name"],
                                      r["department"], r["contact"] or "—",
                                      r["p"], r["ab"], r["tot"], f"{rate}%"),
                              tags=(tag, lvl))

        self._tree.tag_configure("even", background=T["tree_bg"])
        self._tree.tag_configure("odd",  background=T["tree_alt"])
        self._tree.tag_configure("high", foreground=T["success"])
        self._tree.tag_configure("mid",  foreground=T["warning"])
        self._tree.tag_configure("low",  foreground=T["accent2"])

    def _export_records(self):
        rows = self._records_cache or self.db.get_records()
        if not rows:
            messagebox.showinfo("No Data", "No records match the current filter.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="attendance_records")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["ID","Code","Name","Department",
                             "Contact","Date","Day","Month","Year","Status"])
                for r in rows:
                    w.writerow([r["attendance_id"], r["student_code"],
                                r["name"], r["department"],
                                r["contact"] if "contact" in r.keys() else "",
                                r["date"], r["dy"],
                                MONTHS[int(r["mo"])], r["yr"], r["status"]])
            messagebox.showinfo("Done", f"Exported {len(rows)} records to:\n{path}")
        except OSError as e:
            messagebox.showerror("Error", str(e))

    def _export_summary(self):
        rows = self.db.conn.execute("""
            SELECT s.student_code, s.name, s.department, s.contact,
                   SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END) AS p,
                   SUM(CASE WHEN a.status='Absent'  THEN 1 ELSE 0 END) AS ab,
                   COUNT(a.attendance_id) AS tot,
                   ROUND(100.0*SUM(CASE WHEN a.status='Present' THEN 1 ELSE 0 END)
                         /MAX(COUNT(a.attendance_id),1),1) AS rate
            FROM students s LEFT JOIN attendance a USING(student_id)
            GROUP BY s.student_id ORDER BY s.student_code
        """).fetchall()
        if not rows:
            messagebox.showinfo("No Data", "No data to export.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile="attendance_summary")
        if not path: return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Code","Name","Department","Contact",
                             "Present","Absent","Total Days","Rate %"])
                for r in rows:
                    w.writerow([r["student_code"], r["name"],
                                r["department"], r["contact"] or "",
                                r["p"], r["ab"], r["tot"],
                                f"{r['rate']}%"])
            messagebox.showinfo("Done", f"Summary exported to:\n{path}")
        except OSError as e:
            messagebox.showerror("Error", str(e))


#  MAIN APPLICATION

class AttendanceApp(tk.Tk):
    """
    Root window — sidebar, page router, theme toggle, status bar.
    """

    def __init__(self):
        super().__init__()
        self.title("Attendance Management System  v2.0")
        self.geometry("1160x700")
        self.minsize(960, 600)

        self._mode  = "dark"
        self._T     = THEMES["dark"]
        self._style = ttk.Style(self)
        apply_theme(self._style, self._T)

        self.db = DatabaseManager()

        self._pages       = {}
        self._nav_btns    = {}
        self._active_page = "dashboard"

        self._build_ui()

    #  Build 
    def _build_ui(self):
        T = self._T

        # Sidebar
        self._sb = tk.Frame(self, bg=T["sidebar"], width=215)
        self._sb.pack(side="left", fill="y")
        self._sb.pack_propagate(False)

        # Main area
        self._main = tk.Frame(self, bg=T["bg"])
        self._main.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_status_bar()
        self._build_pages()
        self._show_page("dashboard")

    def _build_sidebar(self):
        T = self._T
        sb = self._sb

        # Logo strip
        logo = tk.Frame(sb, bg=T["accent"], height=62)
        logo.pack(fill="x")
        logo.pack_propagate(False)
        tk.Label(logo, text="📋 AttendPro v2",
                 bg=T["accent"], fg="#fff",
                 font=(FONT, 12, "bold")).pack(expand=True)

        tk.Frame(sb, bg=T["sidebar"], height=10).pack(fill="x")
        tk.Label(sb, text="MENU", bg=T["sidebar"], fg=T["subtext"],
                 font=(FONT, 7, "bold"), padx=16, pady=2).pack(anchor="w")

        self._nav_btns = {}
        for label, icon, key in NAV_ITEMS:
            b = tk.Button(sb, text=f"  {icon}  {label}",
                          bg=T["sidebar"], fg=T["text"],
                          font=(FONT, 10), anchor="w",
                          relief="flat", bd=0,
                          padx=10, pady=9,
                          activebackground=T["accent"],
                          activeforeground="#fff",
                          command=lambda k=key: self._show_page(k))
            b.pack(fill="x", padx=8, pady=1)
            self._nav_btns[key] = b

        # Bottom
        bottom = tk.Frame(sb, bg=T["sidebar"])
        bottom.pack(side="bottom", fill="x", pady=12)
        ttk.Separator(sb).pack(side="bottom", fill="x", padx=8, pady=4)

        self._theme_btn = tk.Button(bottom,
                                    text="☀️  Light Mode",
                                    bg=T["sidebar"], fg=T["subtext"],
                                    font=(FONT, 9), anchor="w",
                                    relief="flat", bd=0,
                                    padx=14, pady=6,
                                    command=self._toggle_theme)
        self._theme_btn.pack(fill="x")
        tk.Label(bottom, text="© AttendPro 2025",
                 bg=T["sidebar"], fg=T["subtext"],
                 font=(FONT, 7)).pack()

    def _build_status_bar(self):
        T   = self._T
        bar = tk.Frame(self._main, bg=T["status_bg"], height=24)
        bar.pack(side="bottom", fill="x")
        bar.pack_propagate(False)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(bar, textvariable=self._status_var,
                 bg=T["status_bg"], fg=T["subtext"],
                 font=(FONT, 8), anchor="w", padx=12).pack(side="left", fill="y")

        self._clock_var = tk.StringVar()
        tk.Label(bar, textvariable=self._clock_var,
                 bg=T["status_bg"], fg=T["subtext"],
                 font=(FONT, 8), padx=12).pack(side="right")
        self._tick()

    def _tick(self):
        self._clock_var.set(datetime.now().strftime("%d %b %Y  %H:%M:%S"))
        self.after(1000, self._tick)

    def _build_pages(self):
        T  = self._T
        db = self.db

        # Content area
        self._content = tk.Frame(self._main, bg=T["bg"])
        self._content.pack(fill="both", expand=True)

        # Records page is shared — History page references it
        records_page = RecordsPage(self._content, T, db)

        def jump_to_records(yr, mo, dy):
            self._show_page("records")
            records_page._filter.set_date(yr, mo, dy)

        self._pages = {
            "dashboard":  DashboardPage(self._content,  T, db),
            "students":   StudentsPage(self._content,   T, db),
            "attendance": AttendancePage(self._content, T, db),
            "records":    records_page,
            "history":    HistoryPage(self._content, T, db,
                                      on_jump_to_records=jump_to_records),
            "export":     ExportPage(self._content, T, db),
        }
        for p in self._pages.values():
            p.place(relx=0, rely=0, relwidth=1, relheight=1)

    def _show_page(self, key: str):
        T = self._T
        for k, b in self._nav_btns.items():
            b.config(bg=T["accent"] if k==key else T["sidebar"],
                     fg="#fff"     if k==key else T["text"])

        self._pages[key].lift()
        self._active_page = key

        if hasattr(self._pages[key], "refresh"):
            self._pages[key].refresh()

        labels = {p[2]: p[0] for p in NAV_ITEMS}
        self._status_var.set(f"Viewing: {labels.get(key, key)}")

    def _toggle_theme(self):
        self._mode = "light" if self._mode == "dark" else "dark"
        self._T    = THEMES[self._mode]
        apply_theme(self._style, self._T)

        # Rebuild entire UI (correct approach for full-palette swap in Tkinter)
        for w in self._sb.winfo_children():
            w.destroy()
        for w in self._main.winfo_children():
            w.destroy()

        self._sb.config(bg=self._T["sidebar"])
        self._main.config(bg=self._T["bg"])

        self._build_sidebar()
        self._build_status_bar()
        self._build_pages()
        self._show_page(self._active_page)

        btn_text = "🌙  Dark Mode" if self._mode == "light" else "☀️  Light Mode"
        self._theme_btn.config(text=btn_text)

    def _on_close(self):
        self.db.close()
        self.destroy()


#  ENTRY POINT
if __name__ == "__main__":
    app = AttendanceApp()
    app.protocol("WM_DELETE_WINDOW", app._on_close)
    app.mainloop()