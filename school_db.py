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
CREATE TABLE IF NOT EXISTS guardians (
    guardian_id INTEGER PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS student_guardians (
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    guardian_id INTEGER NOT NULL REFERENCES guardians(guardian_id),
    relationship TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0, 1)),
    PRIMARY KEY(student_id, guardian_id)
);
CREATE TABLE IF NOT EXISTS school_terms (
    term_id INTEGER PRIMARY KEY,
    school_year TEXT NOT NULL,
    term_name TEXT NOT NULL,
    starts_on TEXT NOT NULL,
    ends_on TEXT NOT NULL,
    UNIQUE(school_year, term_name)
);
CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY,
    enrollment_id INTEGER NOT NULL REFERENCES enrollments(enrollment_id),
    term_id INTEGER NOT NULL REFERENCES school_terms(term_id),
    title TEXT NOT NULL,
    due_date TEXT NOT NULL,
    max_points REAL NOT NULL CHECK(max_points > 0),
    UNIQUE(enrollment_id, title)
);
CREATE TABLE IF NOT EXISTS assignment_submissions (
    submission_id INTEGER PRIMARY KEY,
    assignment_id INTEGER NOT NULL UNIQUE REFERENCES assignments(assignment_id),
    submitted_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('submitted', 'late', 'missing', 'excused')),
    score REAL CHECK(score IS NULL OR score >= 0),
    CHECK(status != 'missing' OR score IS NULL)
);
CREATE TABLE IF NOT EXISTS clubs (
    club_id INTEGER PRIMARY KEY,
    club_name TEXT NOT NULL UNIQUE,
    teacher_id INTEGER NOT NULL REFERENCES teachers(teacher_id),
    meeting_day TEXT NOT NULL,
    room_number TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS club_memberships (
    student_id INTEGER NOT NULL REFERENCES students(student_id),
    club_id INTEGER NOT NULL REFERENCES clubs(club_id),
    joined_on TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'Member',
    PRIMARY KEY(student_id, club_id)
);
CREATE TABLE IF NOT EXISTS school_events (
    event_id INTEGER PRIMARY KEY,
    event_name TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_date TEXT NOT NULL,
    description TEXT NOT NULL,
    UNIQUE(event_name, event_date)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_grades_enrollment_term_assessment
    ON grades(enrollment_id, term, assessment);
CREATE INDEX IF NOT EXISTS idx_students_grade_section
    ON students(grade_level, section_id);
CREATE INDEX IF NOT EXISTS idx_enrollments_student_subject
    ON enrollments(student_id, subject_id, teacher_id);
CREATE INDEX IF NOT EXISTS idx_attendance_date_status
    ON attendance(attendance_date, status);
CREATE INDEX IF NOT EXISTS idx_assignments_term_due_date
    ON assignments(term_id, due_date);
CREATE INDEX IF NOT EXISTS idx_submissions_status
    ON assignment_submissions(status);
CREATE INDEX IF NOT EXISTS idx_club_memberships_club
    ON club_memberships(club_id, student_id);
CREATE INDEX IF NOT EXISTS idx_school_events_date
    ON school_events(event_date);
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
    ("Nina", "Shah", "Science", "2018-02-12"),
    ("Isaac", "Moore", "Mathematics", "2023-08-14"),
    ("Elena", "Wilson", "History", "2015-08-17"),
    ("Miles", "Taylor", "Physical Education", "2020-01-06"),
    ("Hana", "Singh", "Languages", "2021-08-16"),
    ("Jasper", "Lee", "Science", "2017-01-09"),
    ("Sana", "Walker", "Arts", "2024-08-19"),
    ("Felix", "Young", "English", "2022-01-10"),
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
    ("Mathematics", "STEM", "Mathematics"),
    ("Biology", "STEM", "Science"),
    ("English Literature", "Humanities", "English"),
    ("World History", "Humanities", "History"),
    ("Computer Science", "STEM", "Science"),
    ("Visual Arts", "Arts", "Arts"),
    ("Chemistry", "STEM", "Science"),
    ("Physics", "STEM", "Mathematics"),
    ("Geography", "Humanities", "History"),
    ("Physical Education", "Wellness", "Physical Education"),
]
CLUBS = [
    ("Robotics Club", "Science", "Wednesday", "Lab 2"),
    ("Debate Society", "English", "Tuesday", "Room 204"),
    ("Art Studio", "Arts", "Thursday", "Art Room"),
    ("Math Circle", "Mathematics", "Monday", "Room 108"),
    ("Eco Club", "Science", "Friday", "Room 305"),
    ("Track and Field", "Physical Education", "Wednesday", "Gym"),
]
EVENTS = [
    ("Welcome Assembly", "Assembly", -55, "Opening gathering for the school community."),
    ("Family Curriculum Night", "Community", -42, "Families meet teachers and learn about coursework."),
    ("Fall Science Fair", "Academic", -25, "Student science projects and demonstrations."),
    ("Reading Week", "Academic", -12, "A week celebrating reading across the school."),
    ("Winter Concert", "Arts", 18, "Seasonal music and student performances."),
    ("Career Exploration Day", "Community", 35, "Students explore career paths and interests."),
    ("Spring Athletics Meet", "Sports", 62, "Friendly inter-section athletic competition."),
    ("Student Showcase", "Arts", 78, "A showcase of student artwork and creative projects."),
    ("Community Service Day", "Community", 91, "School-wide community volunteer activities."),
    ("Year-End Celebration", "Celebration", 115, "A celebration of the school year's achievements."),
]


def initialize_database(database_path: str | Path = DATABASE_PATH) -> Path:
    """Create or upgrade the schema and idempotently seed demo records."""
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        with connection:
            _seed_database(connection)
    return path


def _insert_reference_data(connection: sqlite3.Connection) -> None:
    connection.executemany(
        "INSERT OR IGNORE INTO teachers "
        "(first_name, last_name, email, department, hire_date) VALUES (?, ?, ?, ?, ?)",
        [
            (first, last, f"{first.lower()}.{last.lower()}@demo.school", department, hired)
            for first, last, department, hired in TEACHERS
        ],
    )
    teacher_ids = {
        department: [
            row[0]
            for row in connection.execute(
                "SELECT teacher_id FROM teachers WHERE department = ? ORDER BY teacher_id",
                (department,),
            ).fetchall()
        ]
        for department in {teacher[2] for teacher in TEACHERS}
    }

    for grade in range(6, 13):
        for section_index, section_name in enumerate(("A", "B")):
            exists = connection.execute(
                "SELECT 1 FROM sections WHERE grade_level = ? AND section_name = ?",
                (grade, section_name),
            ).fetchone()
            if exists:
                continue
            homeroom_ids = teacher_ids["Mathematics"]
            teacher_id = homeroom_ids[(grade + section_index) % len(homeroom_ids)]
            connection.execute(
                "INSERT INTO sections "
                "(grade_level, section_name, homeroom_teacher_id, room_number) "
                "VALUES (?, ?, ?, ?)",
                (grade, section_name, teacher_id, f"{grade}{section_index + 1:02d}"),
            )

    connection.executemany(
        "INSERT OR IGNORE INTO subjects (subject_name, department) VALUES (?, ?)",
        [(name, department) for name, department, _ in SUBJECTS],
    )

    today = date.today()
    school_year_start = today.year if today.month >= 8 else today.year - 1
    school_year = f"{school_year_start}-{school_year_start + 1}"
    term_dates = (
        ("Fall", date(school_year_start, 8, 15), date(school_year_start, 12, 19)),
        ("Spring", date(school_year_start + 1, 1, 5), date(school_year_start + 1, 5, 29)),
        ("Summer", date(school_year_start + 1, 6, 8), date(school_year_start + 1, 7, 24)),
    )
    connection.executemany(
        "INSERT OR IGNORE INTO school_terms (school_year, term_name, starts_on, ends_on) "
        "VALUES (?, ?, ?, ?)",
        [
            (school_year, term_name, starts.isoformat(), ends.isoformat())
            for term_name, starts, ends in term_dates
        ],
    )

    for club_name, department, meeting_day, room_number in CLUBS:
        teacher_options = teacher_ids[department]
        connection.execute(
            "INSERT OR IGNORE INTO clubs (club_name, teacher_id, meeting_day, room_number) "
            "VALUES (?, ?, ?, ?)",
            (club_name, teacher_options[0], meeting_day, room_number),
        )

    for name, event_type, day_offset, description in EVENTS:
        event_date = today + timedelta(days=day_offset)
        connection.execute(
            "INSERT OR IGNORE INTO school_events "
            "(event_name, event_type, event_date, description) VALUES (?, ?, ?, ?)",
            (name, event_type, event_date.isoformat(), description),
        )


def _seed_students(connection: sqlite3.Connection) -> None:
    today = date.today()
    section_ids = {
        (row[1], row[2]): row[0]
        for row in connection.execute(
            "SELECT section_id, grade_level, section_name FROM sections ORDER BY section_id"
        ).fetchall()
    }
    for student_id in range(1, 121):
        first = STUDENT_FIRST_NAMES[(student_id - 1) % len(STUDENT_FIRST_NAMES)]
        last = STUDENT_LAST_NAMES[(student_id * 7) % len(STUDENT_LAST_NAMES)]
        grade = 6 + (student_id - 1) % 7
        section_name = ("A", "B")[(student_id - 1) // 7 % 2]
        birth_year = today.year - grade - 6
        birth_month = (student_id % 12) + 1
        birth_day = (student_id % 27) + 1
        connection.execute(
            "INSERT OR IGNORE INTO students "
            "(student_id, first_name, last_name, date_of_birth, grade_level, "
            "section_id, enrollment_date, email) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                student_id,
                first,
                last,
                date(birth_year, birth_month, birth_day).isoformat(),
                grade,
                section_ids[(grade, section_name)],
                f"{today.year - 1}-08-20",
                f"student{student_id:03d}@demo.school",
            ),
        )


def _seed_enrollments(connection: sqlite3.Connection, school_year: str) -> None:
    teachers_by_department: dict[str, list[int]] = {}
    for row in connection.execute(
        "SELECT teacher_id, department FROM teachers ORDER BY teacher_id"
    ):
        teachers_by_department.setdefault(row[1], []).append(row[0])

    subject_teacher_department = {
        name: teacher_department for name, _, teacher_department in SUBJECTS
    }
    fallback_teacher_department = {
        "STEM": "Science",
        "Humanities": "History",
        "Arts": "Arts",
        "Wellness": "Physical Education",
    }
    subjects = connection.execute(
        "SELECT subject_id, subject_name, department FROM subjects ORDER BY subject_id"
    ).fetchall()
    subject_teacher_rows = []
    for subject_id, subject_name, department in subjects:
        teacher_department = subject_teacher_department.get(
            subject_name,
            fallback_teacher_department.get(department, "Science"),
        )
        matching_teacher_ids = teachers_by_department[teacher_department]
        subject_teacher_rows.append(
            (subject_id, matching_teacher_ids, len(matching_teacher_ids))
        )
    connection.executemany(
        "INSERT OR IGNORE INTO enrollments "
        "(student_id, subject_id, teacher_id, school_year) VALUES (?, ?, ?, ?)",
        [
            (
                student_id,
                subject_id,
                matching_teacher_ids[(student_id + subject_id) % teacher_count],
                school_year,
            )
            for student_id in range(1, 121)
            for subject_id, matching_teacher_ids, teacher_count in subject_teacher_rows
        ],
    )


def _seed_academic_records(connection: sqlite3.Connection, school_year: str) -> None:
    rng = random.Random(23)
    today = date.today()
    enrollment_rows = connection.execute(
        "SELECT enrollment_id, student_id FROM enrollments WHERE school_year = ? "
        "ORDER BY enrollment_id",
        (school_year,),
    ).fetchall()
    terms = {
        row[1]: row[0]
        for row in connection.execute(
            "SELECT term_id, term_name FROM school_terms WHERE school_year = ?",
            (school_year,),
        ).fetchall()
    }

    grade_rows = []
    assignment_rows = []
    for enrollment_id, _student_id in enrollment_rows:
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
        for assignment_number, term in enumerate(("Fall", "Spring"), start=1):
            due_date = today + timedelta(days=assignment_number * 7 + enrollment_id % 14)
            assignment_rows.append(
                (
                    enrollment_id,
                    terms[term],
                    f"{term} project {assignment_number}",
                    due_date.isoformat(),
                    100.0,
                )
            )
    connection.executemany(
        "INSERT OR IGNORE INTO grades "
        "(enrollment_id, term, assessment, score, recorded_at) VALUES (?, ?, ?, ?, ?)",
        grade_rows,
    )
    connection.executemany(
        "INSERT OR IGNORE INTO assignments "
        "(enrollment_id, term_id, title, due_date, max_points) VALUES (?, ?, ?, ?, ?)",
        assignment_rows,
    )

    assignment_records = connection.execute(
        "SELECT a.assignment_id, a.due_date FROM assignments AS a "
        "JOIN enrollments AS e ON e.enrollment_id = a.enrollment_id "
        "WHERE e.school_year = ? ORDER BY a.assignment_id",
        (school_year,),
    ).fetchall()
    submission_rows = []
    for assignment_id, due_date_text in assignment_records:
        due_date = date.fromisoformat(due_date_text)
        status = rng.choices(
            ("submitted", "late", "missing", "excused"),
            weights=(78, 12, 8, 2),
            k=1,
        )[0]
        submitted_at = None
        score = None
        if status != "missing":
            submitted_at = (due_date + timedelta(days=1 if status == "late" else -1)).isoformat()
            score = round(max(40, min(100, rng.gauss(84, 10))), 1)
        submission_rows.append((assignment_id, submitted_at, status, score))
    connection.executemany(
        "INSERT OR IGNORE INTO assignment_submissions "
        "(assignment_id, submitted_at, status, score) VALUES (?, ?, ?, ?)",
        submission_rows,
    )


def _seed_attendance(connection: sqlite3.Connection) -> None:
    rng = random.Random(29)
    today = date.today()
    attendance_rows = []
    for student_id in range(1, 121):
        for days_ago in range(120):
            attendance_date = today - timedelta(days=days_ago)
            if attendance_date.weekday() < 5:
                status = rng.choices(
                    ("present", "absent", "late", "excused"),
                    weights=(88, 5, 5, 2),
                    k=1,
                )[0]
                attendance_rows.append(
                    (student_id, attendance_date.isoformat(), status)
                )
    connection.executemany(
        "INSERT OR IGNORE INTO attendance "
        "(student_id, attendance_date, status) VALUES (?, ?, ?)",
        attendance_rows,
    )


def _seed_guardians_and_clubs(connection: sqlite3.Connection) -> None:
    guardian_first_names = ("Alex", "Jordan", "Taylor", "Morgan", "Riley", "Casey")
    connection.executemany(
        "INSERT OR IGNORE INTO guardians "
        "(guardian_id, first_name, last_name, email, phone) VALUES (?, ?, ?, ?, ?)",
        [
            (
                student_id,
                guardian_first_names[(student_id - 1) % len(guardian_first_names)],
                STUDENT_LAST_NAMES[(student_id * 7) % len(STUDENT_LAST_NAMES)],
                f"guardian{student_id:03d}@demo.school",
                f"555-01{student_id % 100:02d}",
            )
            for student_id in range(1, 121)
        ],
    )
    connection.executemany(
        "INSERT OR IGNORE INTO student_guardians "
        "(student_id, guardian_id, relationship, is_primary) VALUES (?, ?, ?, 1)",
        [(student_id, student_id, "Parent/Guardian") for student_id in range(1, 121)],
    )

    club_ids = [
        row[0]
        for row in connection.execute("SELECT club_id FROM clubs ORDER BY club_id")
    ]
    today = date.today()
    membership_rows = []
    for student_id in range(1, 121):
        first_club = (student_id - 1) % len(club_ids)
        second_club = (first_club + 2 + student_id % 3) % len(club_ids)
        membership_rows.extend(
            (
                student_id,
                club_ids[club_index],
                (today - timedelta(days=student_id % 180)).isoformat(),
                "Student Lead" if student_id % 17 == 0 else "Member",
            )
            for club_index in {first_club, second_club}
        )
    connection.executemany(
        "INSERT OR IGNORE INTO club_memberships "
        "(student_id, club_id, joined_on, role) VALUES (?, ?, ?, ?)",
        membership_rows,
    )


def _seed_database(connection: sqlite3.Connection) -> None:
    _insert_reference_data(connection)
    _seed_students(connection)
    today = date.today()
    school_year_start = today.year if today.month >= 8 else today.year - 1
    school_year = f"{school_year_start}-{school_year_start + 1}"
    _seed_enrollments(connection, school_year)
    _seed_academic_records(connection, school_year)
    _seed_attendance(connection)
    _seed_guardians_and_clubs(connection)
