from app_package.users.utils import gen_weather_url, add_new_location, add_weather_history
from app_package.dashboard.utilsSteps import make_steps_chart_util, df_utils
from app_package.users.utils import location_exists
import requests;import json
from ws_models01 import sess, Oura_sleep_descriptions, Users, Oura_token, Weather_history, Locations, User_location_day, \
    Apple_health_export
import os
from ws_config01 import ConfigDev
from datetime import datetime, timedelta
import time
import pandas as pd



from ws_config01 import ConfigDev, ConfigProd
import os
import logging
from logging.handlers import RotatingFileHandler

# config = ConfigDev()
if os.environ.get('TERM_PROGRAM')=='Apple_Terminal' or os.environ.get('COMPUTERNAME')=='NICKSURFACEPRO4':
    config = ConfigDev()
else:
    config = ConfigProd()



logs_dir = os.path.abspath(os.path.join(os.getcwd(), 'logs'))

#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_users = logging.getLogger(__name__)
logger_users.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(logs_dir,'users_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_users.addHandler(file_handler)
logger_users.addHandler(stream_handler)



def get_df_for_dash(USER_ID, data_item):
    file_name = f'user{USER_ID}_df_{data_item}.pkl'
    file_path = os.path.join("/Users/nick/Documents/_databases/ws08/df_files", file_name)
    if not os.path.exists(file_path):
        return False
    df = pd.read_pickle(file_path)
    return df

def user_oldest_day_util(USER_ID):
    data_item_list = ['steps', 'sleep', 'temp', 'cloudcover']
    df_dict = {key:get_df_for_dash(USER_ID,key) for key in data_item_list}
    oldest_date_list = []
    for i in data_item_list:
        if not isinstance(df_dict.get(i), bool):
            if isinstance(df_dict.get(i).iloc[0].date, str):
                oldest_date_list.append(datetime.strptime(df_dict.get(i).iloc[0].date,'%Y-%m-%d'))
    oldest_date_str = min(oldest_date_list).strftime("%Y-%m-%d")
    return oldest_date_str


def add_user_loc_days(oldest_date_str, USER_ID, loc_id):
    # dates_call_dict = {}
    call_period = 1
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    end_date = datetime.strptime(end_date_str,"%Y-%m-%d")
    oldest_day = datetime.strptime(oldest_date_str,"%Y-%m-%d")
    end_date_flag = True# indicates loop is searching for end_date of a period. False means searching for start_date
    # previous_day = end_date

    while end_date >= oldest_day:
        end_date_str = end_date.strftime("%Y-%m-%d")
        search_day = sess.query(User_location_day).filter_by(user_id=USER_ID, date=end_date_str).first()

        if end_date == oldest_day:
            # dates_call_dict[call_period] = {"start": temp_start, "end":temp_end}
            # call_period += 1
            new_user_loc = User_location_day(user_id = USER_ID, location_id=loc_id, date=end_date_str, row_type="user input")
            sess.add(new_user_loc);sess.commit();
        elif not search_day and end_date_flag:
            
            new_user_loc = User_location_day(user_id = USER_ID, location_id=loc_id, date=end_date_str, row_type="user input")
            sess.add(new_user_loc);sess.commit();
            temp_end = end_date.strftime("%Y-%m-%d")
            # temp_start = temp_end
            end_date_flag = False
        elif not search_day and not end_date_flag:
            
            new_user_loc = User_location_day(user_id = USER_ID, location_id=loc_id, date=end_date_str, row_type="user input")
            sess.add(new_user_loc);sess.commit();
            # temp_start = end_date.strftime("%Y-%m-%d")
        elif search_day:
            # if weather history exists: do not add User_Loc_weather, just con

            # if end_date+timedelta(1) != previous_day:
            #     dates_call_dict[call_period] = {"start": temp_start, "end":temp_end}
            #     call_period += 1
            end_date_flag =True
            # previous_day = end_date

        end_date = end_date - timedelta(1)
    # TODO: Do not need these date_call_dict but need to make this for a similar function that users weather_hist
    # return dates_call_dict
        

def get_missing_weather_dates_from_hist(oldest_date_str, loc_id):
    logger_users.info(f'- In get_dates_call_dict_from_hist -')
    dates_call_dict = {}
    call_period = 1
    end_date_str = datetime.now().strftime("%Y-%m-%d")
    end_date = datetime.strptime(end_date_str,"%Y-%m-%d")
    oldest_day = datetime.strptime(oldest_date_str,"%Y-%m-%d")
    end_date_flag = True
    # previous_day = end_date

    while end_date >= oldest_day:
        end_date_str = end_date.strftime("%Y-%m-%d")
        search_day = sess.query(Weather_history).filter_by(location_id=loc_id, date_time=end_date_str).first()
        print(end_date_str)
        if end_date == oldest_day:
            if temp_end != dates_call_dict[call_period-1].get('end'):
                dates_call_dict[call_period] = {"start": temp_start, "end":temp_end}
                call_period += 1
                print('- fire last -')
        elif not search_day and end_date_flag:
            temp_end = end_date.strftime("%Y-%m-%d")
            temp_start = temp_end
            end_date_flag = False
    #         print('temp_start: ', temp_start)
        elif not search_day and not end_date_flag:
            temp_start = end_date.strftime("%Y-%m-%d")
    #         print('temp_start: ', temp_start)
        elif search_day:
            #if end_date+timedelta(1) != previous_day:# what is logic here
            if len(dates_call_dict) ==0:
                dates_call_dict[call_period] = {"start": temp_start, "end":temp_end}
                call_period += 1
                print('- added to dict len=0 - ')

            elif len(dates_call_dict) >0:
                if temp_end != dates_call_dict[call_period-1].get('end'):
                    dates_call_dict[call_period] = {"start": temp_start, "end":temp_end}
    #                 print(f'dates_call_dict[{call_period}]: {dates_call_dict[call_period]}')
        #             date
                    call_period += 1
                    print('- added to dict len>0 - ')
            end_date_flag =True
            # previous_day = end_date

        end_date = end_date - timedelta(1)
    return dates_call_dict