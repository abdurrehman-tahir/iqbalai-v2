"""Update library_items RLS to honour selection holders — T-055."""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "school_0031"
down_revision: str = "school_0030"
branch_labels: tuple[()] = ()
depends_on: str | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'school' AND table_name = 'library_items'"
        )
    ).scalar():
        return

    op.execute("DROP POLICY IF EXISTS library_items_isolation ON school.library_items")
    op.execute(
        """
        CREATE POLICY library_items_isolation ON school.library_items
        USING (
            current_setting('app.current_role', true) = 'platform_admin'
            OR (
                school_id = current_setting('app.current_school_id', true)
                AND (
                    visibility = 'school_public'
                    OR created_by = current_setting('app.current_user_id', true)
                    OR EXISTS (
                        SELECT 1 FROM school.library_item_selections sel
                        WHERE sel.library_item_id = library_items.id
                          AND sel.user_id = current_setting('app.current_user_id', true)
                          AND sel.deleted_at IS NULL
                    )
                )
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS library_items_isolation ON school.library_items")
    op.execute(
        """
        CREATE POLICY library_items_isolation ON school.library_items
        USING (
            current_setting('app.current_role', true) = 'platform_admin'
            OR (
                school_id = current_setting('app.current_school_id', true)
                AND (
                    visibility = 'school_public'
                    OR created_by = current_setting('app.current_user_id', true)
                )
            )
        )
        """
    )
