import xmltodict 
import zipfile
import re
import os
from datetime import datetime
from ws_config01 import ConfigDev, ConfigProd, ConfigLocal
import time
import logging
from logging.handlers import RotatingFileHandler
import shutil
import pandas as pd
from ws_models01 import sess, engine, Apple_health_export
import requests
import json


if os.environ.get('CONFIG_TYPE')=='local':
    config = ConfigLocal()
    print('* Development - Local')
elif os.environ.get('CONFIG_TYPE')=='dev':
    config = ConfigDev()
    print('* Development')
elif os.environ.get('CONFIG_TYPE')=='prod':
    config = ConfigProd()
    print('* ---> Configured for Production')


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

#starting line, next_line is how many lines after starting point do you want to go
# get_lines returns a string object
def get_lines(data, start, next_lines=1):
    line_list = [m.start() for m in re.finditer('\n', data)]
    if start == 1 and isinstance(next_lines,int):
        next_lines = next_lines - 1
        return data[0:line_list[next_lines]]
    elif start > 1 and isinstance(next_lines,int):
        start = start -2
        return data[line_list[start]:line_list[start + next_lines]]
    elif start >1 or start <0:# -- Get's all data from starting point to the end
        start = start -2
        return data[line_list[start]:]
    elif start == 1 and next_lines == None:
        return data[0:]
        

# Make line_list
def line_list_util(data_string, line_char_pos_list):
    line_list = []
    for i in range(0,len(line_char_pos_list)):
        if i != len(line_char_pos_list)-1:
            line_list.append(data_string[line_char_pos_list[i]:line_char_pos_list[i+1] ])
        else:
            line_list.append(data_string[line_char_pos_list[i]: ])
    return line_list


def header_fix_util(line_list):
    counter = 0
    new_string = ''
    flag_start = True
    flag_cdata_or_gt = False
    # flag_gt_watch = False
    error_counter = 0
    
    for line in line_list:
        if flag_start == True:
            if line.find('<!-- HealthKit Export ') > -1:
                new_string = new_string + line
                flag_start = False
            else:
                new_string = new_string + line
                
        elif flag_cdata_or_gt == True:
            if line.find('CDATA') > -1:#cdata
                new_string = new_string + line
            elif line.find('\n>') > -1:#gt
                new_string = new_string + line
                flag_cdata_or_gt = False
                # flag_gt_watch commented out because not being used but might be necessary
                # flag_gt_watch = True
                previous_line = line_list[counter]
            elif line.find('<!ELEM') > -1:
                logger_apple.info(f"- Header Error: <!ELEMENT out of place, line: {counter}")
                #'Error resolved by adding '\n>' before current line
                error_counter += 1
                new_string = new_string + '\n>' + line
                flag_cdata_or_gt = False

                
        else:
            if line.find('<!ATTLIST') > -1:
                new_string = new_string + line
                flag_cdata_or_gt = True
            elif line.find('<!ELEM') > -1:
                new_string = new_string + line
            elif line.find('CDATA') > -1:#gt
                logger_apple.info(f"- Header Error: this line shoudl go before last, line: {counter}")
                #'Error resolved by putting current line before the last'
                error_counter += 1
                new_string = new_string[:-len(previous_line)]
                new_string = new_string + line + previous_line
                
            elif line.find('\n>') > -1:
                logger_apple.info(f"- Header Error: duplicate '>', line: {counter}")
                # error resolved by skipping line
                error_counter += 1
            else:#      < -----------------------Everything not '\n>', 'CDATA', or '<!ATT'
                new_string = new_string + line
        counter += 1
    logger_apple.info(f"-- header_fix_util complete: {error_counter} error(s) found and resolved. -")
    return new_string


# def body_fix_util(body_list):
#     start_time = time.time()
#     counter = 0
#     string_obj = ''
#     error_count = 0
#     checkpoint = 2.5*10**5
# #     checkpoint = 10
    
#     for line in body_list:
#         start_date_line_list = [m.start() for m in re.finditer('startDate', line)]
#         if len(start_date_line_list)>1:
#             error_count += 1
#             string_obj = string_obj + line[:start_date_line_list[1]] + "endDate" + line[start_date_line_list[1]+len('startDate'):]
#         else:
#             string_obj = string_obj + line
        
#         if counter% checkpoint == 0:
            
#             end_time = time.time()
#             run_seconds = round(end_time - start_time)
#             if run_seconds <60:
#                 logger_apple.info(f'{"{:,}".format(counter)} rows have been reviewed --run_time: {str(run_seconds)} seconds')
#             elif run_seconds > 60:
#                 run_minutes =  round(run_seconds / 60)
#                 logger_apple.info(f'{"{:,}".format(counter)} rows have been reviewed ---- run_time: {str(run_minutes)} mins and {str(run_seconds % 60)} seconds')

#         counter += 1
#     logger_apple.info(f'Completed: Found {error_count} startDate errors')
#     return string_obj

def body_fix_small_util(body_list):
    row_counter = 0
    string_obj = ''
    error_count = 0
    # checkpoint = 2.5*10**5
    
    for line in body_list:
        start_date_line_list = [m.start() for m in re.finditer('startDate', line)]
        if len(start_date_line_list)>1:
            error_count += 1
            string_obj = string_obj + line[:start_date_line_list[1]] + "endDate" + line[start_date_line_list[1]+len('startDate'):]
        else:
            string_obj = string_obj + line
        
        row_counter += 1
    return string_obj, row_counter, error_count

def body_fix_looper_util(body_line_list):
    start_time = time.time()
    fixed_body_dict = {}
    break_point_list = []
    error_count = 0
    row_count = 0
    #break list into 10 parts
    for i in range(0,10):
        break_point_list.append(int(len(body_line_list)*(i*.1)))

    #fix one of the ten parts at a time and store into a dictionary (fixed_body_dict)
    for i in range(0,10):
        start = break_point_list[i]
        if i<9:
            end = break_point_list[i+1]
            temp_string, temp_row_count, temp_error_count = body_fix_small_util(body_line_list[start:end])
            fixed_body_dict[i]= temp_string
        else:
            temp_string, temp_row_count, temp_error_count = body_fix_small_util(body_line_list[start:])
            fixed_body_dict[i]= temp_string
        
        error_count = error_count + temp_error_count
        row_count = row_count + temp_row_count
            
    body_string_fixed =''
    for _, string in fixed_body_dict.items():
        body_string_fixed = body_string_fixed + string      
        
    end_time = time.time()
    run_seconds = round(end_time - start_time)
    if run_seconds <60:
        logger_apple.info(f'{"{:,}".format(row_count)} rows, {"{:,}".format(error_count)} errors --run_time: {str(run_seconds)} seconds')
    elif run_seconds > 60:
        run_minutes =  round(run_seconds / 60)
        logger_apple.info(f'{"{:,}".format(row_count)} rows, {"{:,}".format(error_count)} errors -- run_time: {str(run_minutes)} mins and {str(run_seconds % 60)} seconds')

    return body_string_fixed



def xml_get_header_body(header_string,body_string):

    #make list of header lines object:
    header = get_lines(header_string, 1 ,None)
    header_line_char_list = [x.start() for x in re.finditer('\n', header)]
    header_line_list = line_list_util(header, header_line_char_list)

    #make list of body lines object
    body = get_lines(body_string, 1,None)
    body_line_char_list = [x.start() for x in re.finditer('\n', body)]
    body_line_list = line_list_util(body, body_line_char_list)

    return header_line_list, body_line_list


#XML
def xml_file_fixer(xml_path):
    logger_apple.info(f'---- In xml_file_fixer --')
    # Read uncompressed file from database/apple_health/user000#_date.xml
    with open(xml_path, 'r') as f:
        data = f.read()

    # split data (a string obj of xml) into header and body
    try:
        header_string = data[:data.find('\n]>')+3]
        body_string = data[data.find('\n]>')+3:]
        logger_apple.info('**** successfully found header_string and body_string ***')
    except:
        logger_apple.info(f"--- xml_util: never found end of header or beginning of body strings ---")
        return "XML file never found end of header"

    # convert header and body stringst to lists
    header_line_list, body_line_list = xml_get_header_body(header_string, body_string)
    header_string_fixed = header_fix_util(header_line_list)

    # try to convert combined FIXED header and orig body string to dict
    try:
        xml_dict = xmltodict.parse(header_string_fixed + body_string)
        logger_apple.info('**** successfully parsed with xmltodict ***')
        return xml_dict
    except:
        logger_apple.info(f"--- xml_util: attempting to fix body string ---")

    # body_string_fixed = body_fix_util(body_line_list)
    body_string_fixed = body_fix_looper_util(body_line_list)

    # try to convert combined FIXED header and FIXED body string to dict
    try:
        # string to dictionary
        xml_dict = xmltodict.parse(header_string_fixed + body_string_fixed)
        # df_uploaded_record_count = add_apple_to_db(xml_dict)
        return xml_dict
    except:
        logger_apple.info(f"--- xml_util: unable to convert xml to dictionary ---")
        return "Unable to process Apple Health Export"


def compress_to_save_util(decompressed_xml_file_name):
    logger_apple.info('- Compressing and storing users Apple Health data')
    apple_health_dir = config.APPLE_HEALTH_DIR
    app_health_ex_dir = os.path.join(apple_health_dir,'stuff_to_compress', 'apple_health_export')
    stuff_to_compress = os.path.join(apple_health_dir,'stuff_to_compress')
    decompressed_xml = os.path.join(apple_health_dir, decompressed_xml_file_name)
    if not os.path.exists(stuff_to_compress):
        os.mkdir(stuff_to_compress)
        os.mkdir(app_health_ex_dir)
        shutil.copy(decompressed_xml, os.path.join(app_health_ex_dir,'export.xml' ))
        
    #     shutil.make_archive(app_health_ex_dir, 'zip', test_folder)
        new_name_and_path_of_zip = os.path.join(apple_health_dir, decompressed_xml_file_name[:-4])
        shutil.make_archive(new_name_and_path_of_zip, 'zip', stuff_to_compress)
        # delete directory that get's turned to compressed file
        shutil.rmtree(stuff_to_compress)
        # delete decompressed xml file becuase its now stored in a compressed directory
        # that can be reused in WS like original compressed Apple Health Export file
        os.remove(decompressed_xml)




############################
# From utilsApple #
###################



def add_apple_to_db(xml_dict, user_id):
    logger_apple.info('-- in apple_service/utilsXmlUtility/add_apple_to_db --')
    #Add new users apple data to database

    ##########
    # XML already converted to dictionary #
    ###############################

    records_list = xml_dict['HealthData']['Record']
    df = pd.DataFrame(records_list)
    df['user_id'] = int(user_id)
    df['time_stamp_utc']=datetime.utcnow()
    for name in list(df.columns):
        if name.find('@')!=-1:
            df.rename(columns={name:name[1:]}, inplace=True)

# Columns with dictionary structures i di'tn kwon what to do with
    df.MetadataEntry=''
    df.HeartRateVariabilityMetadataList=''

    #get all user's existing apple_health data into df
    base_query = sess.query(Apple_health_export).filter_by(user_id = 1)
    df_existing = pd.read_sql(str(base_query)[:-1] + str(user_id), sess.bind)

    logger_apple.info(f'current user has {len(df_existing)} rows')
    #rename columns

    table_name = 'apple_health_export_'
    cols = list(df_existing.columns)
    for col in cols:
        if col[:len(table_name)] == table_name:
            df_existing = df_existing.rename(columns=({col: col[len(table_name):]}))

    ##############################################################################
    ### NOTE: This is where a problem with apple health dates occurs.
    #### The createDate has slight differences depending on when the file is downloaded due to daylight savings
    #### pd.to_datetime(date_string).asm8 will normalize the data so that different daylight savings times can be compared on same level
    #### Other issues include:
    #### - uniqueness requires ['user_id','type','sourceName','sourceVersion','unit','creationDate','startDate','endDate','value','device']
    #### - 'id' is set to object because there is no int, so need to remove from new data
    ##############################################################################
    # New converting column to datatime value


    if len(df_existing) > 0:
        
        
        #convert df_existing to normalized date string
        df['creationDate'] = pd.to_datetime(df['creationDate'])
        df['creationDate'] = df['creationDate'].map(lambda x: x.asm8)
        df['creationDate'] = df['creationDate'].astype(str)

        df['startDate'] = pd.to_datetime(df['startDate'])
        df['startDate'] = df['startDate'].map(lambda x: x.asm8)
        df['startDate'] = df['startDate'].astype(str)

        df['endDate'] = pd.to_datetime(df['endDate'])
        df['endDate'] = df['endDate'].map(lambda x: x.asm8)
        df['endDate'] = df['endDate'].astype(str)

        for col in df_existing.columns:
            if col not in list(df.columns):
                df[col]=''


        df = df[list(df_existing.columns)]

        logger_apple.info(f'-- length of EXISTING apple health data: {len(df_existing)}')
        logger_apple.info(f'-- length of NEW apple health data: {len(df)}')

        # columns_to_compare_newness_list = ['user_id','type','sourceName','sourceVersion','unit','creationDate','startDate','endDate','value','device']
        columns_to_compare_newness_list = ['user_id','type','sourceName','sourceVersion','unit','creationDate','startDate','endDate','value']
       
        df_existing.set_index(columns_to_compare_newness_list, inplace=True)

        df.set_index(columns_to_compare_newness_list, inplace=True)
        
        df_existing.head(2)
        df.head(2)


        df = df[~df.index.isin(df_existing.index)]
        df.reset_index(inplace=True)
        df.drop(columns=['id'], inplace=True)
        logger_apple.info(f'-- length of NEW apple health data: {len(df)}')

    else:
        #convert df_existing to normalized date string
        df['creationDate'] = pd.to_datetime(df['creationDate'])
        df['creationDate'] = df['creationDate'].map(lambda x: x.asm8)
        df['creationDate'] = df['creationDate'].astype(str)

        df['startDate'] = pd.to_datetime(df['startDate'])
        df['startDate'] = df['startDate'].map(lambda x: x.asm8)
        df['startDate'] = df['startDate'].astype(str)

        df['endDate'] = pd.to_datetime(df['endDate'])
        df['endDate'] = df['endDate'].map(lambda x: x.asm8)
        df['endDate'] = df['endDate'].astype(str)



        logger_apple.info(f'-- length of NEW apple health data: {len(df)}')


 
    #Adding apple health to DATABASE
    logger_apple.info('-- Adding new data to db via df.to_sql')
    
    df.to_sql('apple_health_export', con=engine, if_exists='append', index=False)

    logger_apple.info('* Successfully added xml to database!')
    return len(df)


def clear_df_files(USER_ID):
    # This remove all apple health data df's from databases/df_files

    logger_apple.info('-- in apple_service/utilsXmlUtility/clear_df_files --')
    list_of_df_files = os.listdir(config.DF_FILES_DIR)


    # This might be an old way of 
    search_for_string = f"user{USER_ID}_df_apple_health"
    for file in list_of_df_files:
        if file.find(search_for_string) > -1:
            logger_apple.info(f'-- FOUND file to delete: user{USER_ID}_df_apple_health --')
            os.remove(os.path.join(config.DF_FILES_DIR, file))

    logger_apple.info(f'-- passed checking for  user{USER_ID}_df_apple_health --')
    # open user_browse_apple health
    apple_browse_user_filename = f"user{USER_ID}_df_browse_apple.pkl"
    if os.path.exists(os.path.join(config.DF_FILES_DIR, apple_browse_user_filename)):
        df_browse = pd.read_pickle(os.path.join(config.DF_FILES_DIR, apple_browse_user_filename))
        
        df_browse.to_pickle(os.path.join("/Users/nick/Documents/_jupyter","a_df_browse.pkl"))

        #find items that have been created
        type_formatted_series = df_browse[df_browse['df_file_created']=='true'].type_formatted
        # type_formatted_series = df_browse[df_browse['df_file_existing']=='true']
        
        
        #delete those
        for apple_type in type_formatted_series:
            file_name = f'user{USER_ID}_df_{apple_type.replace(" ", "_").lower()}.pkl'
            os.remove(os.path.join(config.DF_FILES_DIR, file_name))
        
        logger_apple.info(f'-- clear_df_files getting closer to COMPLETion  --')
        
        #then delete user_df_browse_apple
        os.remove(os.path.join(config.DF_FILES_DIR, apple_browse_user_filename))

    logger_apple.info(f'-- clear_df_files COMPLETED SUCCESSFULLY --')


##########################
# Email User #
#################

def email_user(user_id, message, records_uploaded=0):
    headers = { 'Content-Type': 'application/json'}
    payload = {}
    payload['password'] = config.WSH_API_PASSWORD
    payload['user_id'] = user_id
    payload['message'] = message
    payload['records_uploaded'] = records_uploaded
    r_email = requests.request('GET',config.WSH_API_URL_BASE + '/send_email', headers=headers, 
                                    data=str(json.dumps(payload)))
    
    return r_email.status_code