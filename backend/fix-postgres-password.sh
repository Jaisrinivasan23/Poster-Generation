#!/bin/sh
# Script to fix PostgreSQL password authentication

# Backup current pg_hba.conf
docker exec poster-postgres cp /var/lib/postgresql/data/pg_hba.conf /tmp/pg_hba.conf.bak

# Temporarily allow trust authentication
docker exec poster-postgres sh -c "echo 'local all all trust' > /var/lib/postgresql/data/pg_hba.conf"
docker exec poster-postgres sh -c "echo 'host all all all trust' >> /var/lib/postgresql/data/pg_hba.conf"

# Reload configuration
docker exec poster-postgres psql -U poster_user -d postgres -c "SELECT pg_reload_conf();"

# Set password with SCRAM-SHA-256
docker exec poster-postgres psql -U poster_user -d postgres -c "ALTER USER poster_user WITH PASSWORD '2005';"

# Restore original pg_hba.conf
docker exec poster-postgres cp /tmp/pg_hba.conf.bak /var/lib/postgresql/data/pg_hba.conf

# Reload configuration again
docker exec poster-postgres psql -U poster_user -d postgres -c "SELECT pg_reload_conf();"

echo "Password reset complete!"
echo "Now try connecting from pgAdmin with:"
echo "  Host: localhost"
echo "  Port: 5433"
echo "  Database: poster_generation"
echo "  Username: poster_user"
echo "  Password: 2005"
