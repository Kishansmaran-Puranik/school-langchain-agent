import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from school_db import initialize_database
from sql_agent import (
    build_conversation_messages,
    get_schema,
    run_query_tool,
    run_read_only_query,
)


class ReadOnlyQueryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "school.db"
        initialize_database(self.database_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_data_and_schema_are_available(self):
        schema = get_schema(self.database_path)
        self.assertIn("CREATE TABLE students", schema)
        self.assertIn("CREATE TABLE assignment_submissions", schema)
        self.assertIn("CREATE TABLE student_guardians", schema)
        result = run_read_only_query(
            self.database_path, "SELECT COUNT(*) AS student_count FROM students"
        )
        self.assertEqual(120, json.loads(result)["rows"][0]["student_count"])

    def test_school_tables_have_expanded_seed_data(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in (
                    "teachers",
                    "sections",
                    "subjects",
                    "enrollments",
                    "grades",
                    "attendance",
                    "guardians",
                    "student_guardians",
                    "school_terms",
                    "assignments",
                    "assignment_submissions",
                    "clubs",
                    "club_memberships",
                    "school_events",
                )
            }
        self.assertEqual(16, counts["teachers"])
        self.assertEqual(14, counts["sections"])
        self.assertEqual(10, counts["subjects"])
        self.assertEqual(1200, counts["enrollments"])
        self.assertEqual(7200, counts["grades"])
        self.assertEqual(120, counts["guardians"])
        self.assertEqual(counts["assignments"], counts["assignment_submissions"])
        self.assertGreater(counts["attendance"], 8000)
        self.assertGreater(counts["club_memberships"], 120)

    def test_expanded_school_data_supports_cross_table_reports(self):
        query = """
            SELECT s.grade_level, c.club_name, COUNT(*) AS members
            FROM club_memberships AS cm
            JOIN students AS s ON s.student_id = cm.student_id
            JOIN clubs AS c ON c.club_id = cm.club_id
            GROUP BY s.grade_level, c.club_id
            ORDER BY s.grade_level, members DESC
            LIMIT 10
        """
        payload = json.loads(run_read_only_query(self.database_path, query))
        self.assertEqual(10, len(payload["rows"]))
        self.assertIn("club_name", payload["columns"])

    def test_database_seeding_is_idempotent_and_restores_missing_tables(self):
        table_counts = {}
        with closing(sqlite3.connect(self.database_path)) as connection:
            for table in ("students", "enrollments", "grades", "assignments", "attendance"):
                table_counts[table] = connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
            connection.execute("PRAGMA foreign_keys = OFF")
            for table in (
                "club_memberships",
                "assignment_submissions",
                "student_guardians",
                "assignments",
                "clubs",
                "school_events",
                "school_terms",
                "guardians",
            ):
                connection.execute(f"DROP TABLE {table}")
            connection.commit()

        initialize_database(self.database_path)

        with closing(sqlite3.connect(self.database_path)) as connection:
            for table, expected_count in table_counts.items():
                actual_count = connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]
                self.assertEqual(expected_count, actual_count, table)
            self.assertGreater(
                connection.execute("SELECT COUNT(*) FROM assignment_submissions").fetchone()[0],
                0,
            )

    def test_select_query_returns_bounded_results(self):
        result = run_read_only_query(
            self.database_path,
            "SELECT students.student_id FROM students CROSS JOIN subjects "
            "ORDER BY students.student_id",
        )
        payload = json.loads(result)
        self.assertTrue(payload["truncated"])
        self.assertEqual(100, len(payload["rows"]))

    def test_supports_join_aggregation_cte_and_window_function_queries(self):
        query = """
            WITH student_averages AS (
                SELECT s.student_id, s.grade_level, AVG(g.score) AS average_score
                FROM students AS s
                JOIN enrollments AS e ON e.student_id = s.student_id
                JOIN grades AS g ON g.enrollment_id = e.enrollment_id
                GROUP BY s.student_id, s.grade_level
            )
            SELECT grade_level, student_id, ROUND(average_score, 1) AS average_score,
                   RANK() OVER (PARTITION BY grade_level ORDER BY average_score DESC) AS rank
            FROM student_averages
            ORDER BY grade_level, rank
            LIMIT 10
        """
        payload = json.loads(run_read_only_query(self.database_path, query))
        self.assertEqual(10, len(payload["rows"]))
        self.assertEqual(
            ["grade_level", "student_id", "average_score", "rank"],
            payload["columns"],
        )
        self.assertEqual(1, payload["rows"][0]["rank"])

    def test_rejects_write_and_multiple_statement_queries(self):
        for query in (
            "DELETE FROM students",
            "UPDATE students SET grade_level = 1",
            "SELECT 1; DELETE FROM students",
            "PRAGMA table_info(students)",
        ):
            with self.subTest(query=query), self.assertRaises((ValueError, sqlite3.DatabaseError)):
                run_read_only_query(self.database_path, query)

    def test_query_tool_returns_recoverable_error_feedback(self):
        error = run_query_tool(self.database_path, "SELECT unknown_column FROM students")
        self.assertIn("SQL query error", error)
        self.assertIn("no such column", error)
        self.assertIn("try a corrected read-only query", error)

    def test_follow_up_context_retains_recent_chat_turns(self):
        history = [
            {"role": "user", "content": "Which grade has the best attendance?"},
            {"role": "assistant", "content": "Grade 8 has the highest attendance at 94%."},
        ]
        messages = build_conversation_messages(
            "What about grade 7?", history, get_schema(self.database_path)
        )
        self.assertIn("Treat follow-up questions as part of the active conversation", messages[0].content)
        self.assertEqual(history[0]["content"], messages[1].content)
        self.assertEqual(history[1]["content"], messages[2].content)
        self.assertEqual("What about grade 7?", messages[-1].content)

    def test_database_remains_unchanged_after_rejected_queries(self):
        with self.assertRaises(ValueError):
            run_read_only_query(self.database_path, "DELETE FROM students")
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(120, connection.execute("SELECT COUNT(*) FROM students").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
