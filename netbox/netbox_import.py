#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: noai:et:tw=80:ts=4:ss=4:sts=4:sw=4:ft=python

'''
Title:            netbox_import.py
Description:      Insert records from devicetype-library into NetBox
Author:           Ricky Laney
Version:          0.1.5
==============================================================================
'''

import csv
import re
import os
from pathlib import Path
import shutil
from subprocess import run
import pynetbox
from pynetbox.core.query import RequestError
from ruamel.yaml import YAML


_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Adjust this!
_PRIV_KEY_FILE = os.path.join(_ROOT_DIR, 'path/to/your/private-key.pem') # Adjust this!
_TOKEN = 'fa8bcce25cdbe307221458c7dbb2cb5227459484' # Adjust this!# ADJUSTED this!
_HOST = '10.0.0.231' # Adjust this!# ADJUSTED this!
_PORT = '8000' # Adjust this?# ADJUSTED this!
_PROTOCOL = 'http'
_ENDPOINT = f"{_PROTOCOL}://{_HOST}:{_PORT}"
_HEADERS = {"Authorization": f"Bearer {_TOKEN}"}
_THREADING = False
_SSL_VERIFY = False
_PATTERN = '*.yaml'
_REPOS = [
    ('devicetype-library', 'https://github.com/netbox-community/devicetype-library'),
    ('reports', 'https://github.com/netbox-community/reports'),
]
_NOTHING = ['', None, ' ']
TEMPLATE_LIST = [
    'console-ports',
    'console-server-ports',
    'power-ports',
    'power-outlets',
    'interfaces',
    'front-ports',
    'rear-ports',
    'device-bays',
]

nb = pynetbox.api(
    _ENDPOINT,
    private_key_file=_PRIV_KEY_FILE,
    token=_TOKEN,
    ssl_verify=_SSL_VERIFY,
    threading=_THREADING,
)


class ManufacturerLookupError(BaseException):
    """
    Custom exception class
    """


class ManufacturerCreateError(BaseException):
    """
    Custom exception class
    """


class DeviceTypeValidationError(BaseException):
    """
    Custom exception class
    """


class DeviceTypeLookupError(BaseException):
    """
    Custom exception class
    """


class DeviceTypeCreateError(BaseException):
    """
    Custom exception class
    """


class TemplateCreationError(BaseException):
    """
    Custom exception class
    """


class TemplateProcessError(BaseException):
    """
    Custom exception class
    """


def slugify(s):
    """
    Converts dirty strings into something URL-friendly.
    FYI - Ordering is important.
    """
    s = s.lower()
    # Replace these items with underscore first
    for c in [' ', '-', '.', '/']:
        s = s.replace(c, '_')
    # Remove non-word characters
    s = re.sub(r'\W', '', s)
    # Replace underscore with space to eliminate space seperated underscores
    s = s.replace('_', ' ')
    # Replace 2 or more spaces with single space
    s = re.sub(r'\s+', ' ', s)
    # Remove any leading or trailing spaces
    s = s.strip()
    # Finally replace spaces with a dash
    s = s.replace(' ', '-')
    return s


def refresh_repo_dir(repo_dir):
    """
    Runs the "git pull" command if the directory is git repo.
    """
    if os.path.isdir(repo_dir) and '.git' in os.listdir(repo_dir):
        print(f"Running git pull in {repo_dir}")
        run(['git', 'pull'], cwd=repo_dir, check=True)
    else:
        print(f"Not a repo dir: {repo_dir}")


def repo_update(repos=None, repo_dir=None, use_temp_dir=False):
    """
    Does "git pull" on all repos found in directory or "git clone" if not found.
    """
    if not repos or not repo_dir:
        raise Exception("Must provide repos and repo_dir location")
    if use_temp_dir is True and os.path.exists(repo_dir):
        print(f"Deleting temp dir: {repo_dir}")
        shutil.rmtree(repo_dir, ignore_errors=True)
    if not os.path.exists(repo_dir):
        print(f"Creating dir: {repo_dir}")
        os.mkdir(repo_dir)
    for name, url in repos:
        if name in os.listdir(repo_dir):
            print(f"Refreshing {name} in {repo_dir}")
            refresh_repo_dir(os.path.join(repo_dir, name))
        else:
            print(f"Cloning {name} in {repo_dir}")
            run(['git', 'clone', url], cwd=repo_dir, check=True)


def get_yamls(yaml_file_path):
    """
    Finds all yaml files from the given path.
    """
    yamls = []
    yp = Path(yaml_file_path)
    for yf in yp.rglob('*.yaml'):
        yamls.append(yf)
    return yamls


def load_yaml(yaml_file: str):
    """
    Uses ruamel.yaml to load YAML files.
    Stolen from "https://github.com/netbox-community/netbox-docker"
    """
    yf = Path(yaml_file)
    if not yf.is_file():
        return None
    with yf.open("r") as stream:
        yaml = YAML(typ="safe")
        return yaml.load(stream)


def device_type_exists(device_type):
    """
    Runs multiple checks to see if the device type already exists in NetBox.
    """
    try:
        print(f"Checking if {device_type['model']} exists")
        _slug = slugify(device_type['model'])
        if nb.dcim.device_types.filter(model=device_type['model']):
            print(f"Found device_type dict {device_type['model']}")
            return True
        elif nb.dcim.device_types.get(model=device_type['model']):
            print(f"Found device_type name {device_type['model']}")
            return True
        elif nb.dcim.device_types.get(slug=device_type['slug']):
            print(f"Found device_type slug {device_type['slug']}")
            return True
        elif nb.dcim.device_types.get(slug=_slug):
            print(f"Found device_type _slug {_slug}")
            return True
        else:
            return False
    except Exception as e:
        raise DeviceTypeLookupError(f"Error for {device_type}: {e}")


def get_or_create_manufacturer(man):
    """
    Try and get the manufacturer create it if it does not exist.
    """
    print(f"Checking if {man} exists")
    if not nb.dcim.manufacturers.get(name=man):
        print(f"Manufacturer: {man} does not exist")
        new_man = {'name': man, 'slug': slugify(man)}
        print(f"Creating manufacturer with: {new_man}")
        nb.dcim.manufacturers.create(new_man)
    man_id = nb.dcim.manufacturers.get(name=man).id
    print(f"Found manufacturer {man} id: {str(man_id)}")
    return int(man_id)


def create_template(name, template):
    """
    Create a template.
    """
    try:
        if name == 'console-ports':
            results = nb.dcim.console_port_templates.create(template)
        elif name == 'console-server-ports':
            results = nb.dcim.console_server_port_templates.create(template)
        elif name == 'power-ports':
            results = nb.dcim.power_port_templates.create(template)
        elif name == 'power-outlets':
            results = nb.dcim.power_outlet_templates.create(template)
        elif name == 'interfaces':
            results = nb.dcim.interface_templates.create(template)
        elif name == 'front-ports':
            results = nb.dcim.front_port_templates.create(template)
        elif name == 'rear-ports':
            results = nb.dcim.rear_port_templates.create(template)
        elif name == 'device-bays':
            results = nb.dcim.device_bay_templates.create(template)
        print(f"Created new {name}: {results.name}")
        return results
    except RequestError:
        print(f"Already have {name}: {template}")
    except Exception as e:
        raise TemplateCreationError(
                f"Failed creating: {name}: {template}\nException: {e}")


def process_templates(device_type):
    """
    Process the templates.
    """
    try:
        device_type_id = nb.dcim.device_types.get(model=device_type['model']).id
    except:
        raise TemplateProcessError(
            f"Create device_type: {device_type['model']} before extracting \
            templates.")
    for name, data in device_type.items():
        if name in TEMPLATE_LIST:
            for item in data:
                item.update({'device_type': device_type_id})
                print(f"Creating template {name} with {item}")
                create_template(name, item)


def validate_device_data(device_type):
    """
    Validates and modifies data before inserting in NetBox.
    """
    if not isinstance(device_type, dict):
        raise DeviceTypeValidationError(f"Validation FAILED for {device_type}: \
                            {type(device_type)} is not a dict")
    man = device_type['manufacturer']
    man_id = get_or_create_manufacturer(man)
    device_type['manufacturer'] = man_id
    return device_type


def process_device_type(device_type):
    """
    Validates and verifies the device type before inserting in NetBox.
    """
    device_type = validate_device_data(device_type)
    does_exist = device_type_exists(device_type)
    if does_exist is False:
        print(f"Adding new device-type {device_type['model']}")
        nb.dcim.device_types.create(device_type)
    else:
        print(f"Already a device_type: {device_type['model']}")
    print(f"Checking for templates: {device_type['model']}")
    process_templates(device_type)


def process_csv(csv_file):
    """
    Process a CSV file for importing to NetBox.
    """
    with open(csv_file) as cf:
        for line in csv.DictReader(cf):
            if not line['u_height'] or \
                line['u_height'] in _NOTHING:
                line['u_height'] = 0
            if not line['is_full_depth'] or \
                line['is_full_depth'] in _NOTHING:
                line['is_full_depth'] = False
            process_device_type(line)


def process_yaml(yml_file):
    """
    Process a YAML file for importing to NetBox.
    """
    device_type = load_yaml(yml_file)
    process_device_type(device_type)


if __name__ == "__main__":
    TEMP_DIR = os.path.join(_ROOT_DIR, '__temp__')
    repo_update(_REPOS, TEMP_DIR, use_temp_dir=True)
    TEMP_DEV_TYPE_LIB = os.path.join(TEMP_DIR, 'devicetype-library/device-types')
    for yfile in get_yamls(TEMP_DEV_TYPE_LIB):
        process_yaml(yfile)
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    # process_csv('./old_device_types.csv')
