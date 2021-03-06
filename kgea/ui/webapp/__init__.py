import os
import logging

import jinja2
import aiohttp_jinja2
from aiohttp import web

from .kgea_ui_handlers import (
    kge_landing_page,
    kge_login,
    kge_client_authentication,
    get_kge_home,
    kge_logout
)

# paths:
#   /:
#     get:
#       parameters:
#       - name: session
#         in: query
#         required: false
#         schema:
#           type: string
#       tags:
#       - site
#       summary: Display landing page.
#       operationId: landingPage
#       responses:
#         '200':
#           description: >-
#             Non-authenticated users see the login button.
#           content:
#             text/html:
#               schema:
#                 description: HTML landing page
#                 type: string
#         '302':
#           description: >-
#             Authenticated uses get redirected to /home.
#   /home:
#     get:
#       parameters:
#       - name: session
#         in: query
#         required: false
#         schema:
#           type: string
#       tags:
#       - site
#       summary: Display home landing page
#       operationId: getHome
#       responses:
#         '200':
#           description: >-
#             Authenticated users see the KGE dashboard;
#             Non-authenticated users see the login page.
#           content:
#             text/html:
#               schema:
#                 description: HTML home page
#                 type: string
#   /login:
#     get:
#       tags:
#       - site
#       summary: Process client user login
#       operationId: login
#       responses:
#         '302':
#           description: >-
#             Redirects to a hosted Oauth2 client
#             registration and login process
#   /oauth2callback:
#     get:
#       parameters:
#       - name: code
#         in: query
#         required: true
#         schema:
#           type: string
#       - name: state
#         in: query
#         required: true
#         schema:
#           type: string
#       tags:
#       - site
#       summary: Process client authentication
#       operationId: clientAuthentication
#       responses:
#         '200':
#           description: >-
#             Confirms login status (need to redirect?)
#           content:
#             text/html:
#               schema:
#                 description: >-
#                   If authenticated, redirects to
#                   home page, with a valid session
#                 type: string
#   /logout:
#     get:
#       parameters:
#       - name: session
#         in: query
#         required: false
#         schema:
#           type: string
#       tags:
#       - site
#       summary: Process client user logout
#       operationId: logout
#       responses:
#         '302':
#           description: >-
#             Returns redirect to hosted Oauth2 client logout process


def main():
    logging.basicConfig(level=logging.DEBUG)

    app = web.Application()

    # Configure Jinja2 template map
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(templates_dir))

    app.router.add_get('/', kge_landing_page)
    app.router.add_get('/login', kge_login)
    app.router.add_get('/oauth2callback', kge_client_authentication)
    app.router.add_get('/home', get_kge_home)
    app.router.add_get('/logout', kge_logout)

    web.run_app(app)
