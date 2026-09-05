"""Seed a deterministic build history for the capstone.

Every build lands inside the 14-day window ci.py queries, so the
numbers are the same whenever you run it.

    uv run python scripts/seed_builds.py builds.db
"""

import random
import sqlite3
import sys
import time

SERVICES = ["payments-api", "ledger", "gateway"]
TESTS = ["test_charge", "test_refund", "test_auth",
         "test_settle", "test_webhook", "test_retry"]


def seed(path: str) -> None:
    random.seed(20260728)
    now = int(time.time())
    con = sqlite3.connect(path)
    con.executescript(
        "DROP TABLE IF EXISTS builds; DROP TABLE IF EXISTS test_results;"
        "CREATE TABLE builds (id INTEGER PRIMARY KEY, service TEXT,"
        " branch TEXT, status TEXT, started_at INTEGER,"
        " duration_s INTEGER, commit_sha TEXT);"
        "CREATE TABLE test_results (build_id INTEGER, suite TEXT,"
        " name TEXT, status TEXT, duration_ms INTEGER);"
    )
    build_id = 0
    for service in SERVICES:
        for i in range(40):
            build_id += 1
            # 40 builds spread over 13 days: always inside the window
            started = now - (i * 7 + 2) * 3600
            failed = i % 5 == 0                      # exactly 20 percent
            con.execute(
                "INSERT INTO builds VALUES (?,?,?,?,?,?,?)",
                (build_id, service, "main" if i % 3 else "release",
                 "failed" if failed else "passed", started,
                 60 + (i * 17) % 840, f"{build_id:040x}"),
            )
            for t in random.sample(TESTS, 4):
                bad = failed and random.random() < 0.5
                con.execute(
                    "INSERT INTO test_results VALUES (?,?,?,?,?)",
                    (build_id, "integration", t,
                     "failed" if bad else "passed", 20 + build_id % 400),
                )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM builds").fetchone()[0]
    r = con.execute("SELECT COUNT(*) FROM test_results").fetchone()[0]
    con.close()
    print(f"seeded {path}: {n} builds, {r} test results")


if __name__ == "__main__":
    seed(sys.argv[1] if len(sys.argv) > 1 else "builds.db")
