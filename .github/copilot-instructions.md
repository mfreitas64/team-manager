# Team Manager - AI Coding Assistant Instructions

## Project Overview
Team Manager is a Flask-based web application for sports team management, tracking players, practices, tournaments, and statistics across multiple seasons. Built with Flask-Login authentication, SQLAlchemy ORM, Flask-Babel i18n, and WeasyPrint for PDF exports.

## Architecture & Key Patterns

### Multi-Season Data Model
- **Session-based season selection**: Current season stored in `session['season_id']`
- **Critical pattern**: Always check `season_id = session.get('season_id')` at route entry
- If missing, redirect to `url_for('season.manage_seasons')`
- All major models (PlayerModel, TournamentModel, PracticeRegisterModel, etc.) have `season_id` and `user_id` foreign keys
- Season isolation: Query filters must include both `user_id=current_user.id` AND `season_id=session_id`

### Blueprint-Based Routing
- 8 blueprints: `auth`, `players`, `tournaments`, `practise`, `season`, `dashboard`, `exports`, `home`
- Each in `app/<name>/routes.py` with URL prefix (e.g., `/players`, `/tournament`)
- Registered in `app/__init__.py` after Babel/context processors setup
- All data manipulation routes require `@login_required` decorator

### Player Alias System
- Players have both `name` (full) and `alias` (display name)
- **Pattern**: Create `alias_lookup = {p.name: p.alias or p.name}` dict for templates
- Sort players by alias: `sorted([{"name": p.name, "alias": p.alias or p.name}], key=lambda x: x["alias"].lower())`
- Store full names in comma-separated fields, display aliases in UI

### Authorization Pattern
Every data-modifying route must verify:
```python
if entity.user_id != current_user.id or entity.season_id != session.get('season_id'):
    return "⛔ Unauthorized", 403
```

### Comma-Separated Data Storage
- Tournament opponents/players, practice attendees stored as CSV strings in TEXT columns
- **Split pattern**: `names = [n.strip() for n in field.split(',') if n.strip()]`
- **Join pattern**: `','.join(request.form.getlist('field_name'))`

### Tournament Matrix System
- `TournamentMatrixModel` tracks player participation per game/period (4 periods × 6min each)
- Key tuple: `(tournament_id, player_name, opponent_name, period, played=True/False)`
- Dashboard aggregates: filter by `tournament_id.in_(user_tournament_ids)` to prevent cross-user leaks
- Clear old entries before bulk insert: `TournamentMatrixModel.query.filter_by(tournament_id=tid).delete()`

## Internationalization (i18n)
- Flask-Babel with `translations/pt/LC_MESSAGES/` Portuguese translations
- Language stored in session: `session.get('lang', 'en')`
- Use `{{ _('Text') }}` in templates, no direct string usage in `render_template` calls
- Switch via `?lang=pt` query parameter (handled by `get_locale()`)
- Update translations: Run `update_translations.bat` (Windows batch script)

## Database Patterns
- SQLAlchemy models in single `app/models.py`
- Extensions initialized in `app/extensions.py` (db, login_manager)
- No migrations folder - use `db.create_all()` for schema
- PostgreSQL in production (`psycopg2-binary`), connection via `DATABASE_URL` env var
- Relationships use `backref` for bidirectional access (e.g., `season.players`)

## PDF Export System
- WeasyPrint for complex layouts (player stats), ReportLab for tournament grids
- Tournament PDFs: Landscape A4, checkbox matrix for 4 periods × players × opponents
- Base64 image embedding in HTML templates for WeasyPrint: `encode_image_base64(path)`
- Generate in-memory: `BytesIO()` buffer, return `send_file(buffer, mimetype='application/pdf')`

## Development Workflow
- **Run locally**: `python run.py` (debug mode) or `flask run`
- **Production**: Gunicorn via `wsgi.py` entrypoint (`gunicorn app:app`)
- **Docker**: Multi-stage build installs Cairo/Pango for WeasyPrint
- **Environment**: `.env` file with `SECRET_KEY` and `DATABASE_URL`
- No test suite currently exists

## Template & UI Conventions
- Bootstrap 5.3.3 from CDN, custom CSS in `base.html` (coral theme #eb6636)
- Emoji prefixes in UI (🏀, 📅, ⛔, ✅) - preserve this style
- Responsive navbar with language switcher
- Card-based layouts with hover effects
- Chart.js for dashboard visualizations (minutes played, practice attendance)

## Common Pitfalls
1. **Forgetting season_id check**: Always verify session before queries
2. **User data leaks**: Must filter by BOTH `user_id` AND `season_id`
3. **Alias vs name confusion**: Store names, display aliases
4. **Matrix query scope**: When aggregating tournaments, pre-filter tournament IDs by user
5. **Date handling**: Practice dates use `datetime.date` type, tournaments store string dates

## Key Files Reference
- `app/__init__.py` - Application factory, blueprint registration, Babel setup
- `app/models.py` - All 8 database models with relationships
- `app/season/routes.py` - Season management, player copying between seasons
- `app/tournaments/routes.py` - Tournament CRUD, matrix generation
- `app/dashboard/routes.py` - Analytics aggregation (minutes, game counts)
- `app/exports/routes.py` - PDF/CSV export logic (390 lines)
