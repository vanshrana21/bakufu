"""
Add source_geometry_type column to ngdr_national.

Native point layers (~101 rows):
  - commodity_pan_india_mineral_map_ngdr (68)  [loaded as layer 'pan_india']
  - commodity_2m_gcs_ngdr (33)                 [loaded as layer 'commodity_2m']

Polygon layers converted to representative points (~521 rows):
  - exploration (483)
  - lease_auctioned (31)
  - lease_not_auctioned (7)

Note: the loader uses shapely's representative_point() rather than a true
centroid (a centroid can fall outside a concave polygon). The stored value is
'polygon_centroid' as specified, but the underlying geometry is an interior
representative point.

Idempotent: safe to re-run.
"""

from sqlalchemy import text

from src.db.session import get_engine

POLYGON_LAYERS = {"exploration", "lease_auctioned", "lease_not_auctioned"}


def migrate() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
            ALTER TABLE ngdr_national
            ADD COLUMN IF NOT EXISTS source_geometry_type VARCHAR(20);
        """
            )
        )
        result = conn.execute(
            text(
                """
            UPDATE ngdr_national
            SET source_geometry_type = CASE
                WHEN source_layer IN ('exploration', 'lease_auctioned', 'lease_not_auctioned')
                THEN 'polygon_centroid'
                ELSE 'point'
            END
            WHERE source_geometry_type IS NULL;
        """
            )
        )
        print(f"Updated {result.rowcount} rows")

        counts = conn.execute(
            text(
                """
            SELECT source_geometry_type, COUNT(*)
            FROM ngdr_national
            GROUP BY source_geometry_type
            ORDER BY source_geometry_type;
        """
            )
        ).fetchall()
        for gt, n in counts:
            print(f"  {gt}: {n}")


if __name__ == "__main__":
    migrate()
