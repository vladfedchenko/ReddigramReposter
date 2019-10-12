#!/bin/bash

docker build --network=host -t vladfedchenko/reddigram-reposter-base:latest service -f Dockerfile.base && \
docker build --network=host -t vladfedchenko/reddigram-reposter:latest src -f Dockerfile