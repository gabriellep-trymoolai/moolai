#!/bin/bash
# MoolAI Client Backup Script

set -e
source .env

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating backup in $BACKUP_DIR..."

# Backup databases
docker-compose exec -T postgres-client pg_dump -U $DB_USER $DB_NAME_ORCHESTRATOR > "$BACKUP_DIR/orchestrator.sql"
docker-compose exec -T postgres-client pg_dump -U $DB_USER $DB_NAME_MONITORING > "$BACKUP_DIR/monitoring.sql"

# Backup Redis
docker-compose exec -T redis-client redis-cli --rdb "$BACKUP_DIR/redis.rdb" BGSAVE

# Backup configuration
cp .env "$BACKUP_DIR/.env"
cp -r config "$BACKUP_DIR/config" 2>/dev/null || true

echo "✅ Backup completed: $BACKUP_DIR"
