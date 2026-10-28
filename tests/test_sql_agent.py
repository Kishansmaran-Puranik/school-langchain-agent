import json
import sqlite3
import unittest
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory

from school_db import initialize_database
from sql_agent import get_schema, run_query_tool, run_read_only_query


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
        result = run_read_only_query(
            self.database_path, "SELECT COUNT(*) AS student_count FROM students"
        )
        self.assertEqual(30, json.loads(result)["rows"][0]["student_count"])

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

    def test_database_remains_unchanged_after_rejected_queries(self):
        with self.assertRaises(ValueError):
            run_read_only_query(self.database_path, "DELETE FROM students")
        with closing(sqlite3.connect(self.database_path)) as connection:
            self.assertEqual(30, connection.execute("SELECT COUNT(*) FROM students").fetchone()[0])


if __name__ == "__main__":
    unittest.main()
