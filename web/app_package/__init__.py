from flask import Flask
from ws_config01 import ConfigDev, ConfigProd, ConfigLocal
from ws_models01 import login_manager
from flask_mail import Mail
import os
import json
import logging
from logging.handlers import RotatingFileHandler
from pytz import timezone
from datetime import datetime



# User set's .env file in the whatSticks08modules/ws_modules01/ws_config01/.env
if os.environ.get('CONFIG_TYPE')=='local':
    config_object = ConfigLocal()

elif os.environ.get('CONFIG_TYPE')=='dev':
    config_object = ConfigDev()

elif os.environ.get('CONFIG_TYPE')=='prod':
    config_object = ConfigProd()



if not os.path.exists(os.path.join(config_object.WEB_LOGS_DIR)):
    os.makedirs(os.path.join(config_object.WEB_LOGS_DIR))

# timezone 
def timetz(*args):
    return datetime.now(timezone('Europe/Paris') ).timetuple()

logging.Formatter.converter = timetz


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

logger_init = logging.getLogger('__init__')
logger_init.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(os.path.join(config_object.WEB_LOGS_DIR,'__init__.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)


stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

stream_handler_tz = logging.StreamHandler()

logger_init.addHandler(file_handler)
logger_init.addHandler(stream_handler)


#set werkzeug handler
logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('werkzeug').addHandler(file_handler)
#End set up logger

logger_init.info(f'--- Starting ws08web ---')

logger_init.info(f"* ---> Configured for {config_object.SCHED_CONFIG_STRING}")


# App init
mail = Mail()
def create_app():
    app = Flask(__name__)
    app.config.from_object(config_object)
    # print('app.config.get("ENV") says it is ---> ', app.config.get('ENV'))
    app.config.word_doc_database_images_dir = os.path.join(app.config.get('WORD_DOC_DIR'), 'blog_images')
    # app.config.word_doc_static_images_dir = os.path.join(app.config.get('WORD_DOC_DIR'), 'blog_images')

    login_manager.init_app(app)
    mail.init_app(app)
    logger_init.info(f"--- Running DEBUG: {app.config.get('DEBUG')}")
    logger_init.info(f"--- PROPAGATE_EXCEPTIONS: {app.config.get('PROPAGATE_EXCEPTIONS')}")

    from app_package.users.routes import users
    from app_package.dashboard.routes import dash
    from app_package.errors.routes import errors
    from app_package.blog.routes import blog
    
    app.register_blueprint(users)
    app.register_blueprint(dash)
    app.register_blueprint(errors)
    app.register_blueprint(blog)
    
    return app      
