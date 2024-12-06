#!/bin/bash
username=$1

#pull the github profile image url and download it with the size 100x100 
gh api users/${username} --jq '.avatar_url' | sed 's/v=4/size=100/' | xargs curl -L -o image.png
magick convert -gravity east -extent 296x128 -monochrome "image.png" "${username}.png"