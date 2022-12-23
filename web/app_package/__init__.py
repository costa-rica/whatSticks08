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


# # Logging Begin
# logs_dir = os.path.join(os.getcwd(), 'logs')

# Config Begin
config_dict = {}


# User set's .env file in the whatSticks08modules/ws_modules01/ws_config01/.env
if os.environ.get('CONFIG_TYPE')=='local':
    config_object = ConfigLocal()
    # testing_oura = True
    config_dict['production'] = False
    # logger_init.info('* ---> Configured for Production')
elif os.environ.get('CONFIG_TYPE')=='dev':
    config_object = ConfigDev()
    # testing_oura = False
    config_dict['production'] = False
    # logger_init.info('* ---> Configured for Development')
elif os.environ.get('CONFIG_TYPE')=='prod':
    config_object = ConfigProd()
    # testing_oura = False
    # logger_init.info('* ---> Configured for Production')
    config_dict['production'] = True


with open('config_dict.json', 'w') as outfile:
    json.dump(config_dict, outfile)


# print('--- config_object.WEB_LOGS_DIR ----')
# print(config_object.WEB_LOGS_DIR )
# print(os.getcwd())
# print(os.path.exists(os.path.join(config_object.WEB_LOGS_DIR)))

if not os.path.exists(os.path.join(config_object.WEB_LOGS_DIR)):
    os.makedirs(os.path.join(config_object.WEB_LOGS_DIR))

# timezone 
def timetz(*args):
    return datetime.now(tz).timetuple()
# tz = timezone('Europe/Paris')

tz = timezone('Europe/Paris') 
logging.Formatter.converter = timetz


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')
# formatter_terminal_tz = logging_tz.LocalFormatter('%(asctime)s:%(filename)s:%(name)s:%(message)s', datefmt=datefmt)# new for tz

logger_init = logging.getLogger('__init__')
logger_init.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(os.path.join(config_object.WEB_LOGS_DIR,'__init__.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

# logger_tz = logging.getLogger(('__init__-tz'))# new for tz
# logger_tz.setFormatter(formatter_terminal_tz)# new for tz

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

stream_handler_tz = logging.StreamHandler()
# stream_handler_tz.setFormatter(formatter_terminal_tz)# new for tz

logger_init.addHandler(file_handler)
logger_init.addHandler(stream_handler)

# logger_tz.addHandler(stream_handler_tz)# new for tz



#set werkzeug handler
logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('werkzeug').addHandler(file_handler)
#End set up logger

logger_init.info(f'--- Starting ws08web ---')
# logger_tz.info(f'--- Starting ws08web ---')

logger_init.info(f"* ---> Configured for {config_object.SCHED_CONFIG_STRING}")
# # Config Begin
# config_dict = {}


# # User set's .env file in the whatSticks08modules/ws_modules01/ws_config01/.env
# if os.environ.get('CONFIG_TYPE')=='local':
#     config_object = ConfigLocal()
#     # testing_oura = True
#     config_dict['production'] = False
#     logger_init.info('* ---> Configured for Production')
# elif os.environ.get('CONFIG_TYPE')=='dev':
#     config_object = ConfigDev()
#     # testing_oura = False
#     config_dict['production'] = False
#     logger_init.info('* ---> Configured for Development')
# elif os.environ.get('CONFIG_TYPE')=='prod':
#     config_object = ConfigProd()
#     # testing_oura = False
#     logger_init.info('* ---> Configured for Production')
#     config_dict['production'] = True


# with open('config_dict.json', 'w') as outfile:
#     json.dump(config_dict, outfile)



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
