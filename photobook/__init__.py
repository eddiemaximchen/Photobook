
import os,sys

import click
from flask import Flask, render_template
from flask_login import current_user
from flask_wtf.csrf import CSRFError

from photobook.blueprints.admin import admin_bp
from photobook.blueprints.ajax import ajax_bp
from photobook.blueprints.auth import auth_bp
from photobook.blueprints.main import main_bp
from photobook.blueprints.user import user_bp
from photobook.function import bootstrap, db, login_manager, mail, dropzone, moment, avatars, csrf
from photobook.models import Role, User, Photo, Tag, Follow, Notification, Comment, Collect,whooshee

basedir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))

# SQLite URI compatible
WIN = sys.platform.startswith('win')
if WIN:
    prefix = 'sqlite:///'
else:
    prefix = 'sqlite:////'


class Operations:
    CONFIRM = 'confirm'
    RESET_PASSWORD = 'reset-password'
    CHANGE_EMAIL = 'change-email'


class BaseConfig:
    PHOTOBOOK_ADMIN_EMAIL = os.getenv('PHOTOBOOK_ADMIN', 'admin@helloflask.com')
    PHOTOBOOK_PHOTO_PER_PAGE = 12
    PHOTOBOOK_COMMENT_PER_PAGE = 15
    PHOTOBOOK_NOTIFICATION_PER_PAGE = 20
    PHOTOBOOK_USER_PER_PAGE = 20
    PHOTOBOOK_MANAGE_PHOTO_PER_PAGE = 20
    PHOTOBOOK_MANAGE_USER_PER_PAGE = 30
    PHOTOBOOK_MANAGE_TAG_PER_PAGE = 50
    PHOTOBOOK_MANAGE_COMMENT_PER_PAGE = 30
    PHOTOBOOK_SEARCH_RESULT_PER_PAGE = 20
    PHOTOBOOK_MAIL_SUBJECT_PREFIX = '[PHOTOBOOK]'
    PHOTOBOOK_UPLOAD_PATH = os.path.join(basedir, 'uploads')
    PHOTOBOOK_PHOTO_SIZE = {'small': 400,
                         'medium': 800}
    PHOTOBOOK_PHOTO_SUFFIX = {
        PHOTOBOOK_PHOTO_SIZE['small']: '_s',  # thumbnail
        PHOTOBOOK_PHOTO_SIZE['medium']: '_m',  # display
    }

    SECRET_KEY = os.getenv('SECRET_KEY', 'secret string')
    MAX_CONTENT_LENGTH = 3 * 1024 * 1024  # file size exceed to 3 Mb will return a 413 error response.

    BOOTSTRAP_SERVE_LOCAL = True

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    AVATARS_SAVE_PATH = os.path.join(PHOTOBOOK_UPLOAD_PATH, 'avatars')
    AVATARS_SIZE_TUPLE = (30, 100, 200)

    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = 465
    MAIL_USE_SSL = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = ('PHOTOBOOK Admin', MAIL_USERNAME)

    DROPZONE_ALLOWED_FILE_TYPE = 'image'
    DROPZONE_MAX_FILE_SIZE = 3
    DROPZONE_MAX_FILES = 30
    DROPZONE_ENABLE_CSRF = True

    WHOOSHEE_MIN_STRING_LEN = 1


class DevelopmentConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = \
        prefix + os.path.join(basedir, 'data-dev.db')
    REDIS_URL = "redis://localhost"


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite:///'  # in-memory database


class ProductionConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL',
                                        prefix + os.path.join(basedir, 'data.db'))


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
}


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_CONFIG', 'development')

    app = Flask('photobook')
    
    app.config.from_object(config[config_name])

    register_extensions(app)
    register_blueprints(app)
    register_commands(app)
    register_errorhandlers(app)
    register_shell_context(app)
    register_template_context(app)

    return app


def register_extensions(app):
    bootstrap.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    dropzone.init_app(app)
    moment.init_app(app)
    whooshee.init_app(app)
    avatars.init_app(app)
    csrf.init_app(app)


def register_blueprints(app):
    app.register_blueprint(main_bp)
    app.register_blueprint(user_bp, url_prefix='/user')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(ajax_bp, url_prefix='/ajax')


def register_shell_context(app):
    @app.shell_context_processor
    def make_shell_context():
        return dict(db=db, User=User, Photo=Photo, Tag=Tag,
                    Follow=Follow, Collect=Collect, Comment=Comment,
                    Notification=Notification)


def register_template_context(app):
    @app.context_processor
    def make_template_context():
        if current_user.is_authenticated:
            notification_count = Notification.query.with_parent(current_user).filter_by(is_read=False).count()
        else:
            notification_count = None
        return dict(notification_count=notification_count)


def register_errorhandlers(app):
    @app.errorhandler(400)
    def bad_request(e):
        return render_template('errors/400.html'), 400

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403
 
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404
 
    @app.errorhandler(413)
    def request_entity_too_large(e):
        return render_template('errors/413.html'), 413
 
    @app.errorhandler(500)
    def internal_server_error(e):
        return render_template('errors/500.html'), 500
 
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        return render_template('errors/400.html', description=e.description), 500
 
 
def register_commands(app):
    @app.cli.command()
    @click.option('--drop', is_flag=True, help='Create after drop.')
    def initdb(drop):
        """Initialize the database."""
        if drop:
            click.confirm('This operation will delete the database, do you want to continue?', abort=True)
            db.drop_all()
            click.echo('Drop tables.')
        db.create_all()
        click.echo('Initialized database.')
# 
    @app.cli.command()
    def init():
        """Initialize PHOTOBOOK."""
        click.echo('Initializing the database...')
        db.create_all()
# 
        click.echo('Initializing the roles and permissions...')
        Role.init_role()
# 
        click.echo('Done.')
# 
    @app.cli.command()
    @click.option('--user', default=10, help='Quantity of users, default is 10.')
    @click.option('--follow', default=30, help='Quantity of follows, default is 30.')
    @click.option('--photo', default=30, help='Quantity of photos, default is 30.')
    @click.option('--tag', default=20, help='Quantity of tags, default is 20.')
    @click.option('--collect', default=50, help='Quantity of collects, default is 50.')
    @click.option('--comment', default=100, help='Quantity of comments, default is 100.')
    def forge(user, follow, photo, tag, collect, comment):
        """Generate fake data."""
 
        from photobook.fakes import fake_admin, fake_comment, fake_follow, fake_photo, fake_tag, fake_user, fake_collect
 
        db.drop_all()
        db.create_all()
 
        click.echo('Initializing the roles and permissions...')
        Role.init_role()
        click.echo('Generating the administrator...')
        fake_admin()
        click.echo('Generating %d users...' % user)
        fake_user(user)
        click.echo('Generating %d follows...' % follow)
        fake_follow(follow)
        click.echo('Generating %d tags...' % tag)
        fake_tag(tag)
        click.echo('Generating %d photos...' % photo)
        fake_photo(photo)
        click.echo('Generating %d collects...' % photo)
        fake_collect(collect)
        click.echo('Generating %d comments...' % comment)
        fake_comment(comment)
        click.echo('Done.')
