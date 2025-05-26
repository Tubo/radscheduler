# powerline prompt
prompt() {
    PS1="$(powerline-rs --shell bash $?)"
}
PROMPT_COMMAND=prompt

# change bash history file to be in project directory (not home)
export HISTFILE=$(pwd)/.bash_history
# remove duplicates from history
export HISTCONTROL=ignoredups:erasedups
# append to history, don't overwrite it
shopt -s histappend