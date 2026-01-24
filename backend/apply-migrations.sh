#!/bin/bash
# Apply new migrations to existing database

echo "🔄 Applying migrations to existing database..."

# Apply templates schema (migration 003)
echo "📝 Applying migration 003: Templates schema..."
docker exec -i poster-postgres psql -U postgres -d poster_generation < migrations/003_create_templates_schema.sql

# Apply template jobs schema (migration 004)
echo "📝 Applying migration 004: Template jobs schema..."
docker exec -i poster-postgres psql -U postgres -d poster_generation < migrations/004_create_template_jobs_schema.sql

echo "✅ Migrations applied successfully!"
echo ""
echo "Verifying tables..."
docker exec -i poster-postgres psql -U postgres -d poster_generation -c "\dt" | grep -E "(templates|template_|poster_generations)"
