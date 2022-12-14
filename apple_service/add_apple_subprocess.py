from sys import argv
import time
from ws_config01 import ConfigDev, ConfigProd, ConfigLocal
import os
from utilsXmlUtility import xml_file_fixer, add_apple_to_db, \
    compress_to_save_util, email_user, clear_df_files
import xmltodict
import logging
from logging.handlers import RotatingFileHandler
from utilsDf import create_df_files, create_df_files_apple


if os.environ.get('CONFIG_TYPE')=='local':
    config = ConfigLocal()
    print('* apple_subprocess: Development - Local')
elif os.environ.get('CONFIG_TYPE')=='dev':
    config = ConfigDev()
    print('* apple_subprocess: Development')
elif os.environ.get('CONFIG_TYPE')=='prod':
    config = ConfigProd()
    print('* apple_subprocess: Production')



#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_apple = logging.getLogger(__name__)
logger_apple.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(config.APPLE_SUBPROCESS_DIR,'apple_service.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

logger_apple.addHandler(file_handler)
logger_apple.addHandler(stream_handler)

def test_function(args):
    logger_apple.info(' ---- Testing test_function in subprocess ----')
    logger_apple.info(args)
    wait_time =int(args)
    logger_apple.info('Start process')
    time.sleep(wait_time)
    logger_apple.info(f'Waited {wait_time} seconds')
    time.sleep(wait_time)
    logger_apple.info(f'Waited {wait_time} more....')
    return print('process complete')


# test_function(argv[1])

def test_function02():
    print('-- printed in test_function02')
    logger_apple.info(f'--- Started Apple Service: test_function02')


def add_apple(xml_file_name, user_id):
    logger_apple.info(f'--- Started Apple Service to upload data')
    
    new_file_path = os.path.join(config.APPLE_HEALTH_DIR, xml_file_name)

    
    try:
        with open(new_file_path, 'r') as xml_file:
            xml_dict = xmltodict.parse(xml_file.read())
    except:
        #send to fixer
        xml_dict = xml_file_fixer(new_file_path)
        if isinstance(xml_dict, str):
            logger_apple.info(f'---- Failed to process Apple file. No header for data found')
            
            message = "Failed to process Apple file. No header for data found"
            ws_email_api_response = email_user(user_id, message)
            logger_apple.info(f"Emailed user, WS API repsonse: {ws_email_api_response}")
            return message
        
    # try:
    df_uploaded_record_count = add_apple_to_db(xml_dict, user_id)
    logger_apple.info('- Successfully added xml to database!')

    ###############################################
    # TODO: if loads successfully check for exisiting 
    # user_[id]_df_apple_health_.pkl and delete
    ################################################
    if os.path.exists(config.DF_FILES_DIR):
        clear_df_files(user_id)

    # except:
    #     logger_apple.info('---- Failed to add data to database')
    #     message = "Failed to store xml into database"
    #     return message


    # create_df_files(user_id, ['steps'])
    # create_df_files_apple(USER_ID,data_item_list, data_item_name_show, method, data_item_apple_type_name)
    create_df_files_apple(user_id,['apple_health_step_count'], 'Step Count', 'sum', 'HKQuantityTypeIdentifierStepCount')

    message = "Successfully added xml to database!"
    ws_email_api_response = email_user(user_id, message, df_uploaded_record_count)
    logger_apple.info(f"Emailed user, WS API repsonse: {ws_email_api_response}")
    
    compress_to_save_util(os.path.basename(new_file_path))
    #email status to user
    message = "XML succesfully uplodated"
    logger_apple.info(f"-- Successfully added {df_uploaded_record_count} records")

    
    logger_apple.info('Apple subprocess complete!')

add_apple(argv[1], argv[2])

