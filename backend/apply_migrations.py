#!/usr/bin/env python3
"""
Apply new migrations to existing database
Run this script to add template tables without recreating the entire database
"""
import subprocess
import sys

def run_migration(migration_file, description):
    """Apply a single migration file"""
    print(f"\n📝 Applying {description}...")

    cmd = [
        "docker", "exec", "-i", "poster-postgres",
        "psql", "-U", "postgres", "-d", "poster_generation",
        "-f", f"/migrations/{migration_file}"
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=".")
        if result.returncode == 0:
            print(f"✓ {description} applied successfully")
            return True
        else:
            print(f"✗ Error applying {description}:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"✗ Failed to run migration: {e}")
        return False

def main():
    print("=" * 60)
    print("🔄 Applying Template Migrations to Existing Database")
    print("=" * 60)

    migrations = [
        ("003_create_templates_schema.sql", "Templates Schema (Migration 003)"),
        ("004_create_template_jobs_schema.sql", "Template Jobs Schema (Migration 004)")
    ]

    success_count = 0
    for migration_file, description in migrations:
        if run_migration(migration_file, description):
            success_count += 1

    print("\n" + "=" * 60)
    if success_count == len(migrations):
        print("✅ All migrations applied successfully!")
    else:
        print(f"⚠️  {success_count}/{len(migrations)} migrations applied")
        print("Some migrations failed. Check errors above.")

    # Verify tables
    print("\n Verifying new tables...")
    verify_cmd = [
        "docker", "exec", "-i", "poster-postgres",
        "psql", "-U", "postgres", "-d", "poster_generation",
        "-c", "\\dt"
    ]

    try:
        result = subprocess.run(verify_cmd, capture_output=True, text=True)
        if "templates" in result.stdout:
            print("\n✓ Template tables found:")
            for line in result.stdout.split('\n'):
                if any(word in line.lower() for word in ['template', 'poster_generation']):
                    print(f"  {line}")
        else:
            print("\n⚠️  Could not verify tables")
            print(result.stdout)
    except Exception as e:
        print(f"⚠️  Could not verify tables: {e}")

    print("=" * 60)

if __name__ == "__main__":
    main()
