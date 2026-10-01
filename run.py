from app import create_app
from app.db import db
from app.dcbn_artwork import seed_dcbn_artwork
from sqlalchemy.exc import SQLAlchemyError

app = create_app()

with app.app_context():
    try:
        seed_dcbn_artwork()
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception('Could not initialize DC chronicle artwork')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
