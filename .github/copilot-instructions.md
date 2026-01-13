# Team Manager (Flask) — Copilot Instructions

## Big picture
- Flask app factory in `app/__init__.py` (`create_app()`), with blueprints for `auth`, `home`, `players`, `practise`, `tournaments`, `season`, `dashboard`, `export`.
- SQLAlchemy models live in one file: `app/models.py`.
- Multi-tenant data isolation is **by user + season**: most records have `user_id` and `season_id`.

## Season scoping (critical)
- Current season is stored in `session['season_id']`.
- Route pattern used across blueprints (e.g., `app/tournaments/routes.py`, `app/practise/routes.py`, `app/exports/routes.py`):
    ```py
    season_id = session.get('season_id')
    if not season_id:
            return redirect(url_for('season.manage_seasons'))
    ```
- Queries that list/aggregate data should filter on both `user_id=current_user.id` and `season_id=season_id`.

## Authz pattern (data modification)
- For entity edits/deletes, enforce ownership + season (see `app/tournaments/routes.py`, `app/practise/routes.py`):
    ```py
    if entity.user_id != current_user.id or entity.season_id != season_id:
            return "⛔️ Unauthorized", 403
    ```

## “Alias” player display
- Store canonical player names in DB/CSV fields; show `alias` in UI when present.
- Common template helpers (see `app/tournaments/routes.py`, `app/practise/routes.py`):
    - `alias_lookup = {p.name: (p.alias or p.name) for p in raw_players}`
    - Sort by alias: `sorted([{ "name": p.name, "alias": p.alias or p.name }], key=lambda x: x["alias"].lower())`

## CSV-in-TEXT conventions
- Several models store comma-separated values (e.g., `TournamentModel.opponents`, `TournamentModel.players`, `PracticeRegisterModel.players_present`, `PracticeRegisterModel.exercises_used`).
- Use list inputs on POST then `','.join(request.form.getlist('field'))` (see `app/tournaments/routes.py`, `app/practise/routes.py`).
- When reading: `[s.strip() for s in (field or '').split(',') if s.strip()]`.

## Tournament matrix model
- `TournamentMatrixModel` stores per-(player, opponent, period) participation; each “played” cell is worth **6 minutes** (see `app/tournaments/routes.py` and `app/dashboard/routes.py`).
- When aggregating matrix data, first compute the user’s tournament IDs then filter: `TournamentMatrixModel.tournament_id.in_(user_tournament_ids)`.

## i18n (Babel)
- Locale is chosen via `?lang=pt` and stored in session; `_()` is available in templates (see `app/__init__.py`).
- Update translations on Windows via `update_translations.bat` (`pybabel extract/update/compile`).

## PDF/exports
- Exports live in `app/exports/routes.py`.
- ReportLab is used for the tournament grid PDF; WeasyPrint is optional and guarded by `WEASYPRINT_AVAILABLE`.

## Running
- Local dev entrypoint: `python run.py`.
- Production entrypoint: `wsgi.py` (Gunicorn uses `app:app`).
- Requires `DATABASE_URL` and `SECRET_KEY` (loaded via `python-dotenv`).
