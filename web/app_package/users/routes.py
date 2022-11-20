from contextlib import redirect_stderr
from flask import Blueprint
from flask import render_template, url_for, redirect, flash, request, \
    abort, session, Response, current_app, send_from_directory, make_response
import bcrypt
from ws_models01 import sess, Base, Users, login_manager, Oura_token, Locations, \
    Weather_history, User_location_day, Oura_sleep_descriptions, Posts, \
    Apple_health_export, User_notes
from flask_login import login_required, login_user, logout_user, current_user
import requests
#Oura
from app_package.users.utils import oura_sleep_call, oura_sleep_db_add
#Location
from app_package.users.utils import call_location_api, location_exists, \
    add_weather_history, gen_weather_url, add_new_location
#Email
from app_package.users.utils import send_reset_email
#Apple
from app_package.users.utilsApple import make_dir_util, decompress_and_save_apple_health, \
    add_apple_to_db, report_process_time, clear_df_files
from app_package.users.utilsXmlUtility import xml_file_fixer, compress_to_save_util
from app_package.users.utilsDf import create_df_files, remove_df_pkl, create_raw_df, \
    browse_apple_data, create_df_files_apple
#More Weather
from app_package.users.utilsMoreWeather import user_oldest_day_util, add_user_loc_days, \
    search_weather_dict_list_util
from app_package.users.utils import add_weather_history_more
#Admin
from app_package.users.utils import send_confirm_email, make_user_item_list, \
    edit_user_items_dict_util, get_apple_health_count, get_user_df_count


from sqlalchemy import func
from datetime import datetime, timedelta
import time
import logging
from logging.handlers import RotatingFileHandler
import os
import json
from ws_config01 import ConfigDev, ConfigProd
import xmltodict
import pandas as pd

if os.environ.get('TERM_PROGRAM')=='Apple_Terminal' or os.environ.get('COMPUTERNAME')=='NICKSURFACEPRO4':
    config = ConfigDev()
    testing_oura = True
else:
    config = ConfigProd()
    testing_oura = False


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


salt = bcrypt.gensalt()


users = Blueprint('users', __name__)

@users.route('/', methods=['GET', 'POST'])
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))


    make_dir_util(config.DF_FILES_DIR)
    make_dir_util(config.DB_DOWNLOADS)


    latest_post = sess.query(Posts).all()
    if len(latest_post) > 0:
        latest_post = latest_post[-1]

        blog = {}
        keys = latest_post.__table__.columns.keys()
        blog = {key: getattr(latest_post, key) for key in keys}
        blog['blog_name']='blog'+str(latest_post.id).zfill(4)
        blog['date_published'] = blog['date_published'].strftime("%b %d %Y")
        print(blog)
    else:
        blog =''


    if request.method == 'POST':
        formDict = request.form.to_dict()
        if formDict.get('login'):
            return redirect(url_for('users.login'))
        elif formDict.get('register'):
            return redirect(url_for('users.register'))

    return render_template('home.html', blog=blog)

@users.route('/login', methods = ['GET', 'POST'])
def login():
    print('* in login *')
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
    page_name = 'Login'
    if request.method == 'POST':
        formDict = request.form.to_dict()
        print('**** formDict ****')
        print(formDict)
        email = formDict.get('email')

        user = sess.query(Users).filter_by(email=email).first()
        print('user for logging in:::', user)
        # verify password using hash
        password = formDict.get('password_text')

        if user:
            if password:
                if bcrypt.checkpw(password.encode(), user.password):
                    print("match")
                    login_user(user)
                    # flash('Logged in succesfully', 'info')

                    return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
                else:
                    flash('Password or email incorrectly entered', 'warning')
            else:
                flash('Must enter password', 'warning')
        elif formDict.get('btn_login_as_guest'):
            print('GUEST EMAIL::: ', current_app.config['GUEST_EMAIL'])
            user = sess.query(Users).filter_by(id=2).first()
            login_user(user)
            # flash('Logged in succesfully as Guest', 'info')

            return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
        else:
            flash('No user by that name', 'warning')

        # if successsful login_something_or_other...



    return render_template('login.html', page_name = page_name)

@users.route('/register', methods = ['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
    page_name = 'Register'
    if request.method == 'POST':
        formDict = request.form.to_dict()
        new_email = formDict.get('email')

        check_email = sess.query(Users).filter_by(email = new_email).all()
        if len(check_email)==1:
            flash(f'The email you entered already exists you can sign in or try another email.', 'warning')
            return redirect(url_for('users.register'))

        hash_pw = bcrypt.hashpw(formDict.get('password_text').encode(), salt)
        new_user = Users(email = new_email, password = hash_pw)
        sess.add(new_user)
        sess.commit()


        # Send email confirming succesfull registration
        try:
            send_confirm_email(new_email)
        except:
            flash(f'Problem with email: {new_email}', 'warning')
            return redirect(url_for('users.login'))

        #log user in
        print('--- new_user ---')
        print(new_user)
        login_user(new_user)
        flash(f'Succesfully registered: {new_email}', 'info')
        return redirect(url_for('users.login'))

    return render_template('register.html', page_name = page_name)


@users.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('users.home'))


@users.route('/account', methods = ['GET', 'POST'])
@login_required
def account():
    logger_users.info(f"--- user accessed Accounts")
    page_name = 'Account Page'
    email = current_user.email

    logger_users.info(f'Current User: {current_user.email}')

    user = sess.query(Users).filter_by(id = current_user.id).first()

    if user.lat == None or user.lat == '':
        existing_coordinates = ''
        city_name = ''
    else:
        existing_coordinates = f'{user.lat}, {user.lon}'
        location =sess.query(Locations).get(location_exists(user))
        city_name = f"{location.city}, {location.country}"


    if request.method == 'POST':
        if current_user.id == 2:
            flash('Guest can enter any values but they will not change the database', 'info')
            return redirect(url_for('users.account'))
        else:
            startTime_post = time.time()
            formDict = request.form.to_dict()
            new_location = formDict.get('location_text')
            email = formDict.get('email')
            # yesterday = datetime.today() - timedelta(days=1)
            # yesterday_formatted =  yesterday.strftime('%Y-%m-%d')

            #2) User adds location data
            if new_location != existing_coordinates:
                if new_location == '':                          #<--- User is removing their location data
                    user.lat = None
                    user.lon = None
                    sess.commit()
                    flash('User coordinates removed succesfully','info')
                    
                    #remove current user's history
                    sess.query(User_location_day).filter_by(user_id=current_user.id).delete()
                    sess.commit()

                else:                                           #<-- User is updating their location
                    # add lat/lon to users table
                    user.lat = formDict.get('location_text').split(',')[0]
                    user.lon = formDict.get('location_text').split(',')[1]

                    #edit user weather date
                    if isinstance(user.notes,str):
                        user_notes_dict = edit_user_items_dict_util(user.notes)
                    else:
                        user_notes_dict ={}
                    if not user_notes_dict.get('weather_hist_date'):
                        print('-- config.DAYS_HIST_LIMIT_STD --')
                        weather_limit_date = datetime.now() - timedelta(config.DAYS_HIST_LIMIT_STD)
                        weather_limit_date_str = weather_limit_date.strftime("%Y-%m-%d")
                        user_notes_dict['weather_hist_date'] = weather_limit_date_str
                        notes_string = ''
                        for data_item_name,data_item_value in user_notes_dict.items():
                            notes_string = notes_string + data_item_name + ":" + data_item_value + ";"

                        user.notes = notes_string

                    sess.commit()
                    logger_users.info('---- Added new coordinates for user ----')

                    location_id = location_exists(user)# --------- Check if coordinates are in Locations table
                    if location_id == 0:     #<--- Coordinates NOT in database
                        logger_users.info('--- location does not exist, in process of adding ---')
                        location_api_response = call_location_api(user)
                        if isinstance(location_api_response,dict):
                            location_id = add_new_location(location_api_response)

                    else:   #<--- Coordinates in database
                        logger_users.info('--- location already exists in WS database ----')

                    # make list of past 14 days [Y-M-D]
                    today = datetime.now()
                    today_list = [(today-timedelta(days=i)).strftime('%Y-%m-%d') for i in range(1,15)]

                    # Add/update user_loc_day for all in list

                    for day in today_list:
                        # user_loc_day_hist = sess.query(User_location_day).filter_by(user_id=current_user.id, date=day).first()
                        #11/2/2022 commented out delete possible history because:
                        # - when user clears out locaiton they also remove user_loc_day for themselves
                        # - adding funcionality for user to get weather data as far back as they have steps or sleep.
                        # if user_loc_day_hist:
                        #     sess.query(User_location_day).filter_by(user_id = current_user.id , date=day).delete()
                        #     sess.commit()

                        new_user_loc_day = User_location_day(user_id=current_user.id,
                            location_id = location_id,
                            date = day,
                            # local_time = f"{str(datetime.now().hour)}:{str(datetime.now().minute)}",
                            row_type='user input')
                        sess.add(new_user_loc_day)
                        sess.commit()


                    # flash(f"Updated user's location and add weather history", 'info')
                    weather_api_trouble = False
                    for day in today_list:
                        loc_day_weather_hist = sess.query(Weather_history).filter_by(location_id=location_id, date_time=day).first()
                        if loc_day_weather_hist is None:
                            logger_users.info(f'--- Calling Weather api for {day} in loc_id: {location_id} ----')
                            weather_api_response = requests.get(gen_weather_url(location_id, day))
                            if weather_api_response.status_code == 200:
                                add_weather_history(weather_api_response, location_id)
                            else:
                                logger_users.info(f'--- Bad API call for Weather history {day} in location_id: {location_id} ----')
                                logger_users.info(f'--- Status code: {weather_api_response.status_code} ----')
                                weather_api_trouble = True


                        else:
                            logger_users.info(f'--- Weather history already exists for {day} in loc_id: {location_id} ----')

                    if weather_api_trouble == True:
                        flash("Some days might not have been updated with weather due to problems with Weather API", "info")
                    else:
                        flash("Recent weather history updated!", "success")

                # Make DF for user and weather
                create_df_files(current_user.id, ['temp', 'cloudcover'])



            #3) User changes email
            if email != user.email:

                #check that not blank
                if email == '':
                    flash('Must enter a valid email.', 'warning')
                    return redirect(url_for('users.account'))

                #check that email doesn't alreay exist outside of current user
                other_users_email_list = [i.email for i in sess.query(Users).filter(Users.id != current_user.id).all()]

                if email in other_users_email_list:
                    flash('That email is being used by another user. Please choose another.', 'warning')
                    return redirect(url_for('users.account'))

                #update user email
                user.email = email
                sess.commit()
                flash('Email successfully updated.', 'info')
                return redirect(url_for('users.account'))

            #END of POST
            executionTime = (time.time() - startTime_post)
            logger_users.info('POST time in seconds: ' + str(executionTime))
            return redirect(url_for('users.account'))


    print('existing_coordinates: ', existing_coordinates)
    return render_template('accounts.html', page_name = page_name, email=email,
        location_coords = existing_coordinates, city_name = city_name)


@users.route('/add_apple', methods=["GET", "POST"])
def add_apple():

    USER_ID = current_user.id if current_user.id !=2 else 1
    # existing_records = sess.query(Apple_health_export).filter_by(user_id=current_user.id).all()
    file_name = f'user{USER_ID}_df_browse_apple.pkl'
    file_path = os.path.join(config.DF_FILES_DIR, file_name)
    if os.path.exists(file_path):
        df = pd.read_pickle(file_path)
        existing_records = df.record_count.sum()
        apple_records = "{:,}".format(existing_records)
    else:
        apple_records = 0
    # apple_records = "{:,}".format(10000)

    # make APPLE_HEALTH_DIR
    apple_health_dir = config.APPLE_HEALTH_DIR
    make_dir_util(apple_health_dir)

    logger_users.info(f"--- POSTING Apple Health Data (user: {current_user.id}) ---")
    start_post_time = time.time()

    if request.method == 'POST':
        if current_user.id ==2:
            flash("Guest cannot change data. Register and then add data.", "info")
            return redirect(url_for('users.add_apple'))
        filesDict = request.files
        apple_health_data = filesDict.get('apple_health_data')

        if filesDict.get('apple_health_data'):
            logger_users.info(filesDict.get('apple_health_data').filename)

        formDict = request.form.to_dict()

        #4) Apple health data
        if apple_health_data:


            # Measuring file loading time and size
            filesize = float(request.cookies.get('filesize'))
            filesize_mb = round(filesize/ 10**6,1)
            filesize = "{:,}".format(filesize_mb)
            logger_users.info(f"Compressed filesize: {filesize} Mb")


            new_file_path = decompress_and_save_apple_health(apple_health_dir, apple_health_data)
            xml_file_name = os.path.basename(new_file_path)
            # new_rec_count = 9

            filesize_mb = os.stat(new_file_path).st_size / (1024 * 1024)
            logger_users.info(f"--- Decompressed Apple Health Export file size: {filesize_mb} MB ---")

            # 1) if size small try to xmltodict

            if filesize_mb < 100:
                logger_users.info(f"--- Apple export is small processing file while user waits ---")
                try:

                    with open(new_file_path, 'r') as xml_file:
                        xml_dict = xmltodict.parse(xml_file.read())
                    
                except:
                    #Trying to fix file
                    logger_users.info(f'---- xmltodict failed first go around. Sending to xml_file_fixer --')
                    xml_dict = xml_file_fixer(new_file_path)
                    if isinstance(xml_dict, str):
                        logger_users.info(f'---- Failed to process Apple file. No header for data found')
                        flash('Failed to process Apple file. No header for data found', 'warning')
                        return redirect(url_for('users.add_apple'))
                
                try:
                    df_uploaded_record_count = add_apple_to_db(xml_dict)
                    logger_users.info('- Successfully added xml to database!')

                    ###############################################
                    # if loads successfully check for exisiting 
                    # user_[id]_df_apple_health_.pkl and delete
                    ################################################
                    if os.path.exists(config.DF_FILES_DIR):
                        clear_df_files(USER_ID)

                except:
                    logger_users.info('---- Failed to add data to database')
                    return redirect(url_for('users.add_apple'))
                
                # Store successful download in compressed version of /databases/apple_health_data/...
                compress_to_save_util(os.path.basename(new_file_path))

            else:
                logger_users.info(f"--- Apple export is large. Send to API. Email user when complete ---")
                headers = { 'Content-Type': 'application/json'}
                payload = {}
                payload['password'] = config.WSH_API_PASSWORD
                payload['user_id'] = current_user.id
                payload['xml_file_name'] = xml_file_name
                r_store_apple = requests.request('GET', config.WSH_API_URL_BASE + '/store_apple_health', headers=headers, 
                                 data=str(json.dumps(payload)))
                logger_users.info(f'-- Sent api file processing request. Response status code: {r_store_apple.status_code}')
                
        ##### TODO: intentional ERROR so the javascript flag is warning that the user will be emailed ***
                return redirect(url_for('users.add_apple'))
                
            logger_users.info(report_process_time(start_post_time))

            if isinstance(df_uploaded_record_count, str):
                flash('This file cannot be read. Contact nick@dashanddata.com if you would like him to fix it', 'warning')
                return redirect(url_for('users.add_apple'))


            # At this point we already know if the file can be used or not
            flash(f"succesfully saved {'{:,}'.format(df_uploaded_record_count)} records from apple export", 'info')


        elif formDict.get('btn_delete_apple_data'):
            logger_users.info('- delete apple data -')


            # print('Delete apple data')
            rows_deleted = sess.query(Apple_health_export).filter_by(user_id = current_user.id).delete()
            sess.commit()
            flash(f"Removed {'{:,}'.format(rows_deleted)} Apple Health records from What Sticks data storage", 'warning')


            ### Best solution is to rename apple files to user{id}_df_apple_health_{data_item}.pkl

            # Delete user apple_health df_files
            pickle_files_list = os.listdir(config.DF_FILES_DIR)
            for pickle_file in pickle_files_list:
                if pickle_file.find(f'user{USER_ID}_df_apple_health') > -1:
                    # if pickle_file.find('df_sleep.pkl') == -1 and pickle_file.find('df_temp.pkl')== -1 and \
                    #     pickle_file.find('df_cloudcover.pkl') == -1:
                    os.remove(os.path.join(config.DF_FILES_DIR, pickle_file))
                elif pickle_file.find(f'user{USER_ID}_df_browse_apple.pkl') > -1:
                    os.remove(os.path.join(config.DF_FILES_DIR,pickle_file))
            logger_users.info('-- removed user df_files --')






        ###########################################################
        # IF any change to APPLE data: Make DF for user and APPLE #
        ###########################################################
        # create_df_files(current_user.id, ['steps'])
        # create_df_files(current_user.id, ['apple_health_step_count'])

        # create_df_files_apple(USER_ID,data_item_list, data_item_name_show, method, data_item_apple_type_name)
        create_df_files_apple(USER_ID,['apple_health_step_count'], 'Step Count', 'sum', 'HKQuantityTypeIdentifierStepCount')

        return redirect(url_for('users.add_apple'))
    return render_template('add_apple.html', apple_records=apple_records, isinstance=isinstance, str=str)


@users.route('/add_more_apple', methods=['GET', 'POST'])
@login_required
def add_more_apple():
    # table_name = 'apple_health_export_'
    USER_ID = current_user.id if current_user.id !=2 else 1
    file_name = f'user{USER_ID}_df_browse_apple.pkl'
    file_path = os.path.join(config.DF_FILES_DIR, file_name)
    
    # check browse_apple.pkl file exists and if not create it
    if not os.path.exists(file_path):
        browse_apple_data(USER_ID)

    df = pd.read_pickle(file_path)

    list_of_forms = ['form_'+str(i) for i in range(1,len(df)+1)]
    
    df.reset_index(inplace=True)
    df_records_list = df.to_dict('records')
    df_records_list_dict =[json.dumps(i) for i in df_records_list]
    df.set_index('index', inplace=True)

    if request.method == 'POST':

        if current_user.id ==2:
            flash("Guest cannot change data. Register and then add data.", "info")
            return redirect(url_for('users.add_more_apple'))

        formDict = request.form.to_dict()
        print(formDict)

        # index value assigned at creation of browse_apple df
        data_item_id = formDict.get('data_item_index') if formDict.get('data_item_index') else formDict.get('delete_data_item_index')
        data_item_id = int(data_item_id)
        # Apple data name with spaces and capital letters
        data_item_name_show = df.at[data_item_id,'type_formatted'] 
        
        # Apple data name lowercases no spaces for df headings, pkl file names, dict key names
        data_item_list = ['apple_health_' + df.at[data_item_id,'type_formatted'].replace(" ", "_").lower()]
        
        # Apple data name from XML file
        data_item_apple_type_name = df.at[data_item_id,'type'] 

        if formDict.get('btn_add') == 'add' or formDict.get('btn_average')=='average':
            print('-- btn_add ', data_item_id)
            # # index value assigned at creation of browse_apple df
            # data_item_id = int(formDict.get('data_item_index'))
            
            if formDict.get('btn_add') == 'add' :
                agg_method = 'sum'
            elif formDict.get('btn_average') == 'average':
                agg_method = 'average'
            # agg_method = formDict.get('agg_method')
            # agg_method = 'sum'
            

            df_dict = create_df_files_apple(USER_ID, data_item_list , data_item_name_show=data_item_name_show,
                method=agg_method, data_item_apple_type_name = data_item_apple_type_name)

            ##############################################
            #Could Do But not hurting anything now
            #  Checks for df to actually have numeric non-zero data
            # --> if len(df_dict[data_item_list[0]]) >0:
            # --> check column of interest has numeric values
            # If fails either return flash('No usable data in these records', 'warning')
            ###################################

            # update browse df 
            df.at[data_item_id,'df_file_existing'] = 'true'
            df.to_pickle(file_path)
            
            print(f'-- wrote to {file_path}')

            #Add note to user with new data specs
            user = sess.query(Users).get(current_user.id)
            user.notes = f"{user.notes};apple_health_data:{data_item_apple_type_name}_{agg_method};"
            sess.commit()

            flash(f'Successfully added {data_item_name_show}', 'info')





        elif formDict.get('btn_delete') == 'true':
            # print(f'delete data item: {formDict.get("delete_data_item_index")}')
            print('-- in delete --')
            print(data_item_id)

            # delete df_pkl file
            remove_df_pkl(USER_ID, data_item_list[0])

            # delte true from existing column in df
            df.at[data_item_id,'df_file_existing'] = ''
            df.to_pickle(file_path)
            flash(f'Successfully removed {data_item_name_show} from dashboards', 'info')
        elif formDict.get('btn_closer_look'):
            return redirect(url_for('users.under_construction'))
            #TODO: 
            # make name for this data time file 
            apple_health_export_df_file_name = f'check_user{USER_ID}_df_apple_health_{data_item_apple_type_name}.pkl'

            # CHECK if request df file exists before searching/createing
            if not os.path.exists(os.path.join(config.DF_FILES_DIR, apple_health_export_df_file_name)):
                # create df
                df = create_raw_df(USER_ID, Apple_health_export, 'apple_health_export_')
                df = df[df['type']==data_item_apple_type_name]
                # to_pickle
                df.to_pickle(os.path.join(config.DF_FILES_DIR, apple_health_export_df_file_name))

            return redirect(url_for('users.apple_closer_look', data_item_id= data_item_id))
        return redirect(url_for('users.add_more_apple'))

    return render_template('add_apple_more.html', df_records_list=df_records_list,
    df_records_list_dict=df_records_list_dict,
        list_of_forms=list_of_forms)


@users.route('/under_construction')
@login_required
def under_construction():
    return render_template('under_construction.html')

@users.route('/apple_closer_look/<data_item_id>', methods=["GET", "POST"])
@login_required
def apple_closer_look(data_item_id):
    print(' -- ENTERED apple_closer_look --')
    USER_ID = current_user.id if current_user.id !=2 else 1
    browse_file_name = f'user{USER_ID}_df_browse_apple.pkl'
    browse_file_path = os.path.join(config.DF_FILES_DIR, browse_file_name)
    df = pd.read_pickle(browse_file_path)

    # print('--- request.args ---')
    # print(request.args)

    check_all = request.args.get('check_all')
    warning = request.args.get('warning')
 
    # Apple data name with spaces and capital letters
    data_item_name_show = df.at[int(data_item_id),'type_formatted'] 
    # Apple data name from XML file
    data_item_apple_type_name = df.at[int(data_item_id),'type'] 

    # Get apple data filterd on user_id and data_item
    apple_health_export_df_file_name = f'check_user{USER_ID}_df_apple_health_{data_item_apple_type_name}.pkl'
    apple_health_export_df_file_path = os.path.join(config.DF_FILES_DIR, apple_health_export_df_file_name)

    # print(apple_health_export_df_file_path)
    # print('* Do we get this far? *')
    flag_df_abbrev = False
    abbrev_df_message = ''
    if os.path.exists(apple_health_export_df_file_path):
        df = pd.read_pickle(apple_health_export_df_file_path)
        length = "{:,}".format(len(df))
        if len(df) >1000:
            df_abbrev = df.iloc[:1000]
            flag_df_abbrev = True
            abbrev_df_message = f'Too many rows to show all. Only loaded 1,000 of {length}. '
        print('-- Reading from Apple Health pickle file --')
    else:
        flash('Something went wrong. Go back delete exisiting data and come back to this page.','warning')
        return redirect(url_for('users.apple_closer_look', data_item_id=data_item_id))
    
    # Get unique column values from full dataset
    source_name_list = list(df.sourceName.unique())
    source_version_list = list(df.sourceVersion.unique())
    unit_list = list(df.unit.unique())

    # Abbreviate dataset if necessary
    if flag_df_abbrev:
        df_records_list = df_abbrev.to_dict('records')
        # flash('Too many rows to show all. Only have 1,000 showing', 'info')
    else:
        df_records_list = df.to_dict('records')


    col_names = list(df_records_list[0].keys())

    if request.method == 'POST':
        formDict = request.form.to_dict()
        print('-- formDict --')
        print(formDict)

        # check formDict has at least one source_name_, source_version_, unit_name_
        check_string_list = ['source_name_','source_version_', 'unit_name_' ]
        check_string_dict = {'source_name_':False,'source_version_':False, 'unit_name_':False}
        keys_list = list(formDict.keys())
        
        
        ### Check by check string for unfilled 
        missing = ''
        for check_string in check_string_list:
            # if any(check_string in key for key in keys_list ):
            #     if check_string_dict[check_string] == False:
            #         check_string_dict[check_string] = formDict.get(key)
            if not any(check_string in key for key in keys_list ) and missing=='':
                missing = check_string
            elif not any(check_string in key for key in keys_list ):
                missing = missing + ', ' + check_string
                
        if missing != '':
            flash(f'Must pick at least one of: {missing}', 'warning')
            return redirect(url_for('users.apple_closer_look', data_item_id = data_item_id, warning=True))



        if formDict.get('btn_check_all')=='true':
            print('check_all * True * ')
            check_all=True
            # return redirect(url_for('users.apple_closer_look', data_item_id=data_item_id, check_all=check_all))
        elif formDict.get('btn_check_all')=='false':
            print('check_all * False * ')
            check_all=False
            # return redirect(url_for('users.apple_closer_look', data_item_id=data_item_id, check_all=check_all))

        elif formDict.get('btn_add_data')=='true':
            print('-- add data --')
            check_all = False


        # filter df on source_name_

        # filter df on sourc_version
        # filter on unit_name

        # create pickle file

        return redirect(url_for('users.apple_closer_look', data_item_id=data_item_id, check_all=check_all,
            abbrev_df_message = abbrev_df_message
            ))





    return render_template('add_apple_closer_look.html', data_item_name_show = data_item_name_show,
        col_names=col_names, df_records_list = df_records_list, source_name_list=source_name_list,
        source_version_list=source_version_list, unit_list=unit_list, check_all=check_all,
        abbrev_df_message = abbrev_df_message
        )



@users.route('/add_oura', methods=["GET", "POST"])
@login_required
def add_oura():
    logger_users.info(f"--- Add Oura route ---")
    
    existing_records = sess.query(Oura_sleep_descriptions).filter_by(user_id=current_user.id).all()
    oura_sleep_records = "{:,}".format(len(existing_records))

    existing_oura_token =sess.query(Oura_token, func.max(
        Oura_token.id)).filter_by(user_id=current_user.id).first()[0]


    if existing_oura_token:
        oura_token = current_user.oura_token_id[-1].token
        existing_oura_token_str = str(existing_oura_token.token)
    else:
        oura_token = ''
        existing_oura_token_str = ''

    # logger_users.info(f"--- POST (calling) Oura Ring (user: {current_user.id}) ---")
    # print('-- Oura Ring --')
    start_post_time = time.time()

    if request.method == 'POST':
        formDict = request.form.to_dict()
        logger_users.info(formDict)
        if current_user.id ==2:
            flash("Guest cannot change data. Register and then add data.", "info")
            return redirect(url_for('users.add_oura'))



        oura_token_user = sess.query(Oura_token).filter_by(user_id=current_user.id).first()
        if oura_token_user:
            logger_users.info(f"oura_token_user: {oura_token_user}")
            oura_token_id = oura_token_user.id

        if formDict.get('btn_link_oura'):

            startTime_post = time.time()
            # formDict = request.form.to_dict()
            new_token = formDict.get('oura_token_textbox')
            # new_location = formDict.get('location_text')
            # email = formDict.get('email')
            user = sess.query(Users).filter_by(id = current_user.id).first()
            yesterday = datetime.today() - timedelta(days=1)
            yesterday_formatted =  yesterday.strftime('%Y-%m-%d')



            #1) User adds Oura_token data
            if new_token != existing_oura_token_str:#<-- if new token is different
                logger_users.info('------ New token detected ------')
                #1-1a) if user has token replace it
                if existing_oura_token:
                    existing_oura_token.token = new_token
                    sess.commit()
                    oura_token_id = existing_oura_token.id
                    logger_users.info('One alrady exists ---> replace exisiting token')
                #1-1b) else add new token
                else:
                    print('Completely new token')
                    new_oura_token = Oura_token(user_id = current_user.id,
                        token = new_token)
                    sess.add(new_oura_token)
                    sess.commit()

                    oura_token_id = new_oura_token.id

                #1-1b-1) check if user has oura data yesterday
                oura_yesterday = sess.query(Oura_sleep_descriptions).filter_by(
                    user_id = current_user.id,
                    summary_date = yesterday_formatted).first()

                # --> 1-1b-1b) if no data yesterday, call API
                if not oura_yesterday and new_token != '':

                    if testing_oura:# use local json file
                        json_utils_dir = r"/Users/nick/Documents/_testData/json_utils_dir_FromScheduler"
                        with open(os.path.join(json_utils_dir, '_oura2_call_oura_api.json')) as json_file:
                            sleep_dict = json.loads(json.load(json_file))

                        sleep_dict = sleep_dict.get(str(current_user.id))
                        logger_users.info(f"--- Adding oura data from Local json file ---")
                    else:# Make api call
                        sleep_dict = oura_sleep_call(new_token)



                    if isinstance(sleep_dict,dict):
                        sessions_added = oura_sleep_db_add(sleep_dict, oura_token_id)
                        flash(f'Successfully added {str(sessions_added)} sleep sesions and updated user Oura Token', 'info')
                    else:
                        logger_users.info(f'** Unable to get data from Oura API becuase {sleep_dict}')
                        flash(f'Unable to get data from Oura API becuase {sleep_dict}', 'warning')
                elif not new_token:
                    flash('User oura token successfully removed','info')
                    logger_users.info('** removed oura token from user')
                else:
                    logger_users.info('-- date detected yesterday for this user')
                    logger_users.info(oura_yesterday)



        elif formDict.get('recall_api'):
            if not existing_oura_token_str in ["", None]:
                logger_users.info('--- recall_api')
                if testing_oura:# use local json file
                    json_utils_dir = r"/Users/nick/Documents/_testData/json_utils_dir_FromScheduler"
                    with open(os.path.join(json_utils_dir, '_oura2_call_oura_api.json')) as json_file:
                        sleep_dict = json.loads(json.load(json_file))

                    sleep_dict = sleep_dict.get(str(current_user.id))

                    logger_users.info(sleep_dict.keys())
                    logger_users.info(f"--- Adding oura data from Local json file ---")
                else:# Make api call
                    sleep_dict = oura_sleep_call(new_token)

                if isinstance(sleep_dict,dict):
                    sessions_added = oura_sleep_db_add(sleep_dict, oura_token_id)
                    flash(f'Successfully added {str(sessions_added)} sleep sesion(s)', 'info')
            else:
                flash(f"Must have a Oura Token", "warning")

        elif formDict.get('btn_delete_data'):
            logger_users.info('----> delete button pressed')
            # sleep_session_date_for_delete = "2022-10-23"
            delete_count = sess.query(Oura_sleep_descriptions).filter_by(user_id = current_user.id).delete()
            sess.query(Oura_token).filter_by(user_id=current_user.id).delete()
            sess.commit()
            
            # Delete user df.pkl files
            pickle_files_list = os.listdir(config.DF_FILES_DIR)
            for pickle_file in pickle_files_list:
                if pickle_file.find(f'user{current_user.id}_df_oura_') > -1:
                    os.remove(os.path.join(config.DF_FILES_DIR, pickle_file))

            logger_users.info('* Delete Oura Successfull ')
            flash(f"Removed {delete_count} records", "warning")
        
        
        ###########################################################
        # IF any change to OURA data: Make DF for user sleep #
        ###########################################################
        create_df_files(current_user.id, ['oura_sleep_tonight', 'oura_sleep_last_night'])
        
        return redirect(url_for('users.add_oura'))

    return render_template('add_oura.html', oura_sleep_records = oura_sleep_records,
        oura_token = oura_token)



@users.route('/add_more_weather', methods=["GET","POST"])
@login_required
def add_more_weather():
    if current_user.lat == None:
        flash("Must add location before adding more weather data", "warning")
        return redirect(url_for('users.account'))
    USER_ID = current_user.id if current_user.id !=2 else 1
    file_path = config.DF_FILES_DIR
    oldest_date_str = user_oldest_day_util(USER_ID, file_path)
    print('USErs oldest_date_str: ', oldest_date_str)

    user_notes_dict = edit_user_items_dict_util(current_user.notes)
    if user_notes_dict.get('weather_hist_date'):
        hist_limit_date = user_notes_dict.get('weather_hist_date')
        oldest_date_str = hist_limit_date
    else:
        hist_limit_date=''

    #Make a store visual crossing api weather call folder to store calls in case I
    # make a call that doesn't get stored
    vc_api_calls_dir = os.path.join(logs_dir, "vc_api_call_responses")
    make_dir_util(vc_api_calls_dir)
    
    if request.method == 'POST':
        logger_users.info(f"- POST request in add_more_weather -")
        formDict = request.form.to_dict()
        oldest_date_str = formDict.get('get_data_from_date')

        user = sess.query(Users).get(USER_ID)
        loc_id = location_exists(user)
        print('- formDcit =')
        print(formDict)

        # Add row for user to have user_loc_days
        add_user_loc_days(oldest_date_str, USER_ID, loc_id)

        # This is list of dict {"start":date,"end":date} for each gap of weather hist since oldest_date_str
        search_weather_dates_dict_list = search_weather_dict_list_util(oldest_date_str, loc_id)

        # make similar add_user_loc_days but looping through historical weather for loc_id=loc_id
        ### This get dates_call_dict

        logger_users.info(f"- WS finds that the user could add the following dates to complement their existing WS data -")
        logger_users.info(f"{search_weather_dates_dict_list}")

        call_list = []
        call_response = []
        call_file =[]

        for gap in search_weather_dates_dict_list:
            loc = sess.query(Locations).get(loc_id)
            location_coords = f"{loc.lat}, {loc.lon}"
            weather_call_url =f"{config.VISUAL_CROSSING_BASE_URL}{location_coords}/{str(gap.get('start'))}/{str(gap.get('end'))}?key={config.VISUAL_CROSSING_TOKEN}&include=current"
            logger_users.info(gap)
            logger_users.info(weather_call_url)
            r_history = requests.get(weather_call_url)
            logger_users.info(f"--- Visual Crossing ApI call response: {r_history.status_code} ---")

            if r_history.status_code == 200:
                upload_success_count = add_weather_history_more(r_history, loc_id)
                logger_users.info(f"--- Successfully added {upload_success_count} ---")
                
                save_vc_response_file_name = f"vc_response{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(os.path.join(vc_api_calls_dir, save_vc_response_file_name), 'w') as fp:
                    json.dump(r_history.json(), fp)
                

            else:
                logger_users.info(f"--- Unable to get Visual Crossing date. VC respose: {r_history.content} ---")
                save_vc_response_file_name = r_history.content.decode("utf-8") 
                
            call_list.append(weather_call_url)
            call_response.append(r_history.status_code)
            call_file.append(save_vc_response_file_name)
        

        #This just to record my calls
        df=pd.DataFrame(zip(call_list,call_response,call_file),columns=(["weather_call_url", "response","file_name / content"]))
        df.to_csv(os.path.join(logs_dir,'add_weather_VC_api_call_tracker.csv'))


        if len(search_weather_dates_dict_list)>0:
            flash(f"Successfully added more historical weather", 'info')
            ###########################################################
            # IF any change to WEATHER data: Make DF for user weather #
            ###########################################################
            create_df_files(current_user.id, ['temp', 'cloudcover'])
        else:
            flash(f"No additional weather needed to complement the data you have already submitted", "info")
        return redirect(url_for('users.add_more_weather'))
    oldest_date = datetime.strptime(oldest_date_str,"%Y-%m-%d").strftime("%b %d, %Y")
    oldest_date_str = datetime.strptime(oldest_date_str,"%Y-%m-%d").strftime("%m/%d/%Y")

    # one_month_ago = datetime.now()-timedelta(days=30)
    # one_month_ago_str = one_month_ago.strftime("%Y-%m-%d")


    return render_template('add_more_weather.html', oldest_date = oldest_date, oldest_date_str=oldest_date_str,
        hist_limit_date=hist_limit_date)



@users.route('/admin', methods=["GET", "POST"])
@login_required
def admin():
    if current_user.id != 1:
        return redirect(url_for('users.login'))
    list_of_users = sess.query(Users).all()
    list_of_notes = [user.notes for user in list_of_users]
    list_of_forms = ['form_'+str(i) for i in range(1,len(list_of_users)+1)]
    #Add form for delete modal
    list_of_forms = list_of_forms +[f'form_{len(list_of_forms)+1}']
    list_of_apple_count = [get_apple_health_count(u.id) for u in list_of_users]
    list_of_oura_sleep = [get_user_df_count(u.id, 'sleep') for u in list_of_users]

    # For User notes
    oura_bad_token_list = make_user_item_list('oura_token:', list_of_notes)
    weather_hist_status_list = make_user_item_list('weather_hist_status:', list_of_notes)
    weather_hist_dates_list = make_user_item_list('weather_hist_date:', list_of_notes)

    users_list = zip(list_of_users, list_of_forms, oura_bad_token_list,weather_hist_status_list,
        weather_hist_dates_list, list_of_apple_count,list_of_oura_sleep)

    if request.method == 'POST':
        formDict = request.form.to_dict()
        print('formDict: ', formDict)

        if formDict.get('user_id'):
            edit_user_id = formDict.get('user_id')
            edit_user = sess.query(Users).get(int(edit_user_id))
            print(edit_user)

            del formDict['user_id']

            # update all user notes with what is found in formDict
            notes_string = ''
            for data_item_name, data_item_value in formDict.items():
                notes_string = notes_string +  data_item_name + ":" + data_item_value + ";"

            # update notes in db
            edit_user.notes = notes_string
            sess.commit()

        elif formDict.get('delete_user_id'):
            delete_user_id = int(formDict.get('delete_user_id'))
            if delete_user_id in [1, 2]:
                flash('Not deleteing users 1 or 2. Must go into /admin route.', 'warning')
                print(f'-- not delting user {delete_user_id}')
                return redirect(url_for('users.admin'))
            logger_users.info(f"--- Deleteing user {delete_user_id}---")
            
            # Delete User_location_day
            sess.query(User_location_day).filter_by(user_id = delete_user_id).delete()
            sess.query(Apple_health_export).filter_by(user_id = delete_user_id).delete()
            sess.query(Oura_sleep_descriptions).filter_by(user_id = delete_user_id).delete()
            sess.query(Oura_token).filter_by(user_id = delete_user_id).delete()
            sess.query(User_notes).filter_by(user_id = delete_user_id).delete()
            sess.query(Users).filter_by(id = delete_user_id).delete()
            sess.commit()
            logger_users.info('-- removed user from db tables --')

            # Delete user df_files
            pickle_files_list = os.listdir(config.DF_FILES_DIR)
            for pickle_file in pickle_files_list:
                if pickle_file.find(f'user{delete_user_id}_df_') > -1:
                    os.remove(os.path.join(config.DF_FILES_DIR, pickle_file))
            logger_users.info('-- removed user df_files --')


            logger_users.info(f'- {delete_user_id} User deleted successfully -')
            flash(f'Successfully removed user {delete_user_id} from What Sticks', 'info')
        
        return redirect(url_for('users.admin'))

    return render_template('admin.html', users_list = users_list, list_of_forms=list_of_forms)


@users.route('/admin_db', methods=["GET", "POST"])
@login_required
def admin_db():

    list_of_tables = list(Base.metadata.tables.keys())
    make_dir_util(config.DB_DOWNLOADS)

    if request.method == 'POST':
        formDict = request.form.to_dict()
        print(formDict)
        if formDict.get('download_table'):
            print('--- accessed download table --- ')

            table_name_str = formDict.get('download_table')
            print('')

            sql_table = Base.metadata.tables[table_name_str]
            # base_query = sess.query(table).filter_by(user_id = 1)
            # df_oura = pd.read_sql(str(base_query)[:-1] + str(USER_ID), sess.bind)
            base_query = sess.query(sql_table)
            df = pd.read_sql(str(base_query), sess.bind)
            file_name = f"db_{table_name_str}.csv"
            df.to_csv(os.path.join(config.DB_DOWNLOADS, file_name))
            return send_from_directory(os.path.abspath(config.DB_DOWNLOADS), file_name, as_attachment=True)
            # return redirect(url_for('users.download_db_workbook', file_name=file_name))
        elif formDict.get('csv_table_upload'):
            print('-- receiving csv file --')


    return render_template('admin_db.html', list_of_tables=list_of_tables)


# @users.route("/download_db_workbook", methods=["GET","POST"])
# @login_required
# def download_db_workbook():
#     print('--- In download_db_workbook ---')
#     file_name = request.args.get('file_name')
#     print(file_name)
#     # workbook_name=request.args.get('workbook_name')
#     # workbook_name = os.listdir(current_app.config['FILES_DATABASE'])[0]
#     # print('file:::', os.path.join(current_app.root_path, 'static','files_database'),workbook_name)
#     # file_path = r'D:\OneDrive\Documents\professional\20210610kmDashboard2.0\fileShareApp\static\files_database\\'
#     print(config.DB_DOWNLOADS)
#     print(os.path.abspath(config.DB_DOWNLOADS))
#     path = r"/Users/nick/Documents/_databases/ws08/db_downloads"
#     return send_from_directory(path, file_name, as_attachment=True)


@users.route('/reset_password', methods = ["GET", "POST"])
def reset_password():
    page_name = 'Request Password Change'
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
    # form = RequestResetForm()
    # if form.validate_on_submit():
    if request.method == 'POST':
        formDict = request.form.to_dict()
        email = formDict.get('email')
        user = sess.query(Users).filter_by(email=email).first()
        if user:
        # send_reset_email(user)
            logger_users.info('Email reaquested to reset: ', email)
            send_reset_email(user)
            flash('Email has been sent with instructions to reset your password','info')
            # return redirect(url_for('users.login'))
        else:
            flash('Email has not been registered with What Sticks','warning')

        return redirect(url_for('users.reset_password'))
    return render_template('reset_request.html', page_name = page_name)


@users.route('/reset_password/<token>', methods = ["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('dash.dashboard', dash_dependent_var='steps'))
    user = Users.verify_reset_token(token)
    logger_users.info('user::', user)
    if user is None:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('users.reset_password'))
    if request.method == 'POST':

        formDict = request.form.to_dict()
        if formDict.get('password_text') != '':
            hash_pw = bcrypt.hashpw(formDict.get('password_text').encode(), salt)
            user.password = hash_pw
            sess.commit()
            flash('Password successfully updated', 'info')
            return redirect(url_for('users.login'))
        else:
            flash('Must enter non-empty password', 'warning')
            return redirect(url_for('users.reset_token', token=token))

    return render_template('reset_request.html', page_name='Reset Password')


@users.route('/about_us')
def about_us():
    page_name = 'About us'
    return render_template('about_us.html', page_name = page_name)

@users.route('/privacy')
def privacy():
    page_name = 'Privacy'
    return render_template('privacy.html', page_name = page_name)

@users.route('/YouTube_OAuth_Cred_Request')
def youtube_request():
    page_name = 'YouTub OAuth 2.0 Credentials Request'
    return render_template('youtube.html', page_name = page_name)
