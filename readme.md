
<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/wshLogo_300px_doodle02.png?raw=true" alt="what sticks logo" width="200"/>

Visit current working web at:
https://what-sticks.com
#
## Description
What Sticks (WS) is an application that helps navigate your wellness with data already being collected by your other applications and devices.

Availible now to analyze your:
- Apple Health step count
- Oura Ring sleep quality
- Local weather

### Main Part of User Experience
There is a user dashboard that displays a table of correlations from your linked data. Here is an image of the steps dashboard

<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/readme/stepsDashScreenShot.png?raw=true" alt="ws dash screenshot" width="500"/>

#
## Project/repo flow chart
<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/readme/projectFlowChart.png?raw=true" alt="ws project flowchart" width="500"/>




## Installation
This requires:
1. download/install ws_module (config and models) into your venv
2. config json file with api keys (I can provide if you contact me)
3. download this repo
4. python run from inside web/

### Step 1
Download config and models packages from [whatSticks08modules](https://github.com/costa-rica/whatSticks08modules) repo.

```bash
git clone https://github.com/costa-rica/whatSticks08modules
```

### Step 2
**Some hardcoding here see note*

Map config_ws08.json file to the config file in whatSticks08modules. Go to .env file inside whatSticks08modules/ws_modules01/ws_config01/ directory. Here you will edit:

```
CONFIG_PATH="/Users/nick/Documents/_config_files"
CONFIG_FILE_NAME="config_ws08_20221222.json"
CONFIG_TYPE='local'
```

I will send you config_ws08.

<br>
<br>

### NOTE 2022-12-23: 
I am in process of making this easier to update.
I am in process of minimizing the hardcoding steps for anyone to run. This is where some hardcoding takes place in the .env and config_ws08.json files.

As of this note I am building this in a new development from scratch once this note is deleted. I hope to delete this note soon and have a smooth build process.

<br>
<br>

### Step 3
from inside your environment navigate to the downloaded whatSticks08modules/ws_modules01:
```bash
pip install -e .
```

### Step 4
Just download from terminal
```bash
git clone https://github.com/costa-rica/whatSticks08
```

### Step 5
from inside whatSticks08/web
```bash
python run.py
```
#
## Once app is running

- First user to sign up is admin. There is an admin dashboard of all registered users so the admin can delete a user. No other users can see this dashboard. Admin can also write to blog.

- Second user use "Guest" with password "test"

- Login as Guest will then work showing the admin's dashboards but guest users won't be able to make any changes - only view.

- All other sign ups will have normal accounts that can add/remove their own data.
#
## Contributing
DM or email at whatsticks.com@gmail.com. 
I will send latest config.json file with api keys.

Very much welcome help but I would like to get to know you a little before I send keys. 

I am looking for help in these areas:
1. develop iOS application
2. frontend: make web app look pretty
3. backend help connecting to the different api's with OAuth 2.0
4. database
5. data science to improve metrics, data visulalizations, write articles on findings


## Thanks for reading!
:blush:
