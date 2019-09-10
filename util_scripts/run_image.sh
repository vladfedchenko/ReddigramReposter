#!/bin/bash

port=5000

show_help() {
  echo "Usage: cmd [-h] [-p <int>]" 1>&2
}

while getopts ":hp:" opt; do
  case ${opt} in
    h ) show_help
      return 0
      ;;
    p ) port=$OPTARG
      ;;
    \? ) show_help
      return 1
      ;;
  esac
done

docker run -it -p "$port":5000 --mount type=bind,source="$(pwd)"/data,target=/app/data vladfedchenko/reddigram-reposter