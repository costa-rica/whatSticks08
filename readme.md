
<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/wshLogo_300px_doodle02.png?raw=true" alt="what sticks logo" width="200"/>

Visit current working web at:
https://what-sticks.com
#
What Sticks (WS) is an application that helps navigate your wellness with data already being collected by your other applications and devices.

Availible now to analyze your:
- Apple Health step count
- Oura Ring sleep quality
- Local weather

### Main Part of User Experience
There is a user dashboard that displays a table of correlations from your linked data. Here is an image of the steps dashboard

<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/readme/stepsDashScreenShot.png?raw=true" alt="ws dash screenshot" width="300"/>

#
## Project/repo flow chart
<img src="https://github.com/costa-rica/whatSticks08/blob/github-main/web/app_package/static/images/readme/projectFlowChart.png?raw=true" alt="ws project flowchart" width="300"/>



#
## Installation
This requires 2 main things:
1. download/install ws_module (config and models) into your env
2. download this repo
3. python run from inside web

## Step 1
Download config and models packages from [whatSticks08modules](https://github.com/costa-rica/whatSticks08modules) repo.

```bash
git clone https://github.com/costa-rica/whatSticks08modules
```
from inside your environment navigate to the downloaded whatSticks08modules/ws_modules01:
```bash
pip install -e .
```
## Step 2
Just download from terminal
```bash
git clone https://github.com/costa-rica/whatSticks08
```

## Step 3
from inside whatSticks08/web
```bash
python run.py
```

