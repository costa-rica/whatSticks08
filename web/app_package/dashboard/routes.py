from tokenize import cookie_re
from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request, abort, session,\
    Response, current_app, send_from_directory
# import bcrypt
from ws_models01 import sess, Users, login_manager, User_location_day, Oura_sleep_descriptions, \
    Apple_health_export
from flask_login import login_required, login_user, logout_user, current_user
from datetime import datetime
import numpy as np
import pandas as pd
from app_package.dashboard.utils import buttons_dict_util, buttons_dict_update_util, \
    make_chart_util, df_utils, create_raw_df
from app_package.users.utilsDf import create_df_files
import json
import os
import time
import logging
from logging.handlers import RotatingFileHandler
from ws_config01 import ConfigDev, ConfigProd


if os.environ.get('TERM_PROGRAM')=='Apple_Terminal' or os.environ.get('COMPUTERNAME')=='NICKSURFACEPRO4':
    config = ConfigDev()
else:
    config = ConfigProd()


logs_dir = os.path.abspath(os.path.join(os.getcwd(), 'logs'))

#Setting up Logger
formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

#initialize a logger
logger_dash = logging.getLogger(__name__)
logger_dash.setLevel(logging.DEBUG)
# logger_terminal = logging.getLogger('terminal logger')
# logger_terminal.setLevel(logging.DEBUG)

#where do we store logging information
file_handler = RotatingFileHandler(os.path.join(logs_dir,'dashboard_routes.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

#where the stream_handler will print
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

# logger_sched.handlers.clear() #<--- This was useful somewhere for duplicate logs
logger_dash.addHandler(file_handler)
logger_dash.addHandler(stream_handler)


dash = Blueprint('dash', __name__)


@dash.route('/dashboard/<dash_dependent_var>', methods=['GET', 'POST'])
@login_required
def dashboard(dash_dependent_var):
    logger_dash.info(f'- Entered dashboard: {dash_dependent_var.upper()} -')
    page_name = f"{dash_dependent_var[0].upper() + dash_dependent_var[1:]} Dashboard"
    # dash_dependent_var = 'sleep'

    USER_ID = current_user.id if current_user.id !=2 else 1

    # search df_files dir for all user[id]_.pkl
    list_of_data = os.listdir(config.DF_FILES_DIR)

    file_name_start = f'user{USER_ID}_df_'
    start_length = len(file_name_start)
    list_of_data = [i for i in list_of_data if i[:start_length] == file_name_start]
    print('-- list_of _data =-==')
    print(list_of_data)

    data_item_list = [i[start_length:i.find('.')] for i in list_of_data]
    try:
        data_item_list.remove('browse_apple')
    except:
        print('no browse_apple')

    print('-- data_itme_list_+new --')
    print(data_item_list)

    # data_item_list = ['steps', 'sleep', 'temp', 'cloudcover']
 


    #make static/dashbuttons
    dash_btns_dir = os.path.join(current_app.static_folder,'dash_btns')
    # sleep_dash_btns_dir = os.path.join(dash_btns_dir, 'sleep')
    dash_dependent_var_dash_btns_dir = os.path.join(dash_btns_dir, dash_dependent_var)
    
    if not os.path.exists(dash_dependent_var_dash_btns_dir):
        os.makedirs(dash_dependent_var_dash_btns_dir)

    # Buttons for dashboard table to toggle on/off correlations
    buttons_dict = {}
    user_btn_json_name = f'user{USER_ID}_buttons_dict.json'
    if request.method == 'POST':
        formDict = request.form.to_dict()
        logger_dash.info('formDict: ', formDict)
        if formDict.get('refresh_data'):
            logger_dash.info('- Refresh data button pressed -')
            #remove steps because unnecessary and potentially takes a long time
            data_item_sub_list = ['sleep', 'temp', 'cloudcover']
            create_df_files(USER_ID, data_item_sub_list)
        else:
            buttons_dict = buttons_dict_util(formDict, dash_dependent_var_dash_btns_dir, buttons_dict, user_btn_json_name)
        return redirect(url_for('dash.dashboard', dash_dependent_var=dash_dependent_var))

    # Read dict of user's chart data prefrences
    if os.path.exists(os.path.join(dash_dependent_var_dash_btns_dir,user_btn_json_name)):
        buttons_dict = buttons_dict_update_util(dash_dependent_var_dash_btns_dir, user_btn_json_name)

    df_dict = df_utils(USER_ID, data_item_list)

    ### Checking that the DF have data 
    list_of_user_data = [df_name  for df_name, df in df_dict.items() if not isinstance(df, bool)]

    # if user has no data return empty dashboard page
    if len(list_of_user_data) == 0:
        message = "There is no data attached to your user. Go to accounts and add location and oura information."
        return render_template('dashboard_empty.html', page_name=page_name, message = message)
    
    # If user has no data for dash_dependent_var return empty dashboard page
    if isinstance(df_dict.get(dash_dependent_var), bool):
        message = f"You have not added any {dash_dependent_var} data to your profile. Go to your accounts page to add {dash_dependent_var} data."
        return render_template('dashboard_empty.html', page_name=page_name, message=message)

    # Create dataframe of combined data by looping over df_dict and merging df's
    tuple_count = 0
    for _, df in df_dict.items():
        if not isinstance(df, bool) and tuple_count==0:
            df_all = df
            tuple_count += 1

        elif not isinstance(df, bool):
            df_all = pd.merge(df_all, df, how='outer')
    
    df_all = df_all.dropna(axis=1, how='all')#remove columns with all missing values

    if len(df_all)==0:# No weather data will cause this
        message = "Missing weather data. Go to your accounts page and add your location to see this dashboard."
        return render_template('dashboard_empty.html', page_name=page_name, message=message)


    # make each column into a list series
    series_lists_dict = {}
    for col_name in df_all.columns:
        if col_name == 'date':
            series_lists_dict[col_name] =[datetime.strptime(i,'%Y-%m-%d') for i in df_all['date'].to_list() ]
        else:
            series_lists_dict[col_name] = [i for i in df_all[col_name]]
    
    logger_dash.info('---- buttons_dict ___')
    logger_dash.info(buttons_dict)

    # send to chart making
    script_b, div_b, cdn_js_b = make_chart_util(series_lists_dict, buttons_dict)
    

    # Create names dict to show formatted names in Buttons
    formatted_names_dict = {'temp':'Temperature', 'cloudcover':'Cloud Cover', 'sleep': 'Oura Sleep', 'steps': 'Apple Step Count'}
    user_apple_browse_file = f"user{USER_ID}_df_browse_apple.pkl"
    user_apple_browse_path = os.path.join(config.DF_FILES_DIR, user_apple_browse_file)
    if os.path.exists(user_apple_browse_path):
        print(user_apple_browse_path)
        df_browse = pd.read_pickle(os.path.abspath(user_apple_browse_path))
        apple_browse_names_dict = {i.replace(" ", "_").lower():i for i in df_browse.type_formatted}
        formatted_names_dict = formatted_names_dict | apple_browse_names_dict


    # --- calcualute CORRELATIONS ---

    #Filter out rows where the dep vars are null
    df_interest = df_all[df_all[dash_dependent_var].notnull()]

    # Create dictionaries for {data_item: correaltion} (and {data_item: Not enough data})
    data_items_of_interest_list = list(set(data_item_list) & set(df_all.columns))
    corr_dict={}
    corr_dict_na={}
    for df_name in data_items_of_interest_list:
        corr_dict[df_name] = round(df_interest[df_name].corr(df_interest[dash_dependent_var]),2)


        if corr_dict[df_name] != corr_dict[df_name]:# Pythonic way for checking for nan
            corr_dict_na[df_name] = ["Not enough data",formatted_names_dict[df_name]]
            del corr_dict[df_name]
            
    # Remove depenedent variable for corrleations list
    del corr_dict[dash_dependent_var]
    

    
    # Sort correlations by most impactful by converting to DF
    if len(corr_dict) > 0:
        df_corr = pd.DataFrame.from_dict(corr_dict, orient='index')
        df_corr.rename(columns={list(df_corr)[0]:'correlation'}, inplace=True)
        print('--- df_corr ___ ')
        print(df_corr)
        df_corr['abs_corr'] = df_corr['correlation'].abs()
        df_corr = df_corr.sort_values('abs_corr', ascending=False)
        corr_dict = df_corr.to_dict().get('correlation')

        


        corr_dict = {key: ['{:,.0%}'.format(value), formatted_names_dict[key]] for key,value in corr_dict.items() }
    if len(corr_dict_na)>0:# Add back in any vars with "Not enough data" for correlation
        corr_dict = corr_dict | corr_dict_na


    print('--- corr_dict --')
    print(corr_dict)
    # btn_names_dict = {}
    # btn_names_dict['cloudcover'] = "Cloud cover"
    # btn_names_dict['temp'] = "Average outdoor temperature"
    # btn_names_dict['sleep'] = "Sleep score"
    # btn_names_dict['steps'] = "Daily step count"

    return render_template('dashboard.html', page_name=page_name,
        script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, 
        buttons_dict=buttons_dict, dash_dependent_var = dash_dependent_var)

