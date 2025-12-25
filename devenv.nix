{
  pkgs,
  lib,
  config,
  inputs,
  ...
}:

{
  # https://devenv.sh/basics/
  env.FLY_APP = "radscheduler";
  env.FLY_PG_APP = "radscheduler-db";

  env.POSTGRES_HOST = "";
  env.DATABASE_URL = "postgres://${config.env.POSTGRES_USER}:${config.env.POSTGRES_PASSWORD}@${config.env.POSTGRES_HOST}/${config.env.POSTGRES_DB}";
  env.EMAIL_HOST = "localhost";

  dotenv.enable = true;
  dotenv.filename = [
    ".envs/.local/.django"
    ".envs/.local/.postgres"
  ];

  # https://devenv.sh/packages/
  packages = with pkgs; [
    git
    flyctl
    gzip
    coreutils
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
  services.postgres.enable = true;
  services.postgres.initialDatabases = [
    {
      name = config.env.POSTGRES_DB;
      user = config.env.POSTGRES_USER;
      pass = config.env.POSTGRES_PASSWORD;
    }
  ];
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
      python bin/pg_restore.py --clean "$@" 
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
