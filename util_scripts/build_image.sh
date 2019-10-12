#!/bin/bash

docker build --network=host -t vladfedchenko/reddigram-reposter-base:latest docker -f docker/Dockerfile.base
docker build --network=host -t vladfedchenko/reddigram-reposter:latest src -f docker/Dockerfile