## Problem
**CRITICAL**: No backup strategy exists. Complete data loss possible with no recovery mechanism.

**Current state:**
- No backup scripts
- No automated backups
- No documented recovery procedures
- No backup monitoring

## Risk
- Permanent data loss on failure
- No disaster recovery capability
- Compliance violations (if applicable)

## Implementation

### 1. Create Backup Script
File: `scripts/backup.sh`

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

mkdir -p "$BACKUP_DIR"

# PostgreSQL
echo "Backing up PostgreSQL..."
docker exec knowledgebase-postgres-1 pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} | \
  gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

# Neo4j
echo "Backing up Neo4j..."
docker exec knowledgebase-neo4j-1 neo4j-admin database backup neo4j \
  --to-path=/backups --overwrite-destination=true
docker cp knowledgebase-neo4j-1:/backups/neo4j.backup \
  "$BACKUP_DIR/neo4j_${TIMESTAMP}.backup"

# Qdrant
echo "Backing up Qdrant..."
docker exec knowledgebase-qdrant-1 curl -s http://localhost:6333/collections | \
  jq . > "$BACKUP_DIR/qdrant_${TIMESTAMP}.json"

# Cleanup old backups
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.backup" -mtime +$RETENTION_DAYS -delete

echo "Backup completed: $BACKUP_DIR"
ls -lh "$BACKUP_DIR" | tail -5
```

### 2. Create Restore Script
File: `scripts/restore.sh`

### 3. Setup Cron Job
```bash
# Add to crontab
0 2 * * * cd /root/KnowledgeBaseAI && make backup
```

### 4. Test Procedures
- [ ] Test backup script
- [ ] Test restore to separate environment
- [ ] Document recovery procedures
- [ ] Set up backup monitoring

### 5. Add to Makefile
```makefile
.PHONY: backup
backup:
	bash scripts/backup.sh

.PHONY: restore
restore:
	bash scripts/restore.sh $(BACKUP_FILE)
```

## Verification
```bash
# Test backup
make backup

# Verify backup files exist
ls -lh backups/

# Test restore (on dev environment)
make restore BACKUP_FILE=backups/postgres_20260201_020000.sql.gz
```

## Estimated Time
4-6 hours (including testing)

## References
- COMPREHENSIVE_TODO.md: DATA-001
