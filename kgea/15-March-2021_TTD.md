# 15 March 2021 - KGE Archive Things to Do

- Stress test large local file upload (multipart?)
- Fix URL file transfer:
    - ~~Perhaps need to manage the aiohttp sessions used in stream_from_url() globally in the application? See https://docs.aiohttp.org/en/stable/client_quickstart.html#make-a-request~~
    - Stress test URL file transfer
- Fix AIOHTTP session management (esp. with respect to AWS Cognito)
    - Enhance URL handling of websites requiring authorization (e.g. perhaps with OAuth2?)
- Input file format validation: KGX files, metadata file
- Data Access
  - Metadata file download
  - Data file download
  - SmartAPI entry registration
  -  Web file catalog query (tied with metadata and data file indexing)
- User interface clean-up and simplification
  - Derive 'Submitter' from user login identity
  - Review sanitization of UI inputs: content_name, kg_name
- KGX metadata generation (maybe give radio button selection on web form: 1) provided 2) autogenerate!)