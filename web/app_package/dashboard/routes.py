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
from app_package.dashboard.utilsChart import make_oura_df, make_user_loc_day_df, \
    make_weather_hist_df, make_chart, buttons_dict_util, buttons_dict_update_util
from app_package.dashboard.utilsSteps import apple_hist_steps, oura_hist_util, \
    user_loc_day_util
import json
import os


dash = Blueprint('dash', __name__)

@dash.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    print('current_User: ', current_user.email)
    page_name = 'Dashboard'

    USER_ID = current_user.id if current_user.id !=2 else 1

    any_loc_hist = sess.query(User_location_day).filter_by(user_id=USER_ID).all()
    any_oura_hist = sess.query(Oura_sleep_descriptions).filter_by(user_id=USER_ID).all()
    any_apple_data = sess.query(Apple_health_export).filter_by(user_id=USER_ID).all()

    corr_dict = False

    # Buttons for dashboard table to toggle on/off correlations
    buttons_dict = {}
    dashboard_routes_dir = os.path.join(os.getcwd(),'app_package', 'dashboard')
    if request.method == 'POST':
        formDict = request.form.to_dict()

        buttons_dict = buttons_dict_util(formDict, dashboard_routes_dir, buttons_dict)

    if os.path.exists(os.path.join(dashboard_routes_dir,'buttons_dict.json')):
        buttons_dict = buttons_dict_update_util(dashboard_routes_dir)


    # 1) if user has apple_history
        # call def apple_hist_steps_util() -> returns df[date, sum_of_steps]

    # 2) if user has oura_history
    # call def oura_hist_steps_utils() -> returns df[date, oura_sleep_score] 

    # 3) if user has location
    # call def weather_hist() -> returns df[date, temperature, cloudiness]

    # 4) if users has all three



    if len(any_loc_hist) > 0 or len(any_oura_hist) > 0:
        
        print('*** Acceing for Strnagers Data ****')
        df_oura_scores = make_oura_df()
        if df_oura_scores is None:
            df_oura_scores = []

        df_loc_da = make_user_loc_day_df()
        if df_loc_da is None:
            df_loc_da = []

        df_weath_hist = make_weather_hist_df()
        if df_weath_hist is None:
            df_weath_hist = []


        
        # Make weather history for only days the user has locations i.e. match on date and loc_id based on df_loc_day
        df_user_date_temp = pd.merge(df_loc_da, df_weath_hist, 
            how='left', left_on=['date', 'location_id'], right_on=['date', 'location_id'])
        df_user_date_temp = df_user_date_temp[df_user_date_temp['temp'].notna()]

        print('---> THIS NEEDS TO be more than 0:::::: ', len(df_user_date_temp) )
        # print(df_user_date_temp)
        # print(df_oura_scores)



        if len(df_oura_scores) > 0 and len(df_user_date_temp) > 0:
        # if df_oura_scores is not None and df_user_date_temp is not None:
            print('-----> User has both oura and locaiton data')

            #TODO: This needs to concatenate
            df_oura_scores = df_oura_scores.set_index('date')
            df_user_date_temp = df_user_date_temp.set_index('date')

            df = pd.concat([df_user_date_temp, df_oura_scores], axis = 1)
            df.drop('id', inplace = True, axis = 1)
            df = df.where(pd.notnull(df), -99)
            df.reset_index(inplace = True)
            df['cloudcover'] = df['cloudcover'].astype(float)

            temp_data_list = [round(float(temp)) for temp in df['temp'].to_list() ]
            cloudcover_list = [round(float(cloudcover)) for cloudcover in df['cloudcover'].to_list() ]
            sleep_data_list = df['score'].to_list()
            dates_list =[datetime.strptime(i,'%Y-%m-%d') for i in df['date'].to_list() ]

            lists_tuple = (dates_list, sleep_data_list, temp_data_list, cloudcover_list)


            # resize df to remove empty avg temperature calculate correlation:
            df = df[df['temp']!=-99]   
            df = df[df.score != -99]    

            if len(df) > 2:
                print('--- Has enough observations for correlations ----')
                
                corr_dict = {}
                corr_dict['avg_temp'] = round(df['temp'].corr(df['score']),2)
                corr_dict['cloudiness'] = round(df['cloudcover'].corr(df['score']),2)
                # print(df['cloudcover'].to_list())
                # print(df.dtype)
            else:
                print('--- Has DOES NOT enough observations for correlations ----')
                corr_dict = 'too small sample'


        #If user has 
        elif len(df_oura_scores) > 0 and corr_dict==False:
            print('-----> User has only oura data')
        # elif df_oura_scores is not None:
            df_oura_scores = df_oura_scores.drop_duplicates(subset='date', keep='last')
            df = df_oura_scores.copy()
            dates_list =[datetime.strptime(i,'%Y-%m-%d') for i in df['date'].to_list() ]
            sleep_data_list = df['score'].to_list()
            temp_data_list = 'is empty'
            cloudcover_list = 'is empty'
            # lists_tuple = (dates_list, sleep_data_list, temp_data_list)
            
        elif len(df_user_date_temp) > 0 and corr_dict == False:
            print('-----> User has only locaiton data')
        # elif df_user_date_temp is not None:
            df = df_user_date_temp.copy()
            dates_list =[datetime.strptime(i,'%Y-%m-%d') for i in df['date'].to_list() ]
            temp_data_list = [round(float(temp)) for temp in df['temp'].to_list() ]
            cloudcover_list = [round(float(cloudcover)) for cloudcover in df['cloudcover'].to_list() ]
            # cloudcover_list = [cloudcover for cloudcover in df['cloudcover'].to_list() ]
            sleep_data_list = 'is empty'
            
        lists_tuple = (dates_list, sleep_data_list, temp_data_list, cloudcover_list)


        #Use list data to make chart
        script_b, div_b, cdn_js_b = make_chart(lists_tuple, buttons_dict)

        # print(script_b)

        return render_template('dashboard.html', page_name=page_name,
            script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, buttons_dict=buttons_dict)
    else:
        df = ''

        return render_template('dashboard_empty.html', page_name=page_name)




@dash.route('/dashboard_steps', methods=['GET', 'POST'])
@login_required
def dash_steps():
    page_name = "Steps Dashboard"


    USER_ID = current_user.id if current_user.id !=2 else 1

    # any_loc_hist = sess.query(User_location_day).filter_by(user_id=USER_ID).all()
    # any_oura_hist = sess.query(Oura_sleep_descriptions).filter_by(user_id=USER_ID).all()
    # any_apple_data = sess.query(Apple_health_export).filter_by(user_id=USER_ID).all()


    # Buttons for dashboard table to toggle on/off correlations
    buttons_dict = {}
    dashboard_routes_dir = os.path.join(os.getcwd(),'app_package', 'dashboard')
    if request.method == 'POST':
        formDict = request.form.to_dict()

        buttons_dict = buttons_dict_util(formDict, dashboard_routes_dir, buttons_dict)

    if os.path.exists(os.path.join(dashboard_routes_dir,'buttons_dict.json')):
        buttons_dict = buttons_dict_update_util(dashboard_routes_dir)

    # df_dict = {}
    corr_dict = {}

    # 1) if user has apple_history
        # call def apple_hist_steps_util() -> returns df[date, sum_of_steps]
    df_apple_steps = apple_hist_steps(USER_ID)
   

    # 2) if user has oura_history
    # call def oura_hist_steps_utils() -> returns df[date, oura_sleep_score]
    df_oura_sleep = oura_hist_util(USER_ID)


    # 3) if user has location
    # call def weather_hist() -> returns df[date, temperature, cloudiness]
    df_weather = user_loc_day_util(USER_ID)


    #4) steps and temp and cloudiness
    if df_apple_steps != False and df_weather != False:
        df_steps_temp = pd.merge(df_apple_steps, df_weather, how='left', left_on=['date'], right_on=['date'])
        df_steps_temp = df_steps_temp[df_steps_temp['temp'].notna()]

        corr_dict['avg_temp'] = round(df_steps_temp['temp'].corr(df_steps_temp['steps']),2)
        corr_dict['cloudiness'] = round(df_steps_temp['cloudcover'].corr(df_steps_temp['steps']),2)

    #6) steps and sleep
    if df_apple_steps != False and df_oura_sleep != False:
        df_steps_oura = pd.merge(df_apple_steps, df_oura_sleep, how='left', left_on=['date'], right_on=['date'])
        df_steps_oura = df_steps_oura[df_oura_sleep['score'].notna()]

        corr_dict['sleep_score'] = round(df_steps_oura['score'].corr(df_steps_oura['steps']),2)

    #TODO: Merge steps, oura, and temperature into one df using most dates possible
    #TODO: convert to lists for each serires
    # TODO: pass the series to make chart and basically copy what the sleep make_chart function does


    #Use list data to make chart
    script_b, div_b, cdn_js_b = "","",""
    corr_dict =""

    return render_template('dashboard_steps.html', page_name=page_name,
        script_b = script_b, div_b = div_b, cdn_js_b = cdn_js_b, corr_dict=corr_dict, buttons_dict=buttons_dict)
    # else:
    #     df = ''

    #     return render_template('dashboard_steps.html', page_name=page_name)

    # return render_template('dashboard_steps.html', page_name=page_name)