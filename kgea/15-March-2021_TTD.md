# 15 March 2021 - KGE Archive Things to Do

- Stress test large local file upload (multipart?)
- Fix URL file transfer:
    - ~~Perhaps need to manage the aiohttp sessions used in stream_from_url() globally in the application? See https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request~~
    - Stress test URL file transfer
- Fix AIOHTTP session management (esp. with respect to AWS Cognito)
    - Enhance URL handling of websites requiring authorization (e.g. perhaps with OAuth2?)
- Review sanitization of UI inputs: content_name, kg_name
- Derive 'Submitter' from user login identity
- Input file format validation: KGX files, metadata file
- SmartAPI entry registration
- Metadata file download
- Data file download
- KGX metadata generation (maybe give radio button selection on web form: 1) provided 2) autogenerate!)