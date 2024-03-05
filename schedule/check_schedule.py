import os
import re
import requests
import redis
import yaml
from github import Github
from datetime import datetime
from slack_sdk.web.async_client import AsyncWebClient

slack_token = os.environ.get('SLACK_TOKEN', None)
redis_host = os.environ.get('REDIS_HOST', 'localhost')
redis_password = os.environ.get('REDIS_PASSWORD', None)
github_token = os.environ.get('GITHUB_TOKEN', None)


advisory_cluster_api = "https://art-dash-server-art-dashboard-server.apps.artc2023.pc3z.p1.openshiftapps.com/api/v1/errata/advisory/?type=advisory&id="
#redis_client = redis.Redis(host="localhost", port=6379, password=redis_password, ssl=True, decode_responses=True)

github_client = Github(github_token)
cincinnati_repo = github_client.get_repo("openshift/cincinnati-graph-data")
channels = [ i.path for i in cincinnati_repo.get_contents("channels") ]
stable_files = [file for file in channels if file.startswith('channels/stable')]
pattern = re.compile(r'channels/stable-(\d+)\.(\d+)\.yaml') 
major, minor = max(pattern.findall(str(stable_files)), key=lambda x: int(x[1]))
minor = int(minor)
status = []
ocp_build_data = github_client.get_repo("openshift/ocp-build-data")
while minor > 0:
    if yaml.load(ocp_build_data.get_contents("group.yml", ref=f"openshift-{major}.{minor}").decoded_content,Loader=yaml.FullLoader)['software_lifecycle']['phase'] != "eol":
        res = requests.get(f"https://pp.engineering.redhat.com/api/v7/releases/openshift-{major}.{minor}.z/?fields=all_ga_tasks",headers={'Accept': 'application/json'})
        for release in res.json()['all_ga_tasks']:
            if datetime.strptime(release['date_finish'],"%Y-%m-%d") < datetime.now():
                release_date, release_name = release['date_finish'], release['name']
            else:
                break
        if "GA" in release_name:
            assembly = re.search(r'\d+\.\d+', release_name).group()+".0"
        else:
            assembly = re.search(r'\d+\.\d+.\d+', release_name).group()
        print(f"latest {major}.{minor} is {assembly}")
        print(f"next {major}.{minor} is {release['name']} release date is {release['date_finish']} ")
        release_config = yaml.load(ocp_build_data.get_contents("releases.yml", ref=f"openshift-{major}.{minor}").decoded_content,Loader=yaml.FullLoader)
        advisories = release_config['releases'][assembly]['assembly']['group']['advisories']
        for ad in advisories:
            #status_in_redis = redis_client.get(advisories[ad])
            if status_in_redis == "SHIPPED_LIVE" or status_in_redis == "DROPPED_NO_SHIP":
                continue
            else:
                res = requests.get(f"{advisory_cluster_api}{advisories[ad]}")
                errata_state = res.json()['data']['advisory_details'][0]['status']
                if errata_state != status_in_redis:
                    #redis_client.delete(advisories[ad])
                    #redis_client.setex(advisories[ad], 60*60*24*7, errata_state)
                    status.append(f"{assembly} {ad} advisory {advisories[ad]} changed to {errata_state} and release date is {release_date}\n")
        minor = minor - 1
    else:
        break


if status:
    for state in status:
        print(state)
    if slack_token:
        response = await AsyncWebClient(token=slack_token).chat_postMessage(
            channel="#art-dev", text=''.join(status), thread_ts=None, username="art-release-bot", link_names=True, attachments=[], icon_emoji=":robot_face:", reply_broadcast=False)
