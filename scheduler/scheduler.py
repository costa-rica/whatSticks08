from apscheduler.schedulers.background import BackgroundScheduler
import json
import requests
from datetime import datetime, timedelta
import os
from ws_config01 import ConfigDev, ConfigProd, ConfigLocal
import logging
from logging.handlers import RotatingFileHandler
import pandas as pd



# if os.environ.get('CONFIG_TYPE')=='local':
#     config = ConfigLocal()
#     # config_string = 'ConfigDev'
#     print('* Development - Local')
# elif os.environ.get('CONFIG_TYPE')=='dev':
#     config = ConfigDev()
#     # config_string = 'ConfigDev'
#     print('* Development')
# elif os.environ.get('CONFIG_TYPE')=='prod':
#     config = ConfigProd()
#     # config_string = 'ConfigProd'
#     print('* ---> Configured for Production')
if os.environ.get('CONFIG_TYPE')=='local':
    config = ConfigLocal()
elif os.environ.get('CONFIG_TYPE')=='dev':
    config = ConfigDev()
elif os.environ.get('CONFIG_TYPE')=='prod':
    config = ConfigProd()


#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_init = logging.getLogger(__name__)
logger_init.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(config.SCHED_LOGS_DIR,'schduler.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

logger_init.addHandler(file_handler)
logger_init.addHandler(stream_handler)


def scheduler_funct():
    logger_init.info(f'--- Started Scheduler *')
    logger_init.info(f'--- running as {config.SCHED_CONFIG_STRING}')
    if not os.path.exists(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir')):
        os.makedirs(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'))
        logger_init.info(f"--- successfully created {os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir')} *")

    # yesterday = datetime.today() - timedelta(days=1)
    # date_formatted = yesterday.strftime('%Y-%m-%d')
    # logger_init.info(f'- Calling for weather date: {date_formatted}  -')
    scheduler = BackgroundScheduler()

    #job_call_get_locations = scheduler.add_job(get_locations, 'cron', day='*', hour='23', minute='01', second='05')#Production
    #job_call_get_locations = scheduler.add_job(get_locations, 'cron', hour='*', minute='07', second='05')#Testing
    job_call_harmless = scheduler.add_job(harmless, 'cron',  hour='*', minute='19', second='25')#Testing

    scheduler.start()

    while True:
        pass


# create funct_test_harmless

# create funct_weather_on_date

# create funct_



def harmless():
    
    yesterday = datetime.today() - timedelta(days=1)
    date_formatted = yesterday.strftime('%Y-%m-%d')

    logger_init.info(f'---> harmless: date_formatted: {date_formatted}.')

    # base_url = 'http://localhost:5000'#TODO: put this address in config
    base_url = config.WSH_API_URL_BASE#TODO: put this address in config
    # base_url = 'https://api3.what-sticks-health.com'
    logger_init.info(f'Begin Scheduler check of contact with: {base_url}')
    headers = { 'Content-Type': 'application/json'}
    payload = {}

    # are_we_running endpoint
    logger_init.info(f'---> Sending call to wsh06 api are_we_running')
    response_oura_tokens = requests.request('GET',base_url + '/are_we_running', headers = headers)
    
    logger_init.info(f'are_we_running response: {response_oura_tokens.status_code}')
    

    logger_init.info(f'---> Sending call to wsh06 api get_locations')
    payload['password'] = config.WSH_API_PASSWORD
    response_wsh_locations = requests.request('GET',base_url + '/get_locations',
        headers=headers, data=str(json.dumps(payload)))
    logger_init.info(f'get_locations response: {response_wsh_locations.status_code}')
    response_wsh_loc_dict = json.loads(response_wsh_locations.content.decode('utf-8'))
    logger_init.info(f'get_locations content count: {len(response_wsh_loc_dict)}')
    
    logger_init.info(f'---> Sending call to wsh06 api oura_tokens')
    response_oura_tokens = requests.request('GET',base_url + '/oura_tokens', headers=headers, data=str(json.dumps(payload)))
    logger_init.info(f'oura_tokens response: {response_oura_tokens.status_code}')
    oura_tokens_dict = json.loads(response_oura_tokens.content.decode('utf-8'))
    logger_init.info(f'oura_tokens content count: {len(oura_tokens_dict)}')
    logger_init.info(f'Scheduler DONE with harmless check of: {base_url}')


#1) send call to wsh06 api to get locations
def get_locations():
    # print('sending wsh call for all locations')
    logger_init.info(f'---> Sending call to ws08 api for locations.')

    yesterday = datetime.today() - timedelta(days=1)
    date_formatted = yesterday.strftime('%Y-%m-%d')

    logger_init.info(f'---> calling for data for {date_formatted}.')

    # base_url = 'http://localhost:5000'#TODO: put this address in config
    base_url = config.WSH_API_URL_BASE#TODO: put this address in config
    headers = { 'Content-Type': 'application/json'}
    payload = {}
    payload['password'] = config.WSH_API_PASSWORD
    response_wsh_locations = requests.request('GET',base_url + '/get_locations',
        headers=headers, data=str(json.dumps(payload)))
    
    
    # print('API call response code: ', response_oura_tokens.status_code)
    logger_init.info(f'---> API call response code: {response_wsh_locations.status_code}')

    if response_wsh_locations.status_code == 200:
        response_wsh_loc_dict = json.loads(response_wsh_locations.content.decode('utf-8'))
        wsh_loc_dict = json.dumps(response_wsh_loc_dict)
        try:
            # now we get the response... let's save it somewhere
            

            with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_locations1_get_locations.json'), 'w') as outfile:
                json.dump(wsh_loc_dict, outfile)
        
            # print(f'Locations succesfully saved in {os.path.join(os.getcwd(), "_locations1_get_locations.json")}')
            logger_init.info(f'Locations succesfully saved in {os.path.join(os.path.join(config.SCHED_LOGS_DIR,"json_utils_dir"), "_locations1_get_locations.json")}')
        except:
            # print('There was a problem with the response')
            logger_init.info('There was a problem with the response')
    else:
        # print(f'Call not succesful. Status code: ', response_oura_tokens.status_code)
        logger_init.info(f'Call not succesful. Status code: {response_wsh_locations.status_code}')
    
    call_weather_api(date_formatted)


#2) call weather Api every evning 9pm
def call_weather_api(date_formatted):
    # print('--- In call_weather_api() of scheduler.py----')
    logger_init.info('--- In call_weather_api() of scheduler.py----')
    with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_locations1_get_locations.json')) as json_file:
        locations_dict = json.loads(json.load(json_file))
        #locatinos_dict = {loc_id: [lat, lon]}

    today_str = datetime.now().strftime("%Y-%m-%d")

    weather_dict = {}
    call_list = []
    call_response = []
    date_of_call_list = []
    #1) Loop through dictionary
    for loc_id, coords in locations_dict.items():
        location_coords = f"{coords[0]},{coords[1]}"

        date_time = datetime.strptime(date_formatted + " 00:01:00", "%Y-%m-%d %H:%M:%S").isoformat()

        weather_call_url =f"{config.VISUAL_CROSSING_BASE_URL}{location_coords}/{str(date_time)}?key={config.VISUAL_CROSSING_TOKEN}&include=current"
        call_list.append(weather_call_url)

        try:
            r_history = requests.get(weather_call_url)
            call_response.append(r_history.status_code)#tracking weather_call_urls
            date_of_call_list.append(today_str)
            
            if r_history.status_code == 200:
            
                #2) for each id call weather api
                weather_dict[loc_id] = r_history.json()
            else:
                weather_dict[loc_id] = f'Problem connecting with Weather API. Response code: {r_history.status_code}'
        except:
            weather_dict[loc_id] = 'Error making call to Weather API. No response.'
            call_response.append("Error making this call")#tracking weather_call_urls
            date_of_call_list.append(today_str)
    
    #This just to record my calls
    df=pd.DataFrame(zip(date_of_call_list, call_list,call_response),columns=(["date_of_call","weather_call_url", "response"]))
    df.to_csv(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'),'weather_call_urls.csv'), mode='a')

    #3) put response in  a json
    weather_dict_json = json.dumps(weather_dict)
    with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_locations2_call_weather_api.json'), 'w') as outfile:
        json.dump(weather_dict_json, outfile)
    # print('---> json file with oura data successfully written.')
    logger_init.info('---> json file with oura data successfully written.')

    send_weather_data_to_wsh()
    

#3) send weather data to wsh06 api
def send_weather_data_to_wsh():
    logger_init.info('--- In send_weather_data_to_wsh() of scheduler.py----')
    
    try:
        with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_locations2_call_weather_api.json')) as json_file:
            weather_response_dict = json.loads(json.load(json_file))
    except:
        weather_response_dict=''
    
    if weather_response_dict !='':
        
        # base_url = 'http://localhost:5000'#TODO: put this address in config
        base_url = config.WSH_API_URL_BASE
        headers = { 'Content-Type': 'application/json'}
        payload = {}
        payload['password'] = config.WSH_API_PASSWORD
        payload['weather_response_dict'] = weather_response_dict
        
        response_wsh_weather = requests.request('GET',base_url + '/receive_weather_data', 
            headers=headers, data=str(json.dumps(payload)))
        # oura_tokens_dict = json.loads(response_oura_tokens.content.decode('utf-8'))
        logger_init.info(f'--- wsh06 weather api response: {response_wsh_weather.status_code}')

    get_oura_tokens()


#4) scheduler sends call to wsh06 api to get oura ring user tokens
def get_oura_tokens():
    
    logger_init.info(f'**** sending wsh call for all users oura tokens')
    base_url = config.WSH_API_URL_BASE#TODO: put this address in config
    headers = { 'Content-Type': 'application/json'}
    payload = {}
    payload['password'] = config.WSH_API_PASSWORD
    response_oura_tokens = requests.request('GET',base_url + '/oura_tokens', headers=headers, data=str(json.dumps(payload)))
    oura_tokens_dict = json.loads(response_oura_tokens.content.decode('utf-8'))
    response_oura_tokens.status_code

    # now we get the response... let's save it somewhere
    oura_tokens = json.dumps(oura_tokens_dict)

    with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_oura1_get_oura_tokens.json'), 'w') as outfile:
        json.dump(oura_tokens, outfile)
    
    #once finished call oura api
    call_oura_api()


#5) call Oura Ring api every evening 10pm
def call_oura_api():
    logger_init.info(f'--> Calling Oura API')
    # get oura tokens from os.path.join(os.getcwd(), 'get_oura_tokens.json')
    with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_oura1_get_oura_tokens.json')) as json_file:
        oura_tokens_dict = json.loads(json.load(json_file))
    
    oura_response_dict = {}
    date_of_call = []
    today_str = datetime.now().strftime("%Y-%m-%d")
    oura_call_list = []
    oura_user_id_list = []
    oura_call_response = []
    for user_id, oura_token_list in oura_tokens_dict.get('content').items():
        if len(oura_token_list)==2:# this means there is a token_id and token, otherwise we just received ['User has no Oura token']
            # url_sleep='https://api.ouraring.com/v1/sleep?start=2020-03-11&end=2020-03-21?'#TODO: put this address in config
            url_sleep=config.OURA_API_URL_BASE#TODO: put this address in config
            response_sleep = requests.get(url_sleep, headers={"Authorization": "Bearer " + oura_token_list[1]})
            # print('--> response_sleep.status_code: ', response_sleep.status_code)
            logger_init.info(f'--> response_sleep.status_code: {response_sleep.status_code}')
            date_of_call.append(today_str)
            oura_call_list.append(url_sleep)
            oura_user_id_list.append(user_id)
            oura_call_response.append(response_sleep.status_code)
            if response_sleep.status_code == 200:
                sleep_dict = response_sleep.json()
                #add whatSticks token id to dict
                sleep_dict['wsh_oura_token_id'] = oura_token_list[0]
            else:
                sleep_dict = {}
                sleep_dict['wsh_oura_token_id'] = oura_token_list[0]
                sleep_dict['No Oura data reason'] = f'API Status Code: {response_sleep.status_code}'
        else:
            sleep_dict = {}
            sleep_dict['wsh_oura_token_id'] = oura_token_list[0]
            sleep_dict['No Oura data reason'] = 'User has no Oura Ring Token'
        oura_response_dict[user_id] = sleep_dict
    
    #This just to record my calls
    df=pd.DataFrame(zip(date_of_call,oura_user_id_list,oura_call_list, oura_call_response),
        columns=(["date_of_call","user_id","oura_call_url", "response"]))
    df.to_csv(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'),'oura_call_urls.csv'), mode='a')

    oura_sleep_json = json.dumps(oura_response_dict)
    with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_oura2_call_oura_api.json'), 'w') as outfile:
        json.dump(oura_sleep_json, outfile)
    # print('---> json file with oura data successfully written.')
    logger_init.info(f'---> json file with oura data successfully written.')

    # send wsh api oura response data
    send_oura_data_to_wsh()


#6) send data to wsh06 api
def send_oura_data_to_wsh():
    logger_init.info(f'---> Sending oura data to wsh06 api')
    # get oura response data from os.path.join(os.getcwd(), 'get_oura_tokens.json')
    with open(os.path.join(os.path.join(config.SCHED_LOGS_DIR,'json_utils_dir'), '_oura2_call_oura_api.json')) as json_file:
        oura_response_dict = json.loads(json.load(json_file))
    
    # base_url = 'http://localhost:5000'#TODO: put this address in config
    base_url = config.WSH_API_URL_BASE
    headers = {'Content-Type': 'application/json'}
    payload = {}
    payload['password'] = config.WSH_API_PASSWORD
    payload['oura_response_dict'] = oura_response_dict
    response_oura_tokens = requests.request('GET',base_url + '/receive_oura_data', headers=headers, data=str(json.dumps(payload)))
    logger_init.info(f'---> WSH API /receive_oura_data response: {response_oura_tokens.status_code}')
    logger_init.info(f'---> FINISHED last line of call from the Scheduler app')



if __name__ == '__main__':  
    scheduler_funct()