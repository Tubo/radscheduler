# Radscheduler

A rostering program for Radiology Registrars.

[![Built with Cookiecutter Django](https://img.shields.io/badge/built%20with-Cookiecutter%20Django-ff69b4.svg?logo=cookiecutter)](https://github.com/cookiecutter/cookiecutter-django/)
[![Black code style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)

License: MIT

## Back up and restore a database from fly.io

Start a proxy to fly postgres:
`flyctl proxy 54321:5432 --app app-name`

Set env for FLY_DATABASE_URL with credentials.

Download a dump:
`pg_dump -d $FLY_DATABASE_URL | gzip > backups/first.sql.gz`

Restore using
`docker-compose -f local.yml run postgres restore first.sql.gz`
