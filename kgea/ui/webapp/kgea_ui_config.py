import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from os.path import expanduser, abspath


resources = None
try: 
    with open(abspath('kgea_ui_config.yaml'), 'r') as resource_config_file:
        
        resource_config = yaml.load(resource_config_file, Loader=Loader)
        resources = dict(resource_config)

except Exception as e:
    print('ERROR: resource configuration file failed to load')
    print(e)
