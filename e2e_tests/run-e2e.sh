#! /bin/bash

set -u

function die()
{
    echo $1
    exit 1
}

OPTIND=1         # Reset in case getopts has been used previously in the shell.
cwd=$(pwd)
# Initialize our own variables:
pull=0
while getopts "lpcb" opt; do
    case "$opt" in
        p)  pull=1
            ;;
    esac
done


# Makes the bash script to print out every command before it is executed except echo
# this is a replacement for 'set -x'
function preexec ()
{
    [[ $BASH_COMMAND != echo* ]] && echo >&2 "+ $BASH_COMMAND"
}
set -o functrace   # run DEBUG trap in subshells
trap preexec DEBUG


function cleanup()
{
    cd $E2E_DIR
    docker-compose down -v
}

E2E_DIR=$(dirname $(realpath ${BASH_SOURCE[0]}))
cd $E2E_DIR

if test $pull -eq 1; then
    docker-compose pull
fi

trap "cleanup" EXIT
trap "exit 1" SIGINT SIGTERM

docker-compose down -v
docker-compose up --no-start
docker-compose up helper
docker cp tests e2e-helper:/

echo "===> Starting services"
docker-compose up -d validator_one validator_two monitor
echo "===> Waiting for blocks to get mined"
timeout --foreground 105 docker-compose logs -f
echo "===> running pytest"
docker-compose up -d testrunner
result=$(docker wait testrunner)
docker-compose logs -t testrunner
echo "===> shutting down"
docker-compose down
exit $result
