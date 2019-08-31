#!/bin/bash

docker run -it --mount type=bind,source="$(pwd)"/data,target=/app/data vladfedchenko/reddigram-reposter