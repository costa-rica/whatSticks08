from flask import Flask
from ws_config01 import ConfigDev, ConfigProd, ConfigLocal
import logging
from logging.handlers import RotatingFileHandler
import os
from flask_mail import Mail


if os.environ.get('CONFIG_TYPE')=='local':
    config = ConfigLocal()
elif os.environ.get('CONFIG_TYPE')=='dev':
    config = ConfigDev()
elif os.environ.get('CONFIG_TYPE')=='prod':
    config = ConfigProd()

#First placed its called make directory here
if not os.path.exists(os.path.join(config.API_LOGS_DIR)):
    os.makedirs(os.path.join(config.API_LOGS_DIR))

#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

logger_init = logging.getLogger('__init__')
logger_init.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(os.path.join(config.API_LOGS_DIR,'__init__.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

logger_init.addHandler(file_handler)
logger_init.addHandler(stream_handler)

#set werkzeug handler
logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('werkzeug').addHandler(file_handler)
#End set up logger

logger_init.info(f'--- Starting ws08api ---')

# App init
mail = Mail()

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    mail.init_app(app)
    # print('**', dir(app.config))
    # print('**', app.config.keys())
    # print('**', app.config.get('ENV'))
    logger_init.info(f"--- Running DEBUG: {app.config.get('DEBUG')}")

    from app_package.scheduler.routes import sched_route
    from app_package.apple.routes import apple_route
    # from app_package.dashboard.routes import dash
    
    app.register_blueprint(sched_route)
    app.register_blueprint(apple_route)
    # app.register_blueprint(dash)
    
    return app      
