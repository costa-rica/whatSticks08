from flask import Blueprint
from flask import Flask, request, jsonify, make_response, current_app
from ws_config01 import ConfigDev, ConfigProd, ConfigLocal
from ws_models01 import sess, Users, Oura_token, Oura_sleep_descriptions,\
    Locations, Weather_history, User_location_day
from datetime import date, datetime, timedelta
import logging
from logging.handlers import RotatingFileHandler
import os
# from app_package.apple.utilsXmlUtility import xml_file_fixer, add_apple_to_db, \
#     compress_to_save_util
import time
# import xmltodict
import subprocess
from flask_mail import Message
from app_package import mail



# if os.uname()[1] == 'Nicks-Mac-mini.lan' or os.uname()[1] == 'NICKSURFACEPRO4':
#     config = ConfigLocal()
#     # testing_oura = True
# elif 'dev' in os.uname()[1]:
#     config = ConfigDev()
#     # testing_oura = False
# elif 'prod' in os.uname()[1] or os.uname()[1] == 'speedy100':
#     config = ConfigProd()
#     # testing_oura = False


# logs_dir = os.path.abspath(os.path.join(os.getcwd(), 'logs'))
if os.environ.get('CONFIG_TYPE')=='local':
    config_context = ConfigLocal()
elif os.environ.get('CONFIG_TYPE')=='dev':
    config_context = ConfigDev()
elif os.environ.get('CONFIG_TYPE')=='prod':
    config_context = ConfigProd()


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_apple = logging.getLogger(__name__)
logger_apple.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(config_context.API_LOGS_DIR,'apple_service.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_apple.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_apple.addHandler(file_handler)
logger_apple.addHandler(stream_handler)


apple_route = Blueprint('apple_route', __name__)

@apple_route.route('/apple')
def apple_is_running():
    return f"Apple routes are working! Today is {datetime.today()}!"

@apple_route.route('/test_function')
def process_apple():
    logger_apple.info('- In test_function route')
    path_sub = os.path.join(current_app.config.get('APPLE_SUBPROCESS_DIR'),'add_apple_subprocess.py')
    logger_apple.info('path_sub: ', path_sub)
    # subprocess.Popen(['python', path_sub])
    subprocess.Popen(['python', path_sub,'5'])
    logger_apple.info('- Done sub processing ')
    return "Sucessful call"


@apple_route.route('/store_apple_health')
def store_apple_health():
  
    #check password
    logger_apple.info(f'- Accessed store_apple_health endpoint -')
    #1) verify password
    request_data = request.get_json()
    if request_data.get('password') == current_app.config.get('WSH_API_PASSWORD'):
        logger_apple.info(f'--- store_apple_health endpoint PASSWORD verified ---')

        xml_file_name = request_data.get('xml_file_name')
        user_id = request_data.get('user_id')

        
        path_sub = os.path.join(current_app.config.get('APPLE_SUBPROCESS_DIR'), 'add_apple_subprocess.py')
        
        try:
            logger_apple.info(f'--- calling subprocess, from: {path_sub} ---')

            subprocess.Popen(['python', path_sub,xml_file_name, str(user_id)])
            logger_apple.info(f'--- subprocess working now ---')
            return "Sucessful call"
        except:
            email = sess.query(Users).get(int(user_id)).email
            subject = "Problem with WS server unable to process file"
            message = "Please contact Nick (nick@dashanddata.com)"
            msg = Message(subject,
                    sender=current_app.config.get('MAIL_USERNAME'),
                    recipients=[email])
            msg.body = message
            try:
                mail.send(msg)
                logger_apple.info(f'--- Emailed {email} that WS servers not working right ---')
            except:
                logger_apple.info(f'--- Failed to email {email} (user: {user_id} that WS servers not working right ---')


    else:
        return make_response('Could not verify',
            401, 
            {'WWW-Authenticate' : 'Basic realm="Login required!"'})



@apple_route.route('/send_email')
def email_complete():
    request_data = request.get_json()
    # print('reqeust_data: ', request_data)
    if request_data.get('password') == current_app.config.get('WSH_API_PASSWORD'):

        #get user email from users table
        user_id = int(request_data.get('user_id'))
        email = sess.query(Users).get(user_id).email
        records_uploaded = request_data.get('records_uploaded')
        
        #select message type
        message = request_data.get('message')
        if message == "Failed to process Apple file. No header for data found":
            subject = "Unable to Process Apple Health"
            message = """What Sticks is unable to process your Apple Health data because
there was a problem with parsing the data headers and body in the XML file. If you would like
to have someone at WS work on this please email nick@dashanddata.com
            """

        elif message == "Failed to store xml into database":
            subject = "Unable to add your Apple Health to WS database"
            message = """What Sticks is unable to process your Apple Health data. If you would like
to have someone at WS work on this please email nick@dashanddata.com
            """

        elif message == "Successfully added xml to database!":
            records_uploaded = "{:,}".format(records_uploaded)
            subject = f"Successfully added {records_uploaded} your Apple Health Data"
            message = """Login to your What Sticks account and see what your Apple Health data tells you."""
        
        msg = Message(subject,
                    sender=current_app.config.get('MAIL_USERNAME'),
                    recipients=[email])
        msg.body = message

        try:
            mail.send(msg)


            return jsonify({"message": "successfully sent message"})
        except:
            return jsonify({"messsage": "Unable to send message - problem using Flask mail"})
    
    else:
        return make_response('Could not verify',
            401, 
            {'WWW-Authenticate' : 'Basic realm="Login required!"'})