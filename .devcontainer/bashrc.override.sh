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
alias reset_db="python manage.py reset_db && python manage.py drop_test_database && python manage.py migrate && python manage.py import"

# start ssh-agent
# https://code.visualstudio.com/docs/remote/troubleshooting
eval "$(ssh-agent -s)"

# Run npm install only for the first bash session
if [ ! -f ~/.npm_installed ]; then
    npm install
    touch ~/.npm_installed
fi

# install flyctl if not installed
if ! command -v flyctl &> /dev/null; then
    curl -L "https://fly.io/install.sh" | sh
    export PATH="$HOME/.fly/bin:$PATH"
fi