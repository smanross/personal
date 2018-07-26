#using this as a guide and version 8.2 ---> https://<cloudboltip>/static-c2baf63/docs/advanced/api/index.html

export MYUSER="some_user_name"
export MYPW="blahblah"
export MYCBIP="my_cloudbolt_ip"
#I already have a file with the json formatted data without newlines
#  **you can test the "order json file" is suitable with: cat filename | python
#  -mjson.tool
#  **My file was created by ordering a blueprint
#    and then pressing API,·
#    then capturing that to a file,·
#    then removing newlines,·
#    and transferring the file to my unix server.
echo "USER = ${MYUSER}"
echo "PW = ${MYPW}"
export JSONORDER=`cat json-oneline`
#use the username and pw to get an API token
curl -k1 -X POST -H "Content-Type: application/json" -d '{"username":"'"$MYUSER"'", "password": "'"$MYPW"'"}' --insecure "https://$MYCBIP/api/v2/api-token-auth/" -o token.txt
#read the token into $value
value=($(cat token.txt | python -mjson.tool))
#delete temp file (
rm -rf token.txt
#unset these vars (not needed anymore)
unset MYUSER
unset MYPW
#export the auth token and remove the "s
export MYTOKEN=${value[2]//\"}
echo "TOKEN = $MYTOKEN"
curl -v -X POST -k1  -H "Authorization: Bearer $MYTOKEN" -H "Content-Type:application/json" -d "$JSONORDER" --insecure "https://${MYCBIP}/api/v2/orders/"

#unset these vars (not needed anymore)
unset MYTOKEN

#output:
#     {"_links":{"self":{"href":"/api/v2/orders/104","title":"Order id 104"},"group":{"href":"/api/v2/groups/2","title":"Manross.net"},"owner":{"href":"/api/v2/users/2","title":"Steven Manross"},"approved-by":{"href":"/api/v2/users/2","title":"Steven Manross"},"actions":[{"duplicate":{"href":"/api/v2/orders/104/actions/duplicate","title":"Duplicate 'Order id 104'"}}],"jobs":[{"href":"/api/v2/jobs/13364","title":"Job id 13364"}]},"name":"","id":"104","status":"ACTIVE","rate":"28.80/month","create-date":"2018-07-26T17:43:47.463904","approve-date":"2018-07-26T17:44:15.735044","items":{"deploy-items":[{"resource-name":"azure linux test","resource-parameters":{},"blueprint":"/api/v2/blueprints/9","blueprint-items-arguments":{"build-item-Linux Server":{"environment":"/api/v2/environments/5","attributes":{"quantity":1},"parameters":{"node-size":"Basic_A1","create-public-ip":"False"},"os-build":"/api/v2/os-builds/12"}}}]}}
