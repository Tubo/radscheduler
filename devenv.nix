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
    DATABASE_URL = "postgres://${config.env.POSTGRES_USER}:${config.env.POSTGRES_PASSWORD}@${config.env.PGHOST}:${toString config.env.PGPORT}/${config.env.POSTGRES_DB}";

    EMAIL_HOST = "localhost"; # For Mailpit
    EMAIL_PORT = config.processes.mailpit.ports.smtp.value;
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
    flyctl
    gzip
    coreutils
    playwright-test
    playwright-driver
  ];

  # https://devenv.sh/languages/
  languages.python = {
    enable = true;
    version = "3.13";
    venv.enable = true;
    venv.requirements = ./requirements/local.txt;
  };
  languages.javascript.enable = true;
  languages.javascript.pnpm = {
    enable = true;
    install.enable = true;
  };

  # https://devenv.sh/processes/
  # processes.dev.exec = "${lib.getExe pkgs.watchexec} -n -- ls -la";
  # Skipped under `devenv test`, which only needs the services.
  processes = lib.mkIf (!config.devenv.isTesting) {
    "dev:django" = {
      ports.http.allocate = 8000;
      exec = ''
        python manage.py runserver_plus 0.0.0.0:${toString config.processes."dev:django".ports.http.value}
      '';
    };
    "dev:webpack".exec = ''
      pnpm webpack --watch --config webpack/dev.config.js
    '';
  };

  # https://devenv.sh/services/
  services.postgres = {
    enable = true;
    # Pin the major version: a newer default can't open the existing data dir.
    package = pkgs.postgresql_17;
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
      python bin/pg_restore.py "$@" &&
      python manage.py drop_test_database --noinput
    '';
    "db:refresh".exec = ''
      db:pull && db:restore --latest --clean
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

  # https://devenv.sh/tasks/
  tasks = {
    "app:migrate" = lib.mkIf (!config.devenv.isTesting) {
      exec = "python manage.py migrate --noinput";
      after = [ "devenv:processes:postgres" ];
      before = [ "devenv:processes:dev:django" ];
    };
    # Hooks still run on commit; don't run them over the whole repo in `devenv test`.
    "devenv:git-hooks:run".before = lib.mkForce [ ];
  };

  # https://devenv.sh/tests/
  enterTest = ''
    wait_for_port ${toString config.env.PGPORT} 60
    pytest
  '';

  # https://devenv.sh/git-hooks/
  git-hooks = {
    excludes = [
      "^docs/"
      "/migrations/"
    ];
    hooks = {
      trim-trailing-whitespace.enable = true;
      end-of-file-fixer.enable = true;
      check-json = {
        enable = true;
        excludes = [ "^\\.vscode/" ]; # JSON with comments
      };
      check-toml.enable = true;
      check-xml.enable = true;
      check-yaml.enable = true;
      python-debug-statements.enable = true;
      check-builtin-literals.enable = true;
      check-case-conflicts.enable = true;
      check-docstring-first.enable = true;
      detect-private-keys.enable = true;

      prettier = {
        enable = true;
        settings = {
          single-quote = true;
          tab-width = 2;
        };
        excludes = [
          "radscheduler/templates/"
          "pnpm-lock.yaml"
        ];
      };

      django-upgrade = {
        enable = true;
        name = "django-upgrade";
        entry = "${pkgs.django-upgrade}/bin/django-upgrade --target-version 5.2";
        types = [ "python" ];
      };
      # Lint (incl. import sorting and pyupgrade rules) and format; configured in pyproject.toml.
      ruff.enable = true;
      ruff-format.enable = true;

      djlint-reformat-django = {
        enable = true;
        name = "djlint-reformat-django";
        entry = "${pkgs.djlint}/bin/djlint --reformat --profile=django";
        types_or = [ "html" ];
      };
      djlint-django = {
        enable = true;
        name = "djlint-django";
        entry = "${pkgs.djlint}/bin/djlint --profile=django";
        types_or = [ "html" ];
      };
    };
  };

  # See full reference at https://devenv.sh/reference/options/
}
