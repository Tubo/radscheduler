# Radscheduler

A rostering program for Radiology Registrars.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

License: MIT

## Back up and restore a database from fly.io

Start a proxy to fly postgres:
`flyctl proxy 54321:5432 --app radscheduler-db`

Find the password to of DATABASE_URL via:
`flyctl ssh console -C 'env'`

Download a dump:
`pg_dump -d postgres://radscheduler@localhost:54321 | gzip > backups/db.sql.gz`

Restore using
`docker-compose -f local.yml run --rm postgres restore db.sql.gz`

or

`docker exec radscheduler_local_postgres restore db.sql.gz`
