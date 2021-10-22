#!/usr/bin/env bash

usage () {
  echo
  echo "Usage:"
  echo "./set_user_role.bash <username> (user|curator|owner|admin)?"
  echo
  echo "If not specified, the default role assigned to give read-only 'user' access."
  exit 1
  }

if [[ -z "$1" ]]; then
  echo
  echo "Please specify the 'username' whose role you wish to set:"
  usage
else
    username=$1
fi

declare -A role_level
role_level['user']=0
role_level['curator']=1
role_level['owner']=2
role_level['admin']=3
role_level['root']=4

role=${2:-'user'}

echo "Give account '${username}' the role of '${role}'?"
read -p "Continue? (yes/no - default 'no'): " YESNO

if [[ ! $YESNO = "yes" ]]; then
   echo "Sorry to see you leave... Good bye!";
   exit
else
  echo "OK, here we go!...";
fi

python -m kgea.aws.cognito set-user-attribute ${username} 'custom:User_Role' ${role_level[$role]}
python -m kgea.aws.cognito get-user-details ${username}

echo Done!
