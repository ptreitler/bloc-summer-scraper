"""app.py — WSGI entry point"""
import logging

from web import create_app

logging.basicConfig(level=logging.INFO)

app = create_app()

with app.app_context():
    routes = sorted(str(r) for r in app.url_map.iter_rules())
    logging.info("Registered routes: %s", routes)

if __name__ == "__main__":
    app.run(debug=True)
