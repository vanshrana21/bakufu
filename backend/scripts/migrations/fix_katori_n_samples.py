"""
Katori-Jhiriya is backed by 5 surface XRF samples (BR-2 through BR-6).
This sets n_samples=5 for that block.

Other blocks legitimately keep n_samples NULL because their priors
come from published literature aggregates, not counted samples.

Idempotent: safe to re-run.
"""

from sqlalchemy import text

from src.db.session import get_engine


def migrate() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text(
                """
            UPDATE block_grade_priors
            SET n_samples = 5
            WHERE block_name = 'KATORI-JHIRIYA'
              AND n_samples IS NULL;
        """
            )
        )
        print(f"Updated {result.rowcount} row(s) - Katori n_samples set to 5")

        rows = conn.execute(
            text(
                """
            SELECT block_name, prior_type, n_samples
            FROM block_grade_priors
            ORDER BY block_name;
        """
            )
        ).fetchall()
        print("\nCurrent prior_type / n_samples per block:")
        for name, ptype, n in rows:
            print(f"  {name}: {ptype}, n={n}")


if __name__ == "__main__":
    migrate()
