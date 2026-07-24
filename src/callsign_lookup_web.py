from flask import Flask, render_template_string, request, redirect, url_for, send_from_directory, flash, session
from flask_session import Session
import os
import sys
import sqlite3
import logging
from datetime import datetime, timedelta
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))
from modules.config import Config
from modules.database import CallsignLookupDatabase

app = Flask(__name__)
# Configure session to use filesystem
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_FILE_DIR'] = os.path.join(os.path.dirname(__file__), 'flask_session')
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
app.secret_key = 'dev-secret-key-backstop-radio'  # In production, use os.urandom(24)

# Initialize Flask-Session 
Session(app)

@app.before_request
def make_session_permanent():
    session.permanent = True

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize database
try:
    db = CallsignLookupDatabase(Config.DB_PATH)
    if not db.database_exists():
        logger.error("Database does not exist. Please run 'python callsign_lookup.py --update' to create and populate the database.")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    db = None

# Ensure the unified `licenses` view exists (e.g. for a database built before
# Canadian support was added) so country=ca|all queries work. Kept out of the
# init try/except above so a view hiccup can never null out `db`.
if db is not None and db.database_exists():
    try:
        db.create_views()
    except Exception as e:
        logger.warning(f"Could not (re)create views at startup: {e}")

def handle_database_error(func):
    """Decorator to handle database errors gracefully"""
    def wrapper(*args, **kwargs):
        try:
            if db is None:
                return render_template_string(ERROR_TEMPLATE, 
                    error="Database is not initialized",
                    solution="Please run 'python callsign_lookup.py --update' to create and populate the database.",
                    bootstrap_cdn=BOOTSTRAP_CDN,
                    favicon=FAVICON,
                    common_js=COMMON_JS
                )
            return func(*args, **kwargs)
        except sqlite3.Error as e:
            logger.error(f"Database error in {func.__name__}: {e}")
            return render_template_string(ERROR_TEMPLATE,
                error=f"Database error: {e}",
                solution="Please try again later or contact the administrator.",
                bootstrap_cdn=BOOTSTRAP_CDN,
                favicon=FAVICON,
                common_js=COMMON_JS
            )
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}")
            return render_template_string(ERROR_TEMPLATE,
                error=f"Unexpected error: {e}",
                solution="Please try again later or contact the administrator.",
                bootstrap_cdn=BOOTSTRAP_CDN,
                favicon=FAVICON,
                common_js=COMMON_JS
            )
    wrapper.__name__ = func.__name__
    return wrapper

# Add error template
ERROR_TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Error - Offline Callsign Lookup</title>
    {{ bootstrap_cdn|safe }}
    {{ favicon|safe }}
    {{ common_js|safe }}
</head>
<body class="bg-light">
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/"><i class="bi bi-broadcast"></i> Offline Callsign Lookup</a>
            <div class="d-flex">
                <button onclick="toggleTheme()" class="btn btn-outline-light" data-bs-toggle="tooltip" title="Toggle Theme (Ctrl+T)">
                    <i class="bi bi-circle-half"></i>
                </button>
            </div>
        </div>
    </nav>
    <div class="container py-5">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="card shadow-sm">
                    <div class="card-body text-center">
                        <i class="bi bi-exclamation-triangle text-warning display-1 mb-4"></i>
                        <h2 class="mb-4">Oops! Something went wrong</h2>
                        <p class="text-danger mb-3">{{ error }}</p>
                        <p class="text-muted mb-4">{{ solution }}</p>
                        <a href="/" class="btn btn-primary">
                            <i class="bi bi-house-door"></i> Return Home
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <footer class="footer mt-auto py-3 bg-light">
        <div class="container text-center">
            <span class="text-muted">© 2026 BackStop Radio LLC</span>
        </div>
    </footer>
</body>
</html>
'''

BOOTSTRAP_CDN = '''
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.7.2/font/bootstrap-icons.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
'''

FAVICON = '<link rel="icon" type="image/x-icon" href="/favicon.ico">'

COMMON_JS = '''
<script>
// Theme toggle
function toggleTheme() {
    const body = document.body;
    const isDark = body.classList.contains('dark-theme');
    body.classList.toggle('dark-theme');
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
}

// Initialize theme
document.addEventListener('DOMContentLoaded', () => {
    const savedTheme = localStorage.getItem('theme') || 'light';
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-theme');
    }
    
    // Initialize tooltips
    const tooltips = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltips.forEach(tooltip => new bootstrap.Tooltip(tooltip));
    
    // Handle keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            document.querySelector('input[name="callsign"]')?.focus();
        }
        if (e.ctrlKey && e.key === 't') {
            e.preventDefault();
            toggleTheme();
        }
    });
});

// Debounce function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
</script>
<style>
:root {
    --primary-color: #2563eb;
    --primary-hover: #1d4ed8;
    --border-light: rgba(0, 0, 0, 0.1);
    --border-dark: rgba(255, 255, 255, 0.1);
    --text-light: #1f2937;
    --text-dark: #e5e7eb;
    --text-muted-light: #6b7280;
    --text-muted-dark: #9ca3af;
}

body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: linear-gradient(to bottom, rgba(37, 99, 235, 0.02), rgba(37, 99, 235, 0.05));
}

.dark-theme body {
    background: linear-gradient(to bottom, rgba(15, 23, 42, 0.8), rgba(15, 23, 42, 0.9));
}

.search-form {
    max-width: 480px;
    margin: 2rem auto;
    animation: fadeIn 0.5s ease;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

.search-form .card {
    border: none;
    border-radius: 20px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 
                0 2px 4px -2px rgba(0, 0, 0, 0.1);
    background: rgba(255, 255, 255, 0.8);
    backdrop-filter: blur(10px);
    transition: all 0.3s ease;
}

.dark-theme .search-form .card {
    background: rgba(30, 41, 59, 0.8);
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2),
                0 2px 4px -2px rgba(0, 0, 0, 0.2);
}

.search-form .card:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1),
                0 4px 6px -4px rgba(0, 0, 0, 0.1);
}

.search-form .form-control {
    border-radius: 12px;
    padding: 14px 16px;
    font-size: 0.95rem;
    border: 1px solid var(--border-light);
    transition: all 0.2s ease;
    background-color: rgba(255, 255, 255, 0.9);
}

.dark-theme .search-form .form-control {
    background-color: rgba(15, 23, 42, 0.5);
    border-color: var(--border-dark);
    color: var(--text-dark);
}

.search-form .form-control:focus {
    box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
    border-color: var(--primary-color);
    background-color: #ffffff;
}

.dark-theme .search-form .form-control:focus {
    background-color: rgba(15, 23, 42, 0.7);
    box-shadow: 0 0 0 4px rgba(96, 165, 250, 0.15);
}

.search-shortcuts {
    position: absolute;
    right: 12px;
    top: 50%;
    transform: translateY(-50%);
    background: rgba(0, 0, 0, 0.05);
    padding: 4px 10px;
    border-radius: 8px;
    font-size: 0.75rem;
    color: var(--text-muted-light);
    pointer-events: none;
    transition: all 0.2s ease;
}

.dark-theme .search-shortcuts {
    background: rgba(255, 255, 255, 0.1);
    color: var(--text-muted-dark);
}

.form-label {
    font-weight: 600;
    margin-bottom: 0.75rem;
    font-size: 0.875rem;
    color: var(--text-light);
    transition: color 0.2s ease;
}

.dark-theme .form-label {
    color: var(--text-dark);
}

.search-btn {
    padding: 14px;
    font-weight: 600;
    font-size: 0.95rem;
    border-radius: 12px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    margin-top: 1.5rem;
    position: relative;
    overflow: hidden;
}

.search-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
}

.search-btn:active {
    transform: translateY(0);
}

.dark-theme .search-btn {
    background: #3b82f6;
    border-color: #3b82f6;
}

.dark-theme .search-btn:hover {
    background: #2563eb;
    border-color: #2563eb;
    box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
}

.advanced-filters-btn {
    color: var(--primary-color);
    text-decoration: none;
    font-size: 0.875rem;
    font-weight: 500;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 8px 0;
    margin-top: 0.5rem;
    transition: all 0.2s ease;
}

.dark-theme .advanced-filters-btn {
    color: #60a5fa;
}

.advanced-filters-btn:hover {
    color: var(--primary-hover);
    transform: translateX(4px);
}

.dark-theme .advanced-filters-btn:hover {
    color: #93c5fd;
}

.filter-panel {
    border-radius: 16px;
    margin-top: 1rem;
    transition: all 0.3s ease;
}

.filter-panel .card {
    border-radius: 16px;
    border: none;
    background: rgba(0, 0, 0, 0.02);
    box-shadow: none;
}

.dark-theme .filter-panel .card {
    background: rgba(255, 255, 255, 0.03);
}

.filter-panel .form-select {
    border-radius: 12px;
    padding: 14px 16px;
    font-size: 0.95rem;
    background-position: right 16px center;
    border: 1px solid var(--border-light);
    transition: all 0.2s ease;
}

.dark-theme .filter-panel .form-select {
    background-color: rgba(15, 23, 42, 0.5);
    border-color: var(--border-dark);
    color: var(--text-dark);
}

.navbar {
    background: rgba(255, 255, 255, 0.9) !important;
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border-light);
    padding: 1rem 0;
    transition: all 0.3s ease;
}

.dark-theme .navbar {
    background: rgba(15, 23, 42, 0.9) !important;
    border-bottom: 1px solid var(--border-dark);
}

.navbar-brand {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    transition: all 0.2s ease;
}

.navbar-brand i {
    font-size: 1.1em;
    margin-right: 0.75rem;
    vertical-align: -0.1em;
    transition: transform 0.3s ease;
}

.navbar-brand:hover i {
    transform: rotate(-15deg);
}

.theme-toggle {
    width: 42px;
    height: 42px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 1px solid rgba(37, 99, 235, 0.1);
    background: transparent;
    color: var(--primary-color);
    transition: all 0.3s ease;
}

.theme-toggle:hover {
    background: rgba(37, 99, 235, 0.05);
    transform: rotate(180deg);
}

.dark-theme .theme-toggle {
    color: #60a5fa;
    border-color: rgba(96, 165, 250, 0.2);
}

.dark-theme .theme-toggle:hover {
    background: rgba(96, 165, 250, 0.1);
}

.keyboard-shortcuts {
    text-align: center;
    margin-top: 1.5rem;
    font-size: 0.875rem;
    color: var(--text-muted-light);
    transition: color 0.2s ease;
}

.dark-theme .keyboard-shortcuts {
    color: var(--text-muted-dark);
}

.loading {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(to right, var(--primary-color), #60a5fa);
    display: none;
    animation: loading 1s infinite linear;
    z-index: 1000;
}

@keyframes loading {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

.footer {
    margin-top: auto;
    padding: 2rem 0;
    opacity: 0.8;
    transition: opacity 0.2s ease;
}

.footer:hover {
    opacity: 1;
}

.footer .text-muted {
    font-size: 0.875rem;
}
</style>
'''

# Add common CSS variables
COMMON_CSS = """
<style>
:root {
    --primary-color: #2563eb;
    --primary-hover: #1d4ed8;
    --background-light: #ffffff;
    --background-dark: #1a1a1a;
    --text-primary-light: #1a1a1a;
    --text-primary-dark: #ffffff;
    --text-muted-light: #666666;
    --text-muted-dark: #a3a3a3;
    --border-light: #e5e5e5;
    --border-dark: #333333;
}

/* Recent Search Pills */
.recent-search-pill {
    display: inline-flex;
    align-items: center;
    padding: 0.5rem 1rem;
    background: linear-gradient(to right, rgba(37, 99, 235, 0.05), rgba(37, 99, 235, 0.1));
    border: 1px solid rgba(37, 99, 235, 0.1);
    border-radius: 9999px;
    color: var(--text-primary-light);
    text-decoration: none;
    font-size: 0.875rem;
    transition: all 0.2s ease;
    margin: 0.25rem;
}

.dark-theme .recent-search-pill {
    background: linear-gradient(to right, rgba(59, 130, 246, 0.05), rgba(59, 130, 246, 0.1));
    border-color: rgba(59, 130, 246, 0.1);
    color: var(--text-primary-dark);
}

.recent-search-pill:hover {
    background: linear-gradient(to right, rgba(37, 99, 235, 0.1), rgba(37, 99, 235, 0.15));
    border-color: rgba(37, 99, 235, 0.2);
    transform: translateY(-1px);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    color: var(--text-primary-light);
    text-decoration: none;
}

.dark-theme .recent-search-pill:hover {
    background: linear-gradient(to right, rgba(59, 130, 246, 0.1), rgba(59, 130, 246, 0.15));
    border-color: rgba(59, 130, 246, 0.2);
    color: var(--text-primary-dark);
}

.recent-search-pill i {
    margin-right: 0.5rem;
    font-size: 0.75rem;
}

.recent-search-pill i:last-child {
    margin-right: 0;
    margin-left: 0.5rem;
}

.recent-search-pills {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
    margin-top: 1rem;
}

.recent-searches h5 {
    color: var(--text-muted-light);
    font-size: 0.875rem;
    font-weight: 600;
    margin-bottom: 0.75rem;
    display: flex;
    align-items: center;
    justify-content: center;
}

.dark-theme .recent-searches h5 {
    color: var(--text-muted-dark);
}

.recent-searches {
    background: linear-gradient(to right, rgba(37, 99, 235, 0.02), rgba(37, 99, 235, 0.04));
    border: 1px solid rgba(37, 99, 235, 0.06);
    border-radius: 12px;
    padding: 1.25rem;
    margin-bottom: 2rem;
}

.dark-theme .recent-searches {
    background: linear-gradient(to right, rgba(59, 130, 246, 0.02), rgba(59, 130, 246, 0.04));
    border-color: rgba(59, 130, 246, 0.06);
}

/* Base Styles */
body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    background: linear-gradient(to bottom, rgba(37, 99, 235, 0.02), rgba(37, 99, 235, 0.05));
}

.dark-theme body {
    background: linear-gradient(to bottom, rgba(15, 23, 42, 0.8), rgba(15, 23, 42, 0.9));
}

.navbar {
    background: rgba(255, 255, 255, 0.9) !important;
    backdrop-filter: blur(10px);
    border-bottom: 1px solid var(--border-light);
    padding: 1rem 0;
    transition: all 0.3s ease;
}

.dark-theme .navbar {
    background: rgba(15, 23, 42, 0.9) !important;
    border-bottom: 1px solid var(--border-dark);
}

.navbar-brand {
    font-size: 1.25rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    transition: all 0.2s ease;
}

.navbar-brand i {
    font-size: 1.1em;
    margin-right: 0.75rem;
    vertical-align: -0.1em;
    transition: transform 0.3s ease;
}

.navbar-brand:hover i {
    transform: rotate(-15deg);
}

.theme-toggle {
    width: 42px;
    height: 42px;
    padding: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    border: 1px solid rgba(37, 99, 235, 0.1);
    background: transparent;
    color: var(--primary-color);
    transition: all 0.3s ease;
}

.theme-toggle:hover {
    background: rgba(37, 99, 235, 0.05);
    transform: rotate(180deg);
}

.dark-theme .theme-toggle {
    color: #60a5fa;
    border-color: rgba(96, 165, 250, 0.2);
}

.dark-theme .theme-toggle:hover {
    background: rgba(96, 165, 250, 0.1);
}

.loading {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 3px;
    background: linear-gradient(to right, var(--primary-color), #60a5fa);
    display: none;
    animation: loading 1s infinite linear;
    z-index: 1000;
}

@keyframes loading {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

.footer {
    margin-top: auto;
    padding: 2rem 0;
    opacity: 0.8;
    transition: opacity 0.2s ease;
}

.footer:hover {
    opacity: 1;
}

.footer .text-muted {
    font-size: 0.875rem;
}
</style>
"""

SEARCH_FORM = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Offline Callsign Lookup</title>
    {{ bootstrap_cdn|safe }}
    {{ favicon|safe }}
    {{ common_js|safe }}
    {{ common_css|safe }}
    <style>
    .hero {
        min-height: 100vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        padding: 2rem;
        background: linear-gradient(135deg, rgba(37, 99, 235, 0.02) 0%, rgba(37, 99, 235, 0.05) 100%);
        position: relative;
        overflow: hidden;
    }

    .hero::before {
        content: "";
        position: absolute;
        width: 200%;
        height: 200%;
        top: -50%;
        left: -50%;
        z-index: 0;
        background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%232563eb' fill-opacity='0.02'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
        animation: patternMove 60s linear infinite;
    }

    @keyframes patternMove {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .dark-theme .hero::before {
        opacity: 0.5;
    }

    .search-container {
        max-width: 800px;
        width: 100%;
        position: relative;
        z-index: 1;
    }

    .search-card {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 24px;
        border: none;
        backdrop-filter: blur(10px);
        box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.1);
        transition: all 0.3s ease;
        overflow: hidden;
    }

    .dark-theme .search-card {
        background: rgba(30, 41, 59, 0.8);
        box-shadow: 0 10px 40px -10px rgba(0, 0, 0, 0.2);
    }

    .search-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.2);
    }

    .dark-theme .search-card:hover {
        box-shadow: 0 20px 40px -10px rgba(0, 0, 0, 0.3);
    }

    .search-header {
        padding: 2rem;
        text-align: center;
        border-bottom: 1px solid rgba(0, 0, 0, 0.05);
    }

    .dark-theme .search-header {
        border-bottom-color: rgba(255, 255, 255, 0.05);
    }

    .search-title {
        font-size: 2.5rem;
        font-weight: 800;
        margin-bottom: 1rem;
        background: linear-gradient(45deg, #2563eb, #3b82f6);
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradientShift 8s ease infinite;
        background-size: 200% auto;
    }

    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .dark-theme .search-title {
        background: linear-gradient(45deg, #60a5fa, #93c5fd);
        background-clip: text;
        -webkit-background-clip: text;
    }

    .search-subtitle {
        font-size: 1.1rem;
        color: var(--text-muted-light);
        max-width: 600px;
        margin: 0 auto;
    }

    .dark-theme .search-subtitle {
        color: var(--text-muted-dark);
    }

    .search-form {
        padding: 2rem;
    }

    .form-floating {
        margin-bottom: 1.5rem;
        position: relative;
    }

    .form-floating > .form-control,
    .form-floating > .form-select {
        border-radius: 12px;
        border: 1px solid rgba(0, 0, 0, 0.1);
        padding: 1.5rem 1rem 0.5rem;
        height: calc(3.5rem + 2px);
        font-size: 1rem;
        background: rgba(255, 255, 255, 0.9);
        transition: all 0.2s ease;
    }

    .dark-theme .form-floating > .form-control,
    .dark-theme .form-floating > .form-select {
        background: rgba(15, 23, 42, 0.5);
        border-color: rgba(255, 255, 255, 0.1);
        color: var(--text-dark);
    }

    .form-floating > .form-control:focus,
    .form-floating > .form-select:focus {
        border-color: #2563eb;
        box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
    }

    .dark-theme .form-floating > .form-control:focus,
    .dark-theme .form-floating > .form-select:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.15);
    }

    .form-floating > label {
        padding: 0.75rem 1rem;
        color: var(--text-muted-light);
        font-weight: 500;
        font-size: 0.9rem;
        transform-origin: 0 0;
        transition: opacity .1s ease-in-out, transform .1s ease-in-out;
    }

    .dark-theme .form-floating > label {
        color: var(--text-muted-dark);
    }

    .form-floating > .form-control:focus ~ label,
    .form-floating > .form-control:not(:placeholder-shown) ~ label,
    .form-floating > .form-select ~ label {
        transform: scale(0.85) translateY(-0.5rem);
        opacity: 0.8;
    }

    .keyboard-shortcut {
        position: absolute;
        top: 0.5rem;
        right: 0.75rem;
        background: rgba(0, 0, 0, 0.05);
        padding: 0.15rem 0.4rem;
        border-radius: 4px;
        font-size: 0.7rem;
        color: var(--text-muted-light);
        font-weight: normal;
        z-index: 3;
    }

    .dark-theme .keyboard-shortcut {
        background: rgba(255, 255, 255, 0.1);
        color: var(--text-muted-dark);
    }

    .search-btn {
        width: 100%;
        padding: 1rem;
        font-size: 1.1rem;
        font-weight: 600;
        border-radius: 12px;
        background: linear-gradient(45deg, #2563eb, #3b82f6);
        border: none;
        color: white;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }

    .dark-theme .search-btn {
        background: linear-gradient(45deg, #3b82f6, #60a5fa);
    }

    .search-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px -5px rgba(37, 99, 235, 0.3);
    }

    .dark-theme .search-btn:hover {
        box-shadow: 0 10px 20px -5px rgba(59, 130, 246, 0.3);
    }

    .search-btn:active {
        transform: translateY(0);
    }

    .search-btn:disabled {
        opacity: 0.7;
        cursor: not-allowed;
        transform: none;
    }

    .search-btn .spinner-border {
        display: none;
        width: 1.2rem;
        height: 1.2rem;
        margin-left: 0.5rem;
    }

    .search-btn.loading .spinner-border {
        display: inline-block;
    }

    .search-tips {
        background: rgba(255, 255, 255, 0.9);
        border-radius: 12px;
        margin: 1.5rem 0 0;
        border: 1px solid rgba(37, 99, 235, 0.1);
        transition: all 0.3s ease;
        max-height: 0;
        overflow: hidden;
        opacity: 0;
        transform: translateY(-10px);
    }

    .dark-theme .search-tips {
        background: rgba(15, 23, 42, 0.5);
        border-color: rgba(96, 165, 250, 0.1);
    }

    .search-tips.show {
        max-height: 500px;
        opacity: 1;
        transform: translateY(0);
        padding: 1.5rem;
    }

    .search-tips-toggle {
        background: none;
        border: none;
        color: #2563eb;
        padding: 0.75rem 1.25rem;
        font-size: 0.9rem;
        font-weight: 500;
        display: flex;
        align-items: center;
        margin: 0 auto;
        cursor: pointer;
        transition: all 0.2s ease;
        border-radius: 100px;
        background: rgba(37, 99, 235, 0.05);
    }

    .dark-theme .search-tips-toggle {
        color: #60a5fa;
        background: rgba(96, 165, 250, 0.05);
    }

    .search-tips-toggle:hover {
        background: rgba(37, 99, 235, 0.1);
    }

    .dark-theme .search-tips-toggle:hover {
        background: rgba(96, 165, 250, 0.1);
    }

    .search-tips-toggle i {
        margin-right: 0.75rem;
        transition: transform 0.3s ease;
        font-size: 1rem;
    }

    .search-tips-toggle.active {
        background: rgba(37, 99, 235, 0.1);
    }

    .dark-theme .search-tips-toggle.active {
        background: rgba(96, 165, 250, 0.1);
    }

    .search-tips-toggle.active i {
        transform: rotate(180deg);
    }

    .search-tips-content {
        display: grid;
        gap: 1rem;
    }

    .search-tips h5 {
        font-size: 1rem;
        font-weight: 600;
        color: var(--text-light);
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .dark-theme .search-tips h5 {
        color: var(--text-dark);
    }

    .search-tips h5 i {
        color: #2563eb;
        font-size: 1.1em;
    }

    .dark-theme .search-tips h5 i {
        color: #60a5fa;
    }

    .search-tips-list {
        list-style: none;
        padding: 0;
        margin: 0;
        display: grid;
        gap: 0.75rem;
    }

    .search-tips-list li {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        padding: 0.75rem;
        background: rgba(37, 99, 235, 0.03);
        border-radius: 8px;
        transition: all 0.2s ease;
    }

    .dark-theme .search-tips-list li {
        background: rgba(96, 165, 250, 0.03);
    }

    .search-tips-list li:hover {
        background: rgba(37, 99, 235, 0.05);
        transform: translateX(4px);
    }

    .dark-theme .search-tips-list li:hover {
        background: rgba(96, 165, 250, 0.05);
    }

    .search-tips-list li i {
        color: #2563eb;
        font-size: 1rem;
        margin-top: 0.2rem;
    }

    .dark-theme .search-tips-list li i {
        color: #60a5fa;
    }

    .recent-searches {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1rem;
        padding: 1rem;
        background: rgba(37, 99, 235, 0.03);
        border-radius: 12px;
        border: 1px solid rgba(37, 99, 235, 0.1);
    }

    .recent-search-pill {
        background: white;
        color: #2563eb;
        border: 1px solid rgba(37, 99, 235, 0.2);
        padding: 0.5rem 1rem;
        border-radius: 100px;
        font-size: 0.9rem;
        cursor: pointer;
        transition: all 0.2s ease;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
    }

    .dark-theme .recent-search-pill {
        background: rgba(15, 23, 42, 0.5);
        color: #60a5fa;
        border-color: rgba(96, 165, 250, 0.2);
    }

    .recent-search-pill:hover {
        background: rgba(37, 99, 235, 0.1);
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
    }

    .dark-theme .recent-search-pill:hover {
        background: rgba(59, 130, 246, 0.2);
    }

    .recent-search-pill i {
        font-size: 0.8rem;
        opacity: 0.8;
    }

    .recent-searches-header {
        width: 100%;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        color: var(--text-muted-light);
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
    }

    .dark-theme .recent-searches-header {
        color: var(--text-muted-dark);
    }

    .state-select-container {
        position: relative;
    }

    .state-select-search {
        position: absolute;
        top: 100%;
        left: 0;
        right: 0;
        background: white;
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 12px;
        margin-top: 0.5rem;
        padding: 0.5rem;
        display: none;
        z-index: 1000;
        max-height: 300px;
        overflow-y: auto;
    }

    .dark-theme .state-select-search {
        background: rgba(15, 23, 42, 0.9);
        border-color: rgba(255, 255, 255, 0.1);
    }

    .state-select-search.show {
        display: block;
    }

    .state-option {
        padding: 0.5rem;
        cursor: pointer;
        border-radius: 6px;
        transition: all 0.2s ease;
    }

    .state-option:hover {
        background: rgba(37, 99, 235, 0.1);
    }

    .dark-theme .state-option:hover {
        background: rgba(59, 130, 246, 0.1);
    }
    </style>
</head>
<body>
    <div class="hero">
        <div class="search-container">
            <div class="search-card">
                <div class="search-header">
                    <h1 class="search-title">Offline Callsign Lookup</h1>
                    <p class="search-subtitle">Search for amateur radio operators by callsign, name, or location</p>
                </div>
                <form class="search-form" id="searchForm" method="get" action="/search">
                    <div class="form-floating">
                        <input type="text" class="form-control" id="callsign" name="callsign" placeholder="Callsign"
                               value="{{ callsign if callsign else '' }}" autocomplete="off">
                        <label for="callsign">Callsign</label>
                        <span class="keyboard-shortcut">Alt + C</span>
                    </div>
                    <div class="form-floating">
                        <input type="text" class="form-control" id="name" name="name" placeholder="Name"
                               value="{{ name if name else '' }}" autocomplete="off">
                        <label for="name">Name</label>
                        <span class="keyboard-shortcut">Alt + N</span>
                    </div>
                    <div class="form-floating">
                        <select class="form-select" id="country" name="country">
                            {% for c_code, c_name in country_options.items() %}
                            <option value="{{ c_code }}" {{ 'selected' if country == c_code else '' }}>
                                {{ c_name }}
                            </option>
                            {% endfor %}
                        </select>
                        <label for="country">Country</label>
                    </div>
                    <div class="form-floating state-select-container">
                        <select class="form-select" id="state" name="state">
                            <option value="">All States / Provinces</option>
                            {% for state_code, state_name in states.items() %}
                            <option value="{{ state_code }}" {{ 'selected' if state == state_code else '' }}>
                                {{ state_name }}
                            </option>
                            {% endfor %}
                        </select>
                        <label for="state">State / Province</label>
                        <span class="keyboard-shortcut">Alt + S</span>
                        <div class="state-select-search" id="stateSearch">
                            <input type="text" class="form-control mb-2" id="stateSearchInput" placeholder="Search states...">
                            <div id="stateOptions"></div>
                        </div>
                    </div>
                    <button type="submit" class="search-btn" id="searchBtn">
                        <i class="fas fa-search"></i> Search
                        <div class="spinner-border spinner-border-sm" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </button>
                </form>

                {% if recent_searches %}
                <div class="px-4 pb-4">
                    <div class="recent-searches">
                        <div class="recent-searches-header">
                            <i class="bi bi-clock-history"></i>
                            Recent Searches
                        </div>
                        {% for search in recent_searches %}
                        <button type="button" class="recent-search-pill" 
                                data-callsign="{{ search.params.get('callsign', '') }}"
                                data-name="{{ search.params.get('name', '') }}"
                                data-state="{{ search.params.get('state', '') }}">
                            <i class="bi bi-search"></i>
                            {% if search.params.get('callsign') %}{{ search.params.get('callsign') }}{% endif %}
                            {% if search.params.get('name') %}{{ search.params.get('name') }}{% endif %}
                            {% if search.params.get('state') %}({{ search.params.get('state') }}){% endif %}
                        </button>
                        {% endfor %}
                    </div>
                </div>
                {% endif %}

                <div class="px-4 pb-4">
                    <button type="button" class="search-tips-toggle" id="searchTipsToggle">
                        <i class="bi bi-lightbulb"></i>
                        Search Tips
                    </button>
                    <div class="search-tips" id="searchTips">
                        <div class="search-tips-content">
                            <h5>
                                <i class="bi bi-info-circle"></i>
                                How to Search Effectively
                            </h5>
                            <ul class="search-tips-list">
                                <li>
                                    <i class="bi bi-broadcast"></i>
                                    <span>Enter a callsign (e.g. KD2PPR) for exact matches</span>
                                </li>
                                <li>
                                    <i class="bi bi-person"></i>
                                    <span>Search by full or partial name</span>
                                </li>
                                <li>
                                    <i class="bi bi-geo-alt"></i>
                                    <span>Filter by state using the searchable dropdown</span>
                                </li>
                                <li>
                                    <i class="bi bi-keyboard"></i>
                                    <span>Use keyboard shortcuts (Alt + C/N/S) for quick navigation</span>
                                </li>
                                <li>
                                    <i class="bi bi-clock-history"></i>
                                    <span>Click on recent searches to quickly repeat them</span>
                                </li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', function() {
        // Keyboard shortcuts
        document.addEventListener('keydown', function(e) {
            if (e.altKey) {
                switch(e.key.toLowerCase()) {
                    case 'c':
                        e.preventDefault();
                        document.getElementById('callsign').focus();
                        break;
                    case 'n':
                        e.preventDefault();
                        document.getElementById('name').focus();
                        break;
                    case 's':
                        e.preventDefault();
                        document.getElementById('state').focus();
                        break;
                }
            }
        });

        // Search tips toggle
        const searchTipsToggle = document.getElementById('searchTipsToggle');
        const searchTips = document.getElementById('searchTips');
        const searchTipsState = localStorage.getItem('searchTipsVisible') === 'true';

        if (searchTipsState) {
            searchTips.classList.add('show');
            searchTipsToggle.classList.add('active');
        }

        searchTipsToggle.addEventListener('click', function() {
            searchTips.classList.toggle('show');
            this.classList.toggle('active');
            localStorage.setItem('searchTipsVisible', searchTips.classList.contains('show'));
        });

        // Form submission loading state
        const searchForm = document.getElementById('searchForm');
        const searchBtn = document.getElementById('searchBtn');

        searchForm.addEventListener('submit', function() {
            searchBtn.classList.add('loading');
            searchBtn.disabled = true;
        });

        // Recent searches
        document.querySelectorAll('.recent-search-pill').forEach(pill => {
            pill.addEventListener('click', function() {
                const callsign = this.dataset.callsign;
                const name = this.dataset.name;
                const state = this.dataset.state;

                document.getElementById('callsign').value = callsign || '';
                document.getElementById('name').value = name || '';
                document.getElementById('state').value = state || '';

                // Add loading state to button
                this.style.opacity = '0.7';
                this.style.pointerEvents = 'none';
                
                // Submit the form
                document.getElementById('searchForm').submit();
            });
        });

        // Enhanced state selection
        const stateSelect = document.getElementById('state');
        const stateSearch = document.getElementById('stateSearch');
        const stateSearchInput = document.getElementById('stateSearchInput');
        const stateOptions = document.getElementById('stateOptions');
        const states = {{ states|tojson|safe }};

        stateSelect.addEventListener('click', function(e) {
            e.preventDefault();
            stateSearch.classList.add('show');
            stateSearchInput.focus();
        });

        document.addEventListener('click', function(e) {
            if (!stateSearch.contains(e.target) && e.target !== stateSelect) {
                stateSearch.classList.remove('show');
            }
        });

        function renderStateOptions(filter = '') {
            stateOptions.innerHTML = '';
            Object.entries(states)
                .filter(([code, name]) => 
                    name.toLowerCase().includes(filter.toLowerCase()) ||
                    code.toLowerCase().includes(filter.toLowerCase())
                )
                .forEach(([code, name]) => {
                    const option = document.createElement('div');
                    option.className = 'state-option';
                    option.textContent = `${name} (${code})`;
                    option.addEventListener('click', () => {
                        stateSelect.value = code;
                        stateSearch.classList.remove('show');
                    });
                    stateOptions.appendChild(option);
                });
        }

        stateSearchInput.addEventListener('input', function() {
            renderStateOptions(this.value);
        });

        renderStateOptions();
    });
    </script>
</body>
</html>
'''

RESULTS_TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Search Results</title>
    {{ bootstrap_cdn|safe }}
    {{ favicon|safe }}
    {{ common_js|safe }}
    {{ common_css|safe }}
    <style>
    .results-container {
        animation: fadeIn 0.5s ease;
    }

    .results-header {
        margin-bottom: 2rem;
        padding: 1.5rem;
        background: rgba(255, 255, 255, 0.8);
        border-radius: 20px;
        backdrop-filter: blur(10px);
        border: 1px solid var(--border-light);
        transition: all 0.3s ease;
    }

    .dark-theme .results-header {
        background: rgba(30, 41, 59, 0.8);
        border-color: var(--border-dark);
    }

    .results-title {
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0;
        color: var(--text-light);
        transition: color 0.2s ease;
    }

    .dark-theme .results-title {
        color: var(--text-dark);
    }

    .view-toggle-btn {
        width: 42px;
        height: 42px;
        padding: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 12px;
        transition: all 0.3s ease;
    }

    .view-toggle-btn:hover {
        transform: translateY(-2px);
    }

    .view-toggle-btn.active {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: white;
    }

    .dark-theme .view-toggle-btn.active {
        background: #3b82f6;
        border-color: #3b82f6;
    }

    .filters-card {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 20px;
        border: none;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
        margin-bottom: 2rem;
    }

    .dark-theme .filters-card {
        background: rgba(30, 41, 59, 0.8);
    }

    .filters-card .form-select {
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 0.95rem;
        border: 1px solid var(--border-light);
        background-position: right 16px center;
        transition: all 0.2s ease;
    }

    .dark-theme .filters-card .form-select {
        background-color: rgba(15, 23, 42, 0.5);
        border-color: var(--border-dark);
        color: var(--text-dark);
    }

    .filters-card .form-select:focus {
        box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.15);
        border-color: var(--primary-color);
    }

    .dark-theme .filters-card .form-select:focus {
        box-shadow: 0 0 0 4px rgba(96, 165, 250, 0.15);
    }

    .table {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 20px;
        overflow: hidden;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }

    .dark-theme .table {
        background: rgba(30, 41, 59, 0.8);
        color: var(--text-dark);
    }

    .table th {
        font-weight: 600;
        font-size: 0.875rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 1rem;
        background: rgba(0, 0, 0, 0.02);
        border-bottom: 1px solid var(--border-light);
    }

    .dark-theme .table th {
        background: rgba(255, 255, 255, 0.02);
        border-bottom-color: var(--border-dark);
        color: var(--text-dark);
    }

    .table td {
        padding: 1rem;
        vertical-align: middle;
        border-bottom: 1px solid var(--border-light);
        font-size: 0.95rem;
    }

    .dark-theme .table td {
        border-bottom-color: var(--border-dark);
    }

    .table tr:last-child td {
        border-bottom: none;
    }

    .table tr:hover {
        background: rgba(37, 99, 235, 0.05);
    }

    .dark-theme .table tr:hover {
        background: rgba(96, 165, 250, 0.05);
    }

    .table a {
        color: var(--primary-color);
        text-decoration: none;
        font-weight: 500;
        transition: all 0.2s ease;
    }

    .dark-theme .table a {
        color: #60a5fa;
    }

    .table a:hover {
        color: var(--primary-hover);
    }

    .dark-theme .table a:hover {
        color: #93c5fd;
    }

    .badge {
        font-weight: 600;
        padding: 0.5rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        letter-spacing: 0.025em;
        text-transform: uppercase;
    }

    .badge.bg-success {
        background: rgba(5, 150, 105, 0.1) !important;
        color: #059669;
        border: 1px solid rgba(5, 150, 105, 0.2);
    }

    .dark-theme .badge.bg-success {
        background: rgba(5, 150, 105, 0.2) !important;
        color: #34d399;
        border-color: rgba(52, 211, 153, 0.2);
    }

    .badge.bg-secondary {
        background: rgba(156, 163, 175, 0.1) !important;
        color: #6b7280;
        border: 1px solid rgba(156, 163, 175, 0.2);
    }

    .dark-theme .badge.bg-secondary {
        background: rgba(156, 163, 175, 0.2) !important;
        color: #9ca3af;
        border-color: rgba(156, 163, 175, 0.2);
    }

    .badge.bg-info {
        background: rgba(37, 99, 235, 0.1) !important;
        color: #2563eb;
        border: 1px solid rgba(37, 99, 235, 0.2);
    }

    .dark-theme .badge.bg-info {
        background: rgba(59, 130, 246, 0.2) !important;
        color: #60a5fa;
        border-color: rgba(96, 165, 250, 0.2);
    }

    .licensee-card {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 20px;
        border: none;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }

    .dark-theme .licensee-card {
        background: rgba(30, 41, 59, 0.8);
    }

    .licensee-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 20px -8px rgba(0, 0, 0, 0.1);
    }

    .dark-theme .licensee-card:hover {
        box-shadow: 0 12px 20px -8px rgba(0, 0, 0, 0.2);
    }

    .licensee-card .card-title {
        font-size: 1.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        color: var(--primary-color);
    }

    .dark-theme .licensee-card .card-title {
        color: #60a5fa;
    }

    .licensee-card .card-subtitle {
        font-size: 1rem;
        margin-bottom: 1rem;
    }

    .pagination {
        margin-top: 2rem;
        justify-content: center;
    }

    .pagination .page-link {
        border-radius: 12px;
        margin: 0 0.25rem;
        padding: 0.75rem 1rem;
        border: 1px solid var(--border-light);
        color: var(--text-light);
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        transition: all 0.2s ease;
    }

    .dark-theme .pagination .page-link {
        background: rgba(30, 41, 59, 0.8);
        border-color: var(--border-dark);
        color: var(--text-dark);
    }

    .pagination .page-link:hover {
        background: var(--primary-color);
        color: white;
        border-color: var(--primary-color);
        transform: translateY(-2px);
    }

    .dark-theme .pagination .page-item.active .page-link {
        background: var(--primary-color);
        border-color: var(--primary-color);
        color: white;
        font-weight: 600;
    }

    .dark-theme .pagination .page-item.active .page-link {
        background: #3b82f6;
        border-color: #3b82f6;
    }

    .pagination .page-item.disabled .page-link {
        background: rgba(0, 0, 0, 0.02);
        border-color: var(--border-light);
        color: var(--text-muted-light);
    }

    .dark-theme .pagination .page-item.disabled .page-link {
        background: rgba(255, 255, 255, 0.02);
        border-color: var(--border-dark);
        color: var(--text-muted-dark);
    }
    </style>
</head>
<body class="bg-light">
    <div class="loading" id="loadingBar"></div>
    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand text-primary" href="/">
                <i class="bi bi-broadcast"></i>Offline Callsign Lookup
            </a>
            <button onclick="toggleTheme()" class="theme-toggle btn" data-bs-toggle="tooltip" title="Toggle Theme (Ctrl+T)">
                <i class="bi bi-circle-half"></i>
            </button>
        </div>
    </nav>
    
    <div class="container py-4 results-container">
        <div class="results-header">
            <div class="d-flex justify-content-between align-items-center">
                <h2 class="results-title">Search Results</h2>
                <div class="d-flex gap-3">
                    <div class="btn-group" role="group">
                        <button type="button" class="btn btn-outline-primary view-toggle-btn active" data-view="table" data-bs-toggle="tooltip" title="Table View">
                            <i class="bi bi-table"></i>
                        </button>
                        <button type="button" class="btn btn-outline-primary view-toggle-btn" data-view="cards" data-bs-toggle="tooltip" title="Card View">
                            <i class="bi bi-grid"></i>
                        </button>
                    </div>
                    <a href="/" class="btn btn-outline-primary">
                        <i class="bi bi-search me-2"></i>New Search
                    </a>
                </div>
            </div>
        </div>
        
        <div class="filters-card card shadow-sm mb-4">
            <div class="card-body">
                <form method="get" class="row g-3" id="filterForm">
                    <input type="hidden" name="callsign" value="{{ request.args.get('callsign', '') }}">
                    <input type="hidden" name="name" value="{{ request.args.get('name', '') }}">
                    <input type="hidden" name="state" value="{{ request.args.get('state', '') }}">
                    <input type="hidden" name="country" value="{{ country }}">

                    <div class="col-md-3">
                        <label class="form-label">Sort by</label>
                        <select name="sort" class="form-select" onchange="this.form.submit()">
                            <option value="">Default</option>
                            <option value="call_sign" {% if sort=='call_sign' %}selected{% endif %}>Call Sign</option>
                            <option value="name" {% if sort=='name' %}selected{% endif %}>Name</option>
                            <option value="state" {% if sort=='state' %}selected{% endif %}>State</option>
                            <option value="grant_date" {% if sort=='grant_date' %}selected{% endif %}>Grant Date</option>
                        </select>
                    </div>
                    
                    <div class="col-md-3">
                        <label class="form-label">Status</label>
                        <select name="status" class="form-select" onchange="this.form.submit()">
                            <option value="">All Statuses</option>
                            <option value="A" {% if status=='A' %}selected{% endif %}>Active</option>
                            <option value="I" {% if status=='I' %}selected{% endif %}>Inactive</option>
                        </select>
                    </div>
                    
                    <div class="col-md-3">
                        <label class="form-label">License Class</label>
                        <select name="license_class" class="form-select" onchange="this.form.submit()">
                            <option value="">Any</option>
                            <option value="E" {% if license_class=='E' %}selected{% endif %}>Amateur Extra</option>
                            <option value="G" {% if license_class=='G' %}selected{% endif %}>General</option>
                            <option value="T" {% if license_class=='T' %}selected{% endif %}>Technician</option>
                        </select>
                    </div>
                    
                    <div class="col-md-3">
                        <label class="form-label">Results per page</label>
                        <select name="per_page" class="form-select" onchange="this.form.submit()">
                            <option value="20" {% if per_page==20 %}selected{% endif %}>20</option>
                            <option value="50" {% if per_page==50 %}selected{% endif %}>50</option>
                            <option value="100" {% if per_page==100 %}selected{% endif %}>100</option>
                        </select>
                    </div>
                </form>
            </div>
        </div>

        {% if results %}
            <div id="tableView" class="view-container">
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th><a href="{{ url_for('search', **dict(request.args, sort='call_sign')) }}">Call Sign{% if sort=='call_sign' %} <i class="bi bi-arrow-down"></i>{% endif %}</a></th>
                                <th><a href="{{ url_for('search', **dict(request.args, sort='name')) }}">Name{% if sort=='name' %} <i class="bi bi-arrow-down"></i>{% endif %}</a></th>
                                <th><a href="{{ url_for('search', **dict(request.args, sort='country')) }}">Country{% if sort=='country' %} <i class="bi bi-arrow-down"></i>{% endif %}</a></th>
                                <th><a href="{{ url_for('search', **dict(request.args, sort='state')) }}">State / Prov{% if sort=='state' %} <i class="bi bi-arrow-down"></i>{% endif %}</a></th>
                                <th>Status</th>
                                <th>Class</th>
                                <th>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                        {% for r in results %}
                            <tr>
                                <td><a href="{{ url_for('profile', callsign=r['call_sign']) }}">{{ r['call_sign'] }}</a></td>
                                <td>{{ r.get('formatted_name', '') }}</td>
                                <td>
                                    <span class="badge {% if r.get('country') == 'CA' %}bg-danger{% else %}bg-primary{% endif %}">
                                        {{ r.get('country', 'US') }}
                                    </span>
                                </td>
                                <td>{{ r.get('state', '') }}</td>
                                <td>
                                    <span class="badge {% if r.get('license_status', '') == 'A' %}bg-success{% else %}bg-secondary{% endif %}">
                                        {{ 'Active' if r.get('license_status', '') == 'A' else 'Inactive' }}
                                    </span>
                                </td>
                                <td>
                                    {% if r.get('license_class', '') %}
                                        <span class="badge bg-info">
                                            {{ LICENSE_CLASS_MAP.get(r.get('license_class', ''), '') }}
                                        </span>
                                    {% endif %}
                                </td>
                                <td>
                                    <a href="{{ url_for('profile', callsign=r['call_sign']) }}" 
                                       class="btn btn-sm btn-outline-primary"
                                       data-bs-toggle="tooltip"
                                       title="View Details">
                                        <i class="bi bi-info-circle"></i>
                                    </a>
                                </td>
                            </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <div id="cardView" class="view-container row g-4" style="display: none;">
                {% for r in results %}
                    <div class="col-md-6 col-lg-4">
                        <div class="card licensee-card h-100">
                            <div class="card-body">
                                <h5 class="card-title">{{ r['call_sign'] }}</h5>
                                <h6 class="card-subtitle text-muted">{{ r.get('formatted_name', '') }}</h6>
                                <div class="mb-3">
                                    <span class="badge {% if r.get('country') == 'CA' %}bg-danger{% else %}bg-primary{% endif %}">
                                        {{ r.get('country', 'US') }}
                                    </span>
                                    <span class="badge {% if r.get('license_status', '') == 'A' %}bg-success{% else %}bg-secondary{% endif %}">
                                        {{ 'Active' if r.get('license_status', '') == 'A' else 'Inactive' }}
                                    </span>
                                    {% if r.get('license_class', '') %}
                                        <span class="badge bg-info">
                                            {{ LICENSE_CLASS_MAP.get(r.get('license_class', ''), '') }}
                                        </span>
                                    {% endif %}
                                </div>
                                <p class="card-text">
                                    <small class="text-muted">
                                        <i class="bi bi-geo-alt"></i> {{ r.get('state', 'Location N/A') }}
                                    </small>
                                </p>
                                <a href="{{ url_for('profile', callsign=r['call_sign']) }}" 
                                   class="btn btn-sm btn-outline-primary">
                                    <i class="bi bi-info-circle me-1"></i> View Details
                                </a>
                            </div>
                        </div>
                    </div>
                {% endfor %}
            </div>

            <nav aria-label="Page navigation">
                <ul class="pagination">
                    {% if page > 1 %}
                        <li class="page-item">
                            <a class="page-link" href="{{ url_for('search', **dict(request.args, page=page-1)) }}">
                                <i class="bi bi-chevron-left"></i> Previous
                            </a>
                        </li>
                    {% else %}
                        <li class="page-item disabled">
                            <span class="page-link"><i class="bi bi-chevron-left"></i> Previous</span>
                        </li>
                    {% endif %}
                    
                    {% set start_page = [1, page - 2]|max %}
                    {% set end_page = [total_pages, page + 2]|min %}
                    
                    {% if start_page > 1 %}
                        <li class="page-item">
                            <a class="page-link" href="{{ url_for('search', **dict(request.args, page=1)) }}">1</a>
                        </li>
                        {% if start_page > 2 %}
                            <li class="page-item disabled">
                                <span class="page-link">...</span>
                            </li>
                        {% endif %}
                    {% endif %}
                    
                    {% for p in range(start_page, end_page + 1) %}
                        <li class="page-item {% if p == page %}active{% endif %}">
                            <a class="page-link" href="{{ url_for('search', **dict(request.args, page=p)) }}">{{ p }}</a>
                        </li>
                    {% endfor %}
                    
                    {% if end_page < total_pages %}
                        {% if end_page < total_pages - 1 %}
                            <li class="page-item disabled">
                                <span class="page-link">...</span>
                            </li>
                        {% endif %}
                        <li class="page-item">
                            <a class="page-link" href="{{ url_for('search', **dict(request.args, page=total_pages)) }}">{{ total_pages }}</a>
                        </li>
                    {% endif %}
                    
                    {% if page < total_pages %}
                        <li class="page-item">
                            <a class="page-link" href="{{ url_for('search', **dict(request.args, page=page+1)) }}">
                                Next <i class="bi bi-chevron-right"></i>
                            </a>
                        </li>
                    {% else %}
                        <li class="page-item disabled">
                            <span class="page-link">Next <i class="bi bi-chevron-right"></i></span>
                        </li>
                    {% endif %}
                </ul>
            </nav>
        {% else %}
            <div class="alert alert-warning">
                <i class="bi bi-exclamation-triangle me-2"></i> No results found.
            </div>
        {% endif %}
    </div>
    
    <footer class="footer mt-auto py-3">
        <div class="container text-center">
            <span class="text-muted">© 2026 BackStop Radio LLC</span>
        </div>
    </footer>
    
    <script>
    // View toggle functionality
    const viewToggleBtns = document.querySelectorAll('.view-toggle-btn');
    const tableView = document.getElementById('tableView');
    const cardView = document.getElementById('cardView');
    
    viewToggleBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            viewToggleBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const view = btn.dataset.view;
            if (view === 'table') {
                tableView.style.display = 'block';
                cardView.style.display = 'none';
            } else {
                tableView.style.display = 'none';
                cardView.style.display = 'flex';
            }
            
            localStorage.setItem('preferredView', view);
        });
    });
    
    // Load preferred view
    document.addEventListener('DOMContentLoaded', () => {
        const preferredView = localStorage.getItem('preferredView') || 'table';
        document.querySelector(`[data-view="${preferredView}"]`).click();
    });
    
    // Show loading bar on form submit
    document.getElementById('filterForm').addEventListener('submit', () => {
        document.getElementById('loadingBar').style.display = 'block';
    });
    </script>
</body>
</html>
'''

PROFILE_TEMPLATE = '''
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ record['call_sign'] }} - Licensee Profile</title>
    {{ bootstrap_cdn|safe }}
    {{ favicon|safe }}
    {{ common_js|safe }}
    {{ common_css|safe }}
    <style>
    .profile-header {
        position: relative;
        background: linear-gradient(to right, rgba(37, 99, 235, 0.02), rgba(37, 99, 235, 0.05));
        border-radius: 20px;
        padding: 0;
        margin-bottom: 2rem;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(37, 99, 235, 0.1);
        transition: all 0.3s ease;
        overflow: hidden;
        z-index: 1;
        min-height: 400px;
        display: flex;
        align-items: stretch;
    }

    #map {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 1;
        opacity: 0.95;
        transition: all 0.5s ease;
        filter: saturate(1.2) brightness(1.1);
        border-radius: 20px;
    }

    .dark-theme #map {
        filter: saturate(0.8) brightness(0.9) invert(1) hue-rotate(180deg);
        opacity: 0.8;
    }

    .profile-content {
        position: relative;
        z-index: 2;
        background: linear-gradient(to right, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.9));
        padding: 2rem;
        border-radius: 0 20px 20px 0;
        backdrop-filter: blur(8px);
        box-shadow: -4px 0 15px -1px rgba(0, 0, 0, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-left: none;
        transition: all 0.3s ease;
        width: 40%;
        margin-left: auto;
    }

    .dark-theme .profile-content {
        background: linear-gradient(to right, rgba(15, 23, 42, 0.95), rgba(15, 23, 42, 0.9));
        border-color: rgba(255, 255, 255, 0.1);
    }

    @media (max-width: 768px) {
        .profile-content {
            width: 100%;
            border-radius: 20px;
            border: 1px solid rgba(255, 255, 255, 0.2);
            margin: 1rem;
        }
    }

    .callsign {
        font-size: 3.5rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin-bottom: 0.5rem;
        background: linear-gradient(45deg, #2563eb, #3b82f6);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradientShift 8s ease infinite;
    }

    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }

    .dark-theme .callsign {
        background: linear-gradient(45deg, #60a5fa, #93c5fd);
        background-size: 200% 200%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    .licensee-name {
        font-size: 1.75rem;
        font-weight: 600;
        color: var(--text-light);
        margin-bottom: 1.5rem;
        opacity: 0.9;
    }

    .dark-theme .licensee-name {
        color: var(--text-dark);
    }

    .status-badge {
        font-size: 0.875rem;
        font-weight: 600;
        padding: 0.625rem 1.25rem;
        border-radius: 9999px;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
    }

    .status-badge.active {
        background: rgba(5, 150, 105, 0.1);
        color: #059669;
        border: 1px solid rgba(5, 150, 105, 0.2);
    }

    .dark-theme .status-badge.active {
        background: rgba(5, 150, 105, 0.2);
        color: #34d399;
        border-color: rgba(52, 211, 153, 0.2);
    }

    .status-badge.inactive {
        background: rgba(156, 163, 175, 0.1);
        color: #6b7280;
        border: 1px solid rgba(156, 163, 175, 0.2);
    }

    .dark-theme .status-badge.inactive {
        background: rgba(156, 163, 175, 0.2);
        color: #9ca3af;
        border-color: rgba(156, 163, 175, 0.2);
    }

    .class-badge {
        font-size: 0.875rem;
        font-weight: 600;
        padding: 0.625rem 1.25rem;
        border-radius: 9999px;
        background: rgba(37, 99, 235, 0.1);
        color: #2563eb;
        margin-left: 0.75rem;
        border: 1px solid rgba(37, 99, 235, 0.2);
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: all 0.3s ease;
    }

    .dark-theme .class-badge {
        background: rgba(59, 130, 246, 0.2);
        color: #60a5fa;
        border-color: rgba(96, 165, 250, 0.2);
    }

    .location-info {
        margin-top: 1.5rem;
        color: var(--text-muted-light);
        font-size: 1rem;
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 0.75rem 1rem;
        background: rgba(0, 0, 0, 0.02);
        border-radius: 12px;
        border: 1px solid rgba(0, 0, 0, 0.05);
    }

    .dark-theme .location-info {
        color: var(--text-muted-dark);
        background: rgba(255, 255, 255, 0.02);
        border-color: rgba(255, 255, 255, 0.05);
    }

    .location-info i {
        color: #2563eb;
        font-size: 1.1em;
    }

    .dark-theme .location-info i {
        color: #60a5fa;
    }

    .map-loading {
        position: absolute;
        top: 50%;
        left: 30%;
        transform: translate(-50%, -50%);
        color: var(--text-muted-light);
        font-size: 0.875rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
        z-index: 0;
    }

    .dark-theme .map-loading {
        color: var(--text-muted-dark);
    }

    .details-card {
        background: rgba(255, 255, 255, 0.8);
        border-radius: 20px;
        border: none;
        backdrop-filter: blur(10px);
        transition: all 0.3s ease;
    }

    .dark-theme .details-card {
        background: rgba(30, 41, 59, 0.8);
    }

    .section-title {
        font-size: 1.25rem;
        font-weight: 600;
        margin-bottom: 1.5rem;
        color: var(--text-light);
        display: flex;
        align-items: center;
        gap: 0.75rem;
    }

    .dark-theme .section-title {
        color: var(--text-dark);
    }

    .section-title i {
        color: var(--primary-color);
        font-size: 1.2em;
    }

    .dark-theme .section-title i {
        color: #60a5fa;
    }

    .details-table {
        border-collapse: separate;
        border-spacing: 0 0.75rem;
    }

    .details-table th {
        font-weight: 500;
        color: var(--text-muted-light);
        padding: 0.5rem 1rem;
        width: 40%;
        text-align: left;
        vertical-align: top;
    }

    .dark-theme .details-table th {
        color: var(--text-muted-dark);
    }

    .details-table td {
        padding: 0.5rem 1rem;
        background: rgba(0, 0, 0, 0.02);
        border-radius: 8px;
        color: var(--text-light);
    }

    .dark-theme .details-table td {
        background: rgba(255, 255, 255, 0.02);
        color: var(--text-dark);
    }

    .breadcrumb {
        padding: 1rem 0;
        margin-bottom: 1.5rem;
    }

    .breadcrumb-item a {
        color: var(--text-muted-light);
        text-decoration: none;
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        transition: all 0.2s ease;
    }

    .dark-theme .breadcrumb-item a {
        color: var(--text-muted-dark);
    }

    .breadcrumb-item a:hover {
        color: var(--primary-color);
    }

    .dark-theme .breadcrumb-item a:hover {
        color: #60a5fa;
    }

    .breadcrumb-item.active {
        color: var(--text-light);
        font-weight: 500;
    }

    .dark-theme .breadcrumb-item.active {
        color: var(--text-dark);
    }

    .breadcrumb-item + .breadcrumb-item::before {
        content: "•";
        color: var(--text-muted-light);
    }

    .dark-theme .breadcrumb-item + .breadcrumb-item::before {
        color: var(--text-muted-dark);
    }
    </style>
</head>
<body class="bg-light">
    <div class="loading" id="loadingBar"></div>
    <nav class="navbar navbar-expand-lg">
        <div class="container">
            <a class="navbar-brand text-primary" href="/">
                <i class="bi bi-broadcast"></i>Offline Callsign Lookup
            </a>
            <button onclick="toggleTheme()" class="theme-toggle btn" data-bs-toggle="tooltip" title="Toggle Theme (Ctrl+T)">
                <i class="bi bi-circle-half"></i>
            </button>
        </div>
    </nav>
    
    <div class="container py-4">
        <nav aria-label="breadcrumb">
            <ol class="breadcrumb">
                <li class="breadcrumb-item">
                    <a href="/"><i class="bi bi-house-door"></i> Home</a>
                </li>
                <li class="breadcrumb-item">
                    <a href="{{ url_for('search') }}"><i class="bi bi-search"></i> Search</a>
                </li>
                <li class="breadcrumb-item active">{{ record['call_sign'] }}</li>
            </ol>
        </nav>
        
        <div class="profile-header">
            <div id="map"></div>
            <div class="map-loading">
                <i class="bi bi-map"></i> Loading map...
            </div>
            <div class="profile-content">
                <h1 class="callsign">{{ record['call_sign'] }}</h1>
                <h2 class="licensee-name">{{ record.get('formatted_name', '') }}</h2>
                <div class="d-flex align-items-center gap-2">
                    <span class="status-badge {% if record.get('license_status', '') == 'A' %}active{% else %}inactive{% endif %}">
                        <i class="bi bi-{% if record.get('license_status', '') == 'A' %}check-circle-fill{% else %}x-circle-fill{% endif %}"></i>
                        {{ 'Active' if record.get('license_status', '') == 'A' else 'Inactive' }}
                    </span>
                    {% if record.get('license_class', '') %}
                        <span class="class-badge">
                            <i class="bi bi-award"></i>
                            {{ LICENSE_CLASS_MAP.get(record.get('license_class', ''), '') }}
                        </span>
                    {% endif %}
                </div>
                <div class="location-info">
                    <i class="bi bi-geo-alt"></i>
                    {{ record.get('city', '') }}, {{ record.get('state', '') }} {{ record.get('zip_code', '') }}
                </div>
            </div>
        </div>
        
        <div class="row g-4">
            <div class="col-md-6">
                <div class="details-card card h-100">
                    <div class="card-body">
                        <h3 class="section-title">
                            <i class="bi bi-person"></i>
                            Personal Information
                        </h3>
                        <table class="details-table w-100">
                            {% if record.get('entity_name') %}
                            <tr>
                                <th>Entity Name</th>
                                <td>{{ record.get('entity_name', '') }}</td>
                            </tr>
                            {% else %}
                            <tr>
                                <th>First Name</th>
                                <td>{{ record.get('first_name', '') }}</td>
                            </tr>
                            {% if record.get('mi') %}
                            <tr>
                                <th>Middle Initial</th>
                                <td>{{ record.get('mi', '') }}</td>
                            </tr>
                            {% endif %}
                            <tr>
                                <th>Last Name</th>
                                <td>{{ record.get('last_name', '') }}</td>
                            </tr>
                            {% endif %}
                            <tr>
                                <th>Entity Type</th>
                                <td>{{ FCC_CODE_DEFS['entity_type'].get(record.get('entity_type', ''), 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>Applicant Type</th>
                                <td>{{ FCC_CODE_DEFS['applicant_type_code'].get(record.get('applicant_type_code', ''), 'N/A') }}</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="col-md-6">
                <div class="details-card card h-100">
                    <div class="card-body">
                        <h3 class="section-title">
                            <i class="bi bi-geo"></i>
                            Contact Information
                        </h3>
                        <table class="details-table w-100">
                            <tr>
                                <th>Street Address</th>
                                <td>{{ record.get('street_address', 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>City</th>
                                <td>{{ record.get('city', 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>State</th>
                                <td>{{ record.get('state', 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>ZIP Code</th>
                                <td>{{ record.get('zip_code', 'N/A') }}</td>
                            </tr>
                            {% if record.get('email') %}
                            <tr>
                                <th>Email</th>
                                <td>{{ record.get('email', '') }}</td>
                            </tr>
                            {% endif %}
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="col-12">
                <div class="details-card card">
                    <div class="card-body">
                        <h3 class="section-title">
                            <i class="bi bi-card-text"></i>
                            License Details
                        </h3>
                        <table class="details-table w-100">
                            <tr>
                                <th>License Status</th>
                                <td>{{ 'Active' if record.get('license_status', '') == 'A' else 'Inactive' }}</td>
                            </tr>
                            <tr>
                                <th>License Class</th>
                                <td>{{ LICENSE_CLASS_MAP.get(record.get('license_class', ''), 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>Grant Date</th>
                                <td>{{ record.get('grant_date', 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>Expiration Date</th>
                                <td>{{ record.get('expired_date', 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>Last Action Date</th>
                                <td>{{ record.get('last_action_date', 'N/A') }}</td>
                            </tr>
                            <tr>
                                <th>Unique Identifier</th>
                                <td>{{ record.get('unique_system_identifier', 'N/A') }}</td>
                            </tr>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <footer class="footer mt-auto py-3">
        <div class="container text-center">
            <span class="text-muted">© 2026 BackStop Radio LLC</span>
        </div>
    </footer>

    <script>
    // Initialize map
    const map = L.map('map', {
        zoomControl: true,
        dragging: true,
        touchZoom: true,
        scrollWheelZoom: true,
        doubleClickZoom: true,
        attributionControl: false
    });

    // Add OpenStreetMap tiles with custom options
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        minZoom: 3,
        tileSize: 512,
        zoomOffset: -1,
        detectRetina: true
    }).addTo(map);

    // Function to get coordinates from city/state
    async function getCoordinates() {
        const city = '{{ record.get("city", "") }}';
        const state = '{{ record.get("state", "") }}';
        const zip = '{{ record.get("zip_code", "") }}';
        
        if (!city || !state) return null;
        
        try {
            const query = `${city}, ${state} ${zip}, USA`;
            const response = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(query)}&limit=1`);
            const data = await response.json();
            
            if (data && data.length > 0) {
                return [parseFloat(data[0].lat), parseFloat(data[0].lon)];
            }
        } catch (error) {
            console.error('Error getting coordinates:', error);
        }
        
        // Fallback coordinates (center of US)
        return [39.8283, -98.5795];
    }

    // Initialize map with location
    async function initMap() {
        const mapLoading = document.querySelector('.map-loading');
        try {
            const coords = await getCoordinates();
            if (coords) {
                // Set view with smooth animation
                map.setView(coords, 13, {
                    animate: true,
                    duration: 1
                });

                // Add main marker with custom icon
                const markerHtml = `
                    <div style="
                        width: 32px;
                        height: 32px;
                        background: #dc3545;
                        border: 4px solid white;
                        border-radius: 50%;
                        box-shadow: 0 0 15px rgba(220, 53, 69, 0.4);
                        transform: scale(1);
                        animation: markerPulse 2s infinite;
                    "></div>
                `;

                const icon = L.divIcon({
                    html: markerHtml,
                    className: 'custom-marker',
                    iconSize: [32, 32],
                    iconAnchor: [16, 16]
                });

                const marker = L.marker(coords, {
                    icon: icon
                }).addTo(map);

                // Add pulse circles
                const innerCircle = L.circle(coords, {
                    color: '#dc3545',
                    fillColor: '#dc3545',
                    fillOpacity: 0.2,
                    radius: 1000,
                    weight: 2,
                    opacity: 0.4
                }).addTo(map);

                const outerCircle = L.circle(coords, {
                    color: '#dc3545',
                    fillColor: '#dc3545',
                    fillOpacity: 0.1,
                    radius: 2000,
                    weight: 1,
                    opacity: 0.2
                }).addTo(map);

                // Add pulse animation
                const style = document.createElement('style');
                style.textContent = `
                    @keyframes markerPulse {
                        0% { transform: scale(1); box-shadow: 0 0 15px rgba(220, 53, 69, 0.4); }
                        50% { transform: scale(1.2); box-shadow: 0 0 20px rgba(220, 53, 69, 0.6); }
                        100% { transform: scale(1); box-shadow: 0 0 15px rgba(220, 53, 69, 0.4); }
                    }
                    .custom-marker {
                        transition: transform 0.3s ease;
                    }
                    .custom-marker:hover {
                        transform: scale(1.2);
                    }
                `;
                document.head.appendChild(style);

                // Add zoom control to the right
                map.zoomControl.setPosition('topright');
            }
            mapLoading.style.display = 'none';
        } catch (error) {
            console.error('Error initializing map:', error);
            mapLoading.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Failed to load map';
        }
    }

    // Initialize map when page loads
    document.addEventListener('DOMContentLoaded', initMap);

    // Update map when theme changes
    document.addEventListener('themeChanged', () => {
        setTimeout(() => {
            map.invalidateSize();
        }, 100);
    });
    </script>
</body>
</html>
'''

# Add states dictionary
STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri',
    'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio',
    'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont',
    'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
    'DC': 'District of Columbia', 'AS': 'American Samoa', 'GU': 'Guam', 'MP': 'Northern Mariana Islands',
    'PR': 'Puerto Rico', 'VI': 'U.S. Virgin Islands'
}

# Canadian provinces / territories (ISED uses these 2-letter codes in the
# province field; reused in the shared State/Province dropdown when Canada is
# in scope).
PROVINCES = {
    'AB': 'Alberta (CA)', 'BC': 'British Columbia (CA)', 'MB': 'Manitoba (CA)',
    'NB': 'New Brunswick (CA)', 'NL': 'Newfoundland and Labrador (CA)',
    'NS': 'Nova Scotia (CA)', 'NT': 'Northwest Territories (CA)',
    'NU': 'Nunavut (CA)', 'ON': 'Ontario (CA)', 'PE': 'Prince Edward Island (CA)',
    'QC': 'Quebec (CA)', 'SK': 'Saskatchewan (CA)', 'YT': 'Yukon (CA)'
}

# Combined dropdown options (US states first, then Canadian provinces). Note:
# NS/NB/NT/PE/ON/QC etc. are Canadian; US 2-letter codes never collide with
# these, so a merged dict is unambiguous for filtering.
STATES_AND_PROVINCES = {**STATES, **PROVINCES}

# Add license class mapping (FCC single-letter classes + derived Canadian codes).
LICENSE_CLASS_MAP = {
    'E': 'Amateur Extra',
    'G': 'General',
    'T': 'Technician',
    'N': 'Novice',
    'A': 'Advanced',
    'P': 'Technician Plus',
    # Canadian (ISED) qualification levels derived in the `licenses` view.
    'CA_BAS': 'Basic',
    'CA_HON': 'Basic w/ Honours',
    'CA_ADV': 'Advanced'
}

# Country dropdown options.
COUNTRY_OPTIONS = {'us': 'United States', 'ca': 'Canada', 'all': 'US + Canada'}

# Add FCC code definitions
FCC_CODE_DEFS = {
    'entity_type': {
        'CE': 'Transferee contact',
        'CL': 'Licensee Contact',
        'CR': 'Assignor or Transferor Contact',
        'CS': 'Lessee Contact',
        'E': 'Transferee',
        'L': 'Licensee or Assignee',
        'O': 'Owner',
        'R': 'Assignor or Transferor',
        'S': 'Lessee'
    },
    'applicant_type_code': {
        'B': 'Amateur Club',
        'C': 'Corporation',
        'D': 'General Partnership',
        'E': 'Limited Partnership',
        'F': 'Limited Liability Partnership',
        'G': 'Government Entity',
        'H': 'Other',
        'I': 'Individual',
        'J': 'Joint Venture',
        'L': 'Limited Liability Company',
        'M': 'Military Recreation',
        'O': 'Consortium',
        'P': 'Partnership',
        'R': 'RACES',
        'T': 'Trust',
        'U': 'Unincorporated Association'
    }
}

def add_to_recent_searches(search_params):
    """Add a search to recent searches in session"""
    # Filter out empty values and ensure session exists
    filtered_params = {k: v.strip() for k, v in search_params.items() if v and v.strip()}
    
    if not filtered_params:
        return
        
    if 'recent_searches' not in session:
        session['recent_searches'] = []
    
    recent = session['recent_searches']
    
    # Create search display text
    display_parts = []
    if filtered_params.get('callsign'):
        display_parts.append(filtered_params['callsign'])
    if filtered_params.get('name'):
        display_parts.append(filtered_params['name'])
    if filtered_params.get('state'):
        display_parts.append(STATES_AND_PROVINCES.get(filtered_params['state'], filtered_params['state']))
    
    # Create a search entry
    search = {
        'params': filtered_params,
        'display': ' • '.join(display_parts)
    }
    
    # Remove if already exists and add to front
    recent = [r for r in recent if r.get('display') != search['display']]
    recent.insert(0, search)
    
    # Keep only last 5 searches
    recent = recent[:5]
    session['recent_searches'] = recent
    # Explicitly save the session
    session.modified = True

@app.route('/')
@handle_database_error
def index():
    recent_searches = session.get('recent_searches', [])
    logging.info(f"Session ID: {session.get('_id', 'None')}")
    logging.info(f"Recent searches: {recent_searches}")
    return render_template_string(
        SEARCH_FORM,
        bootstrap_cdn=BOOTSTRAP_CDN,
        favicon=FAVICON,
        common_js=COMMON_JS,
        common_css=COMMON_CSS,
        states=STATES_AND_PROVINCES,
        country_options=COUNTRY_OPTIONS,
        country=Config.DEFAULT_COUNTRY,
        recent_searches=recent_searches
    )

@app.route('/search')
@handle_database_error
def search():
    callsign = request.args.get('callsign', '').strip().upper()
    name = request.args.get('name', '').strip().upper()
    state = request.args.get('state', '').strip().upper()
    sort = request.args.get('sort', '')
    status = request.args.get('status', '')
    license_class = request.args.get('license_class', '')
    country = request.args.get('country', Config.DEFAULT_COUNTRY).strip().lower()
    if country not in ('us', 'ca', 'all'):
        country = Config.DEFAULT_COUNTRY
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    # Add to recent searches if this is a new search and has parameters
    if page == 1 and any([callsign, name, state]):
        logging.info(f"Adding search to recent: {callsign} {name} {state}")
        add_to_recent_searches({
            'callsign': callsign,
            'name': name,
            'state': state
        })
        logging.info(f"Recent searches after add: {session.get('recent_searches', [])}")

    if not any([callsign, name, state]):
        return redirect(url_for('index'))

    results = db.search_records(
        callsign=callsign,
        name=name,
        state=state,
        sort=sort,
        status=status,
        license_class=license_class,
        country=country,
        page=page,
        per_page=per_page
    )

    total_pages = (results['total'] + per_page - 1) // per_page

    return render_template_string(
        RESULTS_TEMPLATE,
        bootstrap_cdn=BOOTSTRAP_CDN,
        favicon=FAVICON,
        common_js=COMMON_JS,
        common_css=COMMON_CSS,
        results=results['records'],
        sort=sort,
        status=status,
        license_class=license_class,
        country=country,
        per_page=per_page,
        request=request,
        page=page,
        total_pages=total_pages,
        LICENSE_CLASS_MAP=LICENSE_CLASS_MAP,
        states=STATES_AND_PROVINCES
    )

@app.route('/profile/<callsign>')
@handle_database_error
def profile(callsign):
    rec = db.get_record_by_call_sign(callsign.upper())
    if not rec:
        # Fall back to Canadian (ISED) data.
        ca = db.get_ca_records_by_call_sign(callsign.upper())
        rec = ca[0] if ca else None
    if not rec:
        return render_template_string(
            ERROR_TEMPLATE,
            error=f"No record found for call sign {callsign.upper()}",
            solution="Please check the call sign and try again.",
            bootstrap_cdn=BOOTSTRAP_CDN,
            favicon=FAVICON,
            common_js=COMMON_JS,
            common_css=COMMON_CSS
        )

    # Format name for display
    if rec.get('entity_name'):
        rec['formatted_name'] = rec['entity_name']
    else:
        name_parts = []
        if rec.get('first_name'): name_parts.append(rec['first_name'])
        if rec.get('mi'): name_parts.append(rec['mi'])
        if rec.get('last_name'): name_parts.append(rec['last_name'])
        rec['formatted_name'] = ' '.join(name_parts)

    # Format dates for display
    for date_field in ['grant_date', 'expired_date', 'last_action_date']:
        if rec.get(date_field):
            try:
                date_obj = datetime.strptime(rec[date_field], '%Y-%m-%d')
                rec[date_field] = date_obj.strftime('%m/%d/%Y')
            except ValueError:
                pass

    return render_template_string(
        PROFILE_TEMPLATE,
        bootstrap_cdn=BOOTSTRAP_CDN,
        favicon=FAVICON,
        common_js=COMMON_JS,
        common_css=COMMON_CSS,
        record=rec,
        LICENSE_CLASS_MAP=LICENSE_CLASS_MAP,
        FCC_CODE_DEFS=FCC_CODE_DEFS,
        states=STATES
    )

@app.route('/favicon.ico') # type: ignore
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/debug/session')
def debug_session():
    return {
        'session_id': session.get('_id', 'None'),
        'recent_searches': session.get('recent_searches', []),
        'session_data': dict(session)
    }

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Offline Callsign Lookup web interface')
    parser.add_argument(
        '--port', type=int, default=int(os.environ.get('PORT', 5000)),
        help='Port to serve on (default: 5000, or the PORT env var). '
             'Use this if port 5000 is taken — on macOS the AirPlay Receiver uses it.'
    )
    parser.add_argument(
        '--host', default=os.environ.get('HOST', '0.0.0.0'),
        help='Host/interface to bind to (default: 0.0.0.0)'
    )
    args = parser.parse_args()

    app.run(debug=True, host=args.host, port=args.port)