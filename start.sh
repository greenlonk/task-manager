#!/bin/bash

# Create/update database tables
python models.py

# Run the migration if needed (first time setup)
if [ ! -f ".migration_complete" ]; then
  python migrate_db.py
  touch .migration_complete
fi

# Start the application
uvicorn app:app --reload
