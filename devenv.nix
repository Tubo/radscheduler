{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:

{
  # https://devenv.sh/basics/
  env = {
    FLY_APP = "radscheduler";
    FLY_PG_APP = "radscheduler-db";

    PGDATABASE = config.env.POSTGRES_DB;
    DATABASE_URL = "postgres://${config.env.POSTGRES_USER}:${config.env.POSTGRES_PASSWORD}@${config.env.PGHOST}/${config.env.POSTGRES_DB}";

    EMAIL_HOST = "localhost"; # For Mailpit
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = 1;
    PLAYWRIGHT_BROWSERS_PATH = "${pkgs.playwright-driver.browsers}";
  };

  dotenv.enable = true;
  dotenv.filename = [
    ".envs/.local/.django"
    ".envs/.local/.postgres"
  ];

  # https://devenv.sh/packages/
  packages = with pkgs; [
    libpq.pg_config
    git
    flyctl
    gzip
    coreutils
    playwright-test
    playwright-driver
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    version = "3.11";
    venv.enable = true;
  };
  languages.javascript.enable = true;
  languages.javascript.pnpm = {
    enable = true;
    install.enable = true;
  };

  # https://devenv.sh/processes/
  # processes.dev.exec = "${lib.getExe pkgs.watchexec} -n -- ls -la";
  processes."dev:django".exec = ''
    python manage.py runserver_plus 0.0.0.0:8000
  '';
  processes."dev:webpack".exec = ''
    pnpm webpack --watch --config webpack/dev.config.js
  '';

  # https://devenv.sh/services/
  services.postgres = {
    enable = true;
    listen_addresses = "localhost";
    initialScript = ''
      ALTER USER "${config.env.POSTGRES_USER}" WITH SUPERUSER;
    '';
    initialDatabases = [
      {
        name = config.env.POSTGRES_DB;
        user = config.env.POSTGRES_USER;
        pass = config.env.POSTGRES_PASSWORD;
      }
    ];
  };
  services.mailpit.enable = true;

  # https://devenv.sh/scripts/
  scripts = {
    manage.exec = ''
      python manage.py "$@"
    '';
    "db:pull".exec = ''
      python bin/pg_pull_from_fly.py
    '';
    "db:restore".exec = ''
      latest_backup="$(ls -1t backups/* | head -n 1)" && echo "Latest: $latest_backup"
      dropdb "${config.env.POSTGRES_DB}"
      echo "Database ${config.env.POSTGRES_DB} dropped"
      createdb "${config.env.POSTGRES_DB}" --owner="${config.env.POSTGRES_USER}"
      echo "Database ${config.env.POSTGRES_DB} created"
      gunzip -c "$latest_backup" | psql "${config.env.POSTGRES_DB}" >/dev/null 2>&1 && echo "Restore success" || echo "Restore failed"
      python manage.py drop_test_database --noinput
      echo "Test database dropped"
    '';
    "pip:compile".exec = ''
      pip-compile --extra local -o requirements/local.txt "$@"
      pip-compile --extra production -o requirements/production.txt "$@"
    '';
    "pip:sync".exec = ''
      pip-compile --extra local -o requirements/local.txt "$@" > /dev/null 2>&1 && echo "Compiled local requirements"
      pip-compile --extra production -o requirements/production.txt "$@" > /dev/null 2>&1 && echo "Compiled production requirements"
      pip-sync requirements/local.txt
    '';
    "pip:upgrade".exec = ''
      pip-compile --extra local -o requirements/local.txt --upgrade "$@"
      pip-compile --extra production -o requirements/production.txt --upgrade "$@"
    '';
  };

  # https://devenv.sh/basics/
  enterShell = ''
    git --version # Use packages
  '';

  # https://devenv.sh/tasks/
  tasks = {
  };

  # https://devenv.sh/tests/
  enterTest = ''
    echo "Running tests"
    git --version | grep --color=auto "${pkgs.git.version}"
  '';

  # https://devenv.sh/git-hooks/
  # git-hooks.hooks.shellcheck.enable = true;

  # See full reference at https://devenv.sh/reference/options/
}
