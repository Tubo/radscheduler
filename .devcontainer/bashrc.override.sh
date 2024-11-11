
#
# .bashrc.override.sh
#

# persistent bash history
HISTFILE=~/.bash_history
PROMPT_COMMAND="history -a; $PROMPT_COMMAND"

# set some django env vars
source /entrypoint

# restore default shell options
set +o errexit
set +o pipefail
set +o nounset

alias makemigrations="python manage.py makemigrations"
alias migrate="python manage.py migrate"
alias reset_db="python manage.py reset_db && python manage.py drop_test_database && python manage.py migrate && python manage.py import resources/2021-2023.csv"

# start ssh-agent
# https://code.visualstudio.com/docs/remote/troubleshooting
eval "$(ssh-agent -s)"

npm install

# install flyctl
curl -L "https://fly.io/install.sh" | sh
export PATH="$HOME/.fly/bin:$PATH"
