"""DPMES (performance of public bodies and policy areas), https://dpmes.mopd.gov.et/api/docs/.

- `client`: the DPMES API calls (with the Digital Hub's API key, cached).
- `compat`: maps DPMES responses to the shapes the website and app expect.
- `views`, `urls`: the /api/mobile/... endpoints the website's scorecard pages
  call. The browser cannot call DPMES itself: every data endpoint needs the
  key, and DPMES sends no CORS headers.
"""
