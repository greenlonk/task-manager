import os
from cron_descriptor import get_description

def basename(path):
    """Return the basename of a path"""
    return os.path.basename(path)

def cron_description(cron_expression):
    """Convert cron expression to human-readable description"""
    try:
        return get_description(cron_expression)
    except Exception:
        return "Invalid cron expression"

def register_filters(templates):
    """Register all custom filters with the app"""
    templates.env.filters['basename'] = basename
    templates.env.filters['cron_description'] = cron_description
