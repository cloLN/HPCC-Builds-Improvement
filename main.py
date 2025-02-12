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

Version_Number_pattern = re.compile(
    r'(?P<Version_Number>(?:(\d{1,2})\.)(?:(\d{1,2})\.)(\d{1,})(\-|\.|\~)(\d{1,2}|rc|closedown|beta|alpha|trunk)(\d{1,2})?)'
)

def extract_info(file_name):
    Version_Number_match = re.search(Version_Number_pattern, file_name)
    if Version_Number_match and not contains_k8s(file_name):
        Version_Number = Version_Number_match.group('Version_Number')
        pre_Version_Number_text = file_name.split(Version_Number)[0]
        install_info = pre_Version_Number_text.replace("hpccsystems-", "").replace("community-", "").replace("-community", "").rstrip("_-")
        for id_pattern, id_regex in id_regexes:
            id_match = re.search(id_regex, file_name)
            if id_match:
                return {
                    'Type': install_info,
                    'Version_Number': Version_Number.split('-', 1)[0],
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

                    print(f"id is: %s", info['ID'], "install is: %s", info['Type'])
                if info['ID'] == entry['id'] and info['Type'] == entry['type']:
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

def parse_Version_Number_string(Version_Number_string):
    # Remove everything before the "_"
    _, Version_Number_info = Version_Number_string.split('_', 1)
    
    # Split the Version_Number info using "." and "-" as separators
    parts = Version_Number_info.replace('-', '.').split('.')
    
    # Assign the parts to variables
    major_Version_Number = parts[0]
    minor_Version_Number = parts[1]
    patch_Version_Number = parts[2]
    build_number = parts[3]
    
    return major_Version_Number, minor_Version_Number, patch_Version_Number, build_number

def calculate_md5sum(url):
    response = requests.get(url)
    response.raise_for_status()
    file_content = response.content
    md5_hash = hashlib.md5(file_content).hexdigest()
    return md5_hash

def contains_k8s(input_string):
    return 'k8s' in input_string

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
        info["Download_Size"] = f"{bytes_to_mb(asset['size'])} MB"
        info["MD5"] = md5_dict.get(file_name)
        if contains_k8s(file_name):
            info["MD5"] = calculate_md5sum(asset['browser_download_url'])

        if 'docs' in file_name.lower():
            info["MD5"] = calculate_md5sum(asset['browser_download_url'])
            docs_type = 'UNKNOWN'
            if 'en_us' in info['Type'].lower():
                docs_type = 'EN_US'
            elif 'pt_br' in info['Type'].lower():
                docs_type = 'PT_BR'
            info['Edge_Cast_Path'] = f"releases/CE-Candidate-{info['Version_Number']}/docs/{docs_type}/{file_name}"
        else:
            info['Edge_Cast_Path'] = f"releases/CE-Candidate-{info['Version_Number']}/bin/{info['Type'].split('-', 1)[0]}/{file_name}"

        extracted_info.append(info)

mapped_info, unknown_ids = map_to_os_dict(extracted_info)

found_count = sum(1 for info in mapped_info if info['OS'] != 'Unknown')
unknown_count = sum(1 for info in mapped_info if info['OS'] == 'Unknown')

json_obj = []

major, minor, point, sequence = parse_Version_Number_string(TAG)

# Printing and collecting JSON objects
for info in mapped_info:
    print(f"OS: {info['OS']}")
    print(f"Download_Size: {info['Download_Size']}")
    print(f"Version_Number: {info['Version_Number']}")
    print(f"Link_Path: {info['Link_Path']}")
    print(f"Display_Name: {info['Display_Name']}")
    print(f"File Name: {info['File_Name']}")
    print(f"Link_Text: {info['Link_Text']}")
    print(f"Edge_Cast_Path: {info['Edge_Cast_Path']}")
    print(f"Type: {info['Type']}")
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
        file.write("\"Version_Number\": \"" + TAG.split('_')[1] + "\", \n")       
        file.write("\"type\": \"release\"\n")
        file.write("}")
except Exception as e:
    print(f"An error occurred: {e}")