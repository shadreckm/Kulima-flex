"""Bootstrap / reset Kulima intelligence database."""

from kulima.db import IntelligenceRepository


if __name__ == "__main__":
    repo = IntelligenceRepository()
    print(f"Database ready at: {repo.db_path}")
    print("Schema: intelligence_runs + founders (legacy)")
