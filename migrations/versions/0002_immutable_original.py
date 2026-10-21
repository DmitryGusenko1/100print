"""Protect source text at the database boundary."""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE FUNCTION protect_memory_original() RETURNS trigger AS $$
        BEGIN
            IF NEW.original_text IS DISTINCT FROM OLD.original_text THEN
                RAISE EXCEPTION 'memory_items.original_text is immutable';
            END IF;
            NEW.updated_at := CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER memory_original_immutable BEFORE UPDATE ON memory_items
        FOR EACH ROW EXECUTE FUNCTION protect_memory_original()
    """)


def downgrade():
    op.execute("DROP TRIGGER memory_original_immutable ON memory_items")
    op.execute("DROP FUNCTION protect_memory_original()")
