#!/bin/bash

docker build -t vladfedchenko/reddigram-reposter-base:latest service -f Dockerfile.base && \
docker build -t vladfedchenko/reddigram-reposter:latest src -f Dockerfile
