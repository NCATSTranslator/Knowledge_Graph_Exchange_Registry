import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from os.path import abspath


resources = None
try:
    # the following config file should be visible in the root 'web_ui' subdirectory, as copied
    # from the available template and populated with site-specific configuration values
    with open(abspath('server/kgea_ui_config.yaml'), 'r') as resource_config_file:
        
        resource_config = yaml.load(resource_config_file, Loader=Loader)
        resources = dict(resource_config)

except Exception as e:
    print('ERROR: KGE Archive User Interface resource configuration file failed to load')
    print(e)
