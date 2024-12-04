from OS import OS
import requests
import re
import json
import os
import hashlib
import requests

REPO_OWNER = os.getenv('REPO_OWNER')
REPO_NAME = os.getenv('REPO_NAME')
TAG = os.getenv('TAG')
GITHUB_TOKEN = os.getenv('GIT_TKN')

headers = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

url = f'https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases'

response = requests.get(url, headers=headers)
response.raise_for_status()

releases = response.json()
# Handle multiple releases, assuming the assets are spread across them
assets = []
for release in releases:
    if release['tag_name'] == TAG:
        assets.extend(release['assets'])

id_patterns = [
    'bionic*64', 'rocky8', 'Windows*x86_64', 'xenial', 'el7', 'plugins*rocky8', 'disco', 'jammy*64',
    'el6', 'plugins*el7', 'Windows*i386', 'Windows*x86', 'el8', 'Darwin', 'squeeze_amd64',
    'plugins*el6', 'focal*64', 'suse11.4', 'DOCS', 'kinetic', 'VM',
    'Windows', 'plugins*el8'
]

id_regexes = [(id_pattern, re.compile(id_pattern.replace('*', '.*'))) for id_pattern in id_patterns]

version_pattern = re.compile(
    r'(?P<Version>(?:(\d{1,2})\.)(?:(\d{1,2})\.)(\d{1,})(\-|\.|\~)(\d{1,2}|rc|closedown|beta|alpha|trunk)(\d{1,2})?)'
)

def extract_info(file_name):
    version_match = re.search(version_pattern, file_name)
    if version_match:
        version = version_match.group('Version')
        pre_version_text = file_name.split(version)[0]
        install_info = pre_version_text.replace("hpccsystems-", "").replace("community-", "").replace("-community", "").rstrip("_-")
        for id_pattern, id_regex in id_regexes:
            id_match = re.search(id_regex, file_name)
            if id_match:
                return {
                    'Install': install_info,
                    'Version': version.split('-', 1)[0],
                    'ID': id_pattern
                }
    return None

def map_to_os_dict(extracted_info):
    unknown_ids = set()
    
    for info in extracted_info:
        found = False
        for os_family in OS.values():
            for entry in os_family:
                if info['ID'] == "Windows":
                    print(f"id is: %s", info['ID'], "install is: %s", info['Install'])
                if info['ID'] == entry['id'] and info['Install'] == entry['install']:
                    info['OS'] = entry['name']
                    info['Essential'] = entry['essential']
                    info['Link_Path'] = entry['link']
                    info['Link_Text'] = entry['text']
                    info['Display_Name'] = entry['title']
                    found = True
                    break
            if found:
                break
        if not found:
            info['OS'] = 'Unknown'
            unknown_ids.add(info['ID'])
    return extracted_info, unknown_ids


def filter_md5_assets(assets):
    md5_dict = {}
    for asset in assets:
        if asset['name'].endswith('.md5sum'):
            base_name = asset['name'].rsplit('.md5sum', 1)[0]
            response = requests.get(asset['browser_download_url'], headers=headers)
            response.raise_for_status()
            md5_content = response.text.strip().split()[0]
            md5_dict[base_name] = md5_content
    return md5_dict

def bytes_to_mb(bytes_size):
    return round(bytes_size / (1024 * 1024), 3)

def parse_version_string(version_string):
    # Remove everything before the "_"
    _, version_info = version_string.split('_', 1)
    
    # Split the version info using "." and "-" as separators
    parts = version_info.replace('-', '.').split('.')
    
    # Assign the parts to variables
    major_version = parts[0]
    minor_version = parts[1]
    patch_version = parts[2]
    build_number = parts[3]
    
    return major_version, minor_version, patch_version, build_number

def calculate_md5sum(url):
    response = requests.get(url)
    response.raise_for_status()
    file_content = response.content
    md5_hash = hashlib.md5(file_content).hexdigest()
    return md5_hash

extracted_info = []

# Get the md5 dictionary
md5_dict = filter_md5_assets(assets)

# Extracting information from assets
for asset in assets:
    file_name = asset['name']
    info = extract_info(file_name)
    if file_name.endswith('.md5sum'):
        continue
    if info:
        info["File_Name"] = file_name
        info["File_Size"] = f"{bytes_to_mb(asset['size'])} MB"
        info["MD5"] = md5_dict.get(file_name)
        if 'docs' in file_name.lower():
            docs_type = 'UNKNOWN'
            if 'en_us' in info['Install'].lower():
                docs_type = 'EN_US'
            elif 'pt_br' in info['Install'].lower():
                docs_type = 'PT_BR'
            info['Edge_Cast_Path'] = f"releases/CE-Candidate-{info['Version']}/docs/{docs_type}/{file_name}"
        else:
            info['Edge_Cast_Path'] = f"releases/CE-Candidate-{info['Version']}/bin/{info['Install'].split('-', 1)[0]}/{file_name}"

        extracted_info.append(info)

mapped_info, unknown_ids = map_to_os_dict(extracted_info)

found_count = sum(1 for info in mapped_info if info['OS'] != 'Unknown')
unknown_count = sum(1 for info in mapped_info if info['OS'] == 'Unknown')

json_obj = []

major, minor, point, sequence = parse_version_string(TAG)

# Printing and collecting JSON objects
for info in mapped_info:
    print(f"OS: {info['OS']}")
    print(f"File Size: {info['File_Size']}")
    print(f"Version: {info['Version']}")
    print(f"Link_Path: {info['Link_Path']}")
    print(f"Display_Name: {info['Display_Name']}")
    print(f"File Name: {info['File_Name']}")
    print(f"Link_Text: {info['Link_Text']}")
    print(f"Edge_Cast_Path: {info['Edge_Cast_Path']}")
    print(f"Type: {info['Install']}")
    print(f"Essential: {info['Essential']}")
    print(f"MD5: {info['MD5']}")
    json_obj.append(info)
    print("\n")

# Saving to JSON file
outfile = TAG + ".json"
try:
    with open(outfile, 'w') as file:
        file.write("{ \n")
        file.write("\"files\": ")
    with open(outfile, 'a') as json_file:
        json.dump(json_obj, json_file, indent=4)
    
    with open(outfile, 'a') as file:
        file.write(", \n")
        file.write("\"Major\": \"" + major + "\", \n")
        file.write("\"Minor\": \"" + minor + "\", \n")
        file.write("\"Point\": \"" + point + "\", \n")
        file.write("\"Sequence\": \"" + sequence + "\", \n")
        file.write("\"Version\": \"" + TAG.split('_')[1] + "\", \n")       
        file.write("\"type\": \"release\"\n")
        file.write("}")
except Exception as e:
    print(f"An error occurred: {e}")