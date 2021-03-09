import os
import logging

# import asyncio
# import time
import base64
from cryptography import fernet
# from aiohttp import web
from aiohttp_session import setup  # , get_session, session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage

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

# async def handler(request):
#     session = await get_session(request)
#     last_visit = session['last_visit'] if 'last_visit' in session else None
#     text = 'Last visited: {}'.format(last_visit)
#     return web.Response(text=text)


async def make_app():

    app = web.Application()

    # secret_key must be 32 url-safe base64-encoded bytes
    fernet_key = fernet.Fernet.generate_key()
    secret_key = base64.urlsafe_b64decode(fernet_key)
    setup(app, EncryptedCookieStorage(secret_key))

    # Configure Jinja2 template map
    templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
    aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader(templates_dir))

    app.router.add_get('/', kge_landing_page)
    app.router.add_get('/login', kge_login)
    app.router.add_get('/oauth2callback', kge_client_authentication)
    app.router.add_get('/home', get_kge_home)
    app.router.add_get('/logout', kge_logout)

    return app


def main():
    logging.basicConfig(level=logging.DEBUG)
    web.run_app(make_app())
