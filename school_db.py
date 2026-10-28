"""SQLite school database setup and deterministic demo data."""

from __future__ import annotations

import random
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

DATABASE_PATH = Path(__file__).parent / "school.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS teachers (
    teacher_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL,
    hire_date TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sections (
    section_id INTEGER PRIMARY KEY,
    grade_level INTEGER NOT NULL,
    section_name TEXT NOT NULL,
    homeroom_teacher_id INTEGER NOT NULL REFERENCES teachers(teacher_id),
    room_number TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS students (
    student_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    grade_level INTEGER NOT NULL,
    section_id INTEGER NOT NULL REFERENCES sections(section_id),
    enrollment_date TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS subjects (
    subject_id INTEGER PRIMARY KEY,
    subject_name TEXT NOT NULL UNIQUE,
    department TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS enrollments (
    enrollment_id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    subject_id INTEGER NOT NULL REFERENCES subjects(subject_id),
    teacher_id INTEGER NOT NULL REFERENCES teachers(teacher_id),
    school_year TEXT NOT NULL,
    UNIQUE(student_id, subject_id, school_year)
);
CREATE TABLE IF NOT EXISTS grades (
    grade_id INTEGER PRIMARY KEY,
    enrollment_id INTEGER NOT NULL REFERENCES enrollments(enrollment_id),
    term TEXT NOT NULL,
    assessment TEXT NOT NULL,
    score REAL NOT NULL CHECK(score BETWEEN 0 AND 100),
    recorded_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS attendance (
    attendance_id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    attendance_date TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('present', 'absent', 'late', 'excused')),
    UNIQUE(student_id, attendance_date)
);
"""

TEACHERS = [
    ("Ava", "Patel", "Mathematics", "2018-08-15"),
    ("Noah", "Kim", "Science", "2019-01-07"),
    ("Mia", "Garcia", "English", "2017-08-21"),
    ("Ethan", "Johnson", "History", "2020-08-10"),
    ("Zoe", "Chen", "Mathematics", "2021-01-04"),
    ("Leo", "Williams", "Science", "2016-08-12"),
    ("Ivy", "Brown", "Arts", "2022-08-18"),
    ("Owen", "Davis", "English", "2019-08-19"),
]

STUDENT_FIRST_NAMES = [
    "Aria", "Mason", "Nora", "Lucas", "Layla", "Elijah", "Sofia", "James",
    "Amara", "Henry", "Mila", "Mateo", "Chloe", "Eli", "Aisha", "Finn",
    "Priya", "Theo", "Ruby", "Kai", "Leah", "Ezra", "Anya", "Caleb",
    "Iris", "Hugo", "Maya", "Jude", "Zara", "Rowan",
]
STUDENT_LAST_NAMES = [
    "Shah", "Miller", "Wilson", "Singh", "Moore", "Taylor", "Anderson",
    "Thomas", "Martin", "Lee", "Clark", "Lewis", "Walker", "Hall", "Young",
]
SUBJECTS = [
    ("Mathematics", "STEM"),
    ("Biology", "STEM"),
    ("English Literature", "Humanities"),
    ("World History", "Humanities"),
    ("Computer Science", "STEM"),
    ("Visual Arts", "Arts"),
]


def initialize_database(database_path: str | Path = DATABASE_PATH) -> Path:
    """Create the schema and seed demo records once, preserving existing data."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        with connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.executescript(SCHEMA)
            if connection.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
                _seed_database(connection)
    return path


def _seed_database(connection: sqlite3.Connection) -> None:
    rng = random.Random(23)
    today = date.today()
    connection.executemany(
        "INSERT INTO teachers (first_name, last_name, email, department, hire_date) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (first, last, f"{first.lower()}.{last.lower()}@demo.school", department, hired)
            for first, last, department, hired in TEACHERS
        ],
    )
    connection.executemany(
        "INSERT INTO sections (grade_level, section_name, homeroom_teacher_id, room_number) "
        "VALUES (?, ?, ?, ?)",
        [
            (grade, section, (grade + offset) % len(TEACHERS) + 1, f"{100 + grade * 10 + offset}")
            for grade in range(6, 9)
            for offset, section in enumerate(("A", "B"))
        ],
    )
    connection.executemany(
        "INSERT INTO subjects (subject_name, department) VALUES (?, ?)", SUBJECTS
    )

    section_rows = connection.execute(
        "SELECT section_id, grade_level FROM sections ORDER BY section_id"
    ).fetchall()
    students = []
    for student_id in range(1, 31):
        first = STUDENT_FIRST_NAMES[student_id - 1]
        last = STUDENT_LAST_NAMES[(student_id * 7) % len(STUDENT_LAST_NAMES)]
        section_id, grade = section_rows[(student_id - 1) % len(section_rows)]
        birth_year = today.year - grade - 6
        students.append(
            (
                first,
                last,
                date(birth_year, (student_id % 12) + 1, (student_id % 27) + 1).isoformat(),
                grade,
                section_id,
                f"{today.year - 1}-08-20",
                f"student{student_id:02d}@demo.school",
            )
        )
    connection.executemany(
        "INSERT INTO students (first_name, last_name, date_of_birth, grade_level, "
        "section_id, enrollment_date, email) VALUES (?, ?, ?, ?, ?, ?, ?)",
        students,
    )

    subject_rows = connection.execute(
        "SELECT subject_id, subject_name FROM subjects ORDER BY subject_id"
    ).fetchall()
    enrollments = []
    for student_id in range(1, 31):
        for subject_id, subject_name in subject_rows:
            teacher_id = {
                "Mathematics": 1,
                "Biology": 2,
                "English Literature": 3,
                "World History": 4,
                "Computer Science": 5,
                "Visual Arts": 7,
            }[subject_name]
            enrollments.append((student_id, subject_id, teacher_id, f"{today.year}-{today.year + 1}"))
    connection.executemany(
        "INSERT INTO enrollments (student_id, subject_id, teacher_id, school_year) "
        "VALUES (?, ?, ?, ?)",
        enrollments,
    )

    grade_rows = []
    for enrollment_id in range(1, len(enrollments) + 1):
        for term in ("Fall", "Spring"):
            for assessment in ("Quiz", "Project", "Exam"):
                grade_rows.append(
                    (
                        enrollment_id,
                        term,
                        assessment,
                        round(max(45, min(100, rng.gauss(82, 11))), 1),
                        today.isoformat(),
                    )
                )
    connection.executemany(
        "INSERT INTO grades (enrollment_id, term, assessment, score, recorded_at) "
        "VALUES (?, ?, ?, ?, ?)",
        grade_rows,
    )

    attendance_rows = []
    for student_id in range(1, 31):
        for days_ago in range(30):
            attendance_date = today - timedelta(days=days_ago)
            if attendance_date.weekday() < 5:
                status = rng.choices(
                    ("present", "absent", "late", "excused"),
                    weights=(88, 5, 5, 2),
                    k=1,
                )[0]
                attendance_rows.append((student_id, attendance_date.isoformat(), status))
    connection.executemany(
        "INSERT INTO attendance (student_id, attendance_date, status) VALUES (?, ?, ?)",
        attendance_rows,
    )
