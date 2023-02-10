redoc_template = r"""<!DOCTYPE html>
<html>
  <head>
    <title>ReDoc</title>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" rel="stylesheet">
    <style>
      body {
        margin: 0;
        padding: 0;
      }
    </style>
  </head>
  <body>
    <redoc spec-url='/openapi.json'></redoc>
    <script src="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js"> </script>
  </body>
</html>
"""

rapidoc_template = r"""<!doctype html> <!-- Important: must specify -->
  <html>
  <head>
    <meta charset="utf-8"> <!-- Important: rapi-doc uses utf8 charecters -->
    <script src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
  </head>
  <body>
    <rapi-doc
      spec-url="/openapi.json"
    > </rapi-doc>
  </body>
  </html>
"""
