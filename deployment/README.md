# Production site configuration

This document is adapted from AIOHTTP application deployment details [here](https://docs.aiohttp.org/en/stable/deployment.html).

## NGINX

We provide a [sample template for NGINX configuration](./kge_nginx.conf-template). Refer also to general NGINX documentation for further guidance.

## Supervisord

ROUGHED IN ONLY, BUT AS YET UNTESTED!

NOTE: SUPERVISORD AND DOCKER MAY NOT PLAY WELL TOGETHER... SEE:
- https://stackoverflow.com/questions/30034813/best-way-to-manage-docker-containers-with-supervisord

See [AIOHTTP notes on supervisor use](https://docs.aiohttp.org/en/stable/deployment.html#supervisord) plus [supervisor docs](http://supervisord.org/) for further details. Once again, we provide a template [supervisord-template](./supervisord-template) which may (eventually) be useful.

## KGE Archive Server Applications

STUB DOCUMENTATION - SAMPLE CODE CUT AND PASTED FROM
https://docs.aiohttp.org/en/stable/deployment.html#aiohttp-server
THIS NEEDS CUSTOMIZATION AND ELABORATION RELATING TO THE REAL CODE!

We have distinct KGE UI and web services applications to be run.  Assuming we have properly configured aiohttp.web.Application and THE port is specified by command line, the task is trivial:

```python
# aiohttp_example.py
import argparse
from aiohttp import web

parser = argparse.ArgumentParser(description="aiohttp server example")
parser.add_argument('--path')
parser.add_argument('--port')


if __name__ == '__main__':
    app = web.Application()
    # configure app

    args = parser.parse_args()
    web.run_app(app, path=args.path, port=args.port)
```

## Docker Compose Running of the System

WORK-IN-PROGRESS

Some possible information resources to consult:
- https://help.cmd.com/en/articles/3616684-supervisord-deployment-guide
- https://www.cilans.net/skill-development/running-multiple-services-in-a-docker-container-via-supervisord-at-runtime/
