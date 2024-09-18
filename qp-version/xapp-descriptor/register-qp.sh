# get appmgr http ip
httpAppmgr=$(kubectl get svc -n ricplt | grep service-ricplt-appmgr-http | awk '{print $3}') 

# for delete the rigister by curl
curl -X POST "http://${httpAppmgr}:8080/ric/v1/deregister" -H "accept: application/json" -H "Content-Type: application/json" -d '{"appName": "qp", "appInstanceName": "qp"}'

# for delete the registeration which is registered after xapp is enabled (kpimon use null appInstanceName to register)
curl -X POST "http://${httpAppmgr}:8080/ric/v1/deregister" -H "accept: application/json" -H "Content-Type: application/json" -d '{"appName": "qp", "appInstanceName": ""}'

httpEndpoint=$(kubectl get svc -n ricxapp | grep 8080 | awk '{print $3}')
rmrEndpoint=$(kubectl get svc -n ricxapp | grep 4560 | awk '{print $3}')

# do register
curl -X POST "http://${httpAppmgr}:8080/ric/v1/register" -H 'accept: application/json' -H 'Content-Type: application/json' -d '{"appName": "qp", "appVersion": "0.0.6", "configPath": "", "appInstanceName": "qp", "httpEndpoint": "", "rmrEndpoint": "10.98.145.246:4560", "config": "{\"name\": \"qp\", \"xapp_name\": \"qp\", \"version\": \"0.0.6\", \"containers\": [{\"name\": \"qp\", \"image\": {\"registry\": \"127.0.0.1:5000\", \"name\": \"o-ran-sc/ric-app-qp\", \"tag\": \"latest\" }}], \"livenessProbe\": {\"httpGet\": {\"path\": \"ric/v1/health/alive\", \"port\": 8080 }, \"initialDelaySeconds\": 5, \"periodSeconds\": 15 }, \"readinessProbe\": {\"httpGet\": {\"path\": \"ric/v1/health/ready\", \"port\": 8080 }, \"initialDelaySeconds\": 5, \"periodSeconds\": 15 }, \"messaging\": {\"ports\": [{\"name\": \"http\", \"container\": \"qp\", \"port\": 8080, \"description\": \"http service\" }, {\"name\": \"rmr-data\", \"container\": \"qp\", \"port\": 4560, \"rxMessages\": [\"TS_UE_LIST\"], \"txMessages\": [\"TS_QOE_PREDICTION\"], \"policies\": [], \"description\": \"rmr receive data port for qp\" }, {\"name\": \"rmr-route\", \"container\": \"qp\", \"port\": 4561, \"description\": \"rmr route port for qp\" }]}, \"rmr\": {\"protPort\": \"tcp:4560\", \"maxSize\": 2072, \"numWorkers\": 1, \"rxMessages\": [\"TS_UE_LIST\"], \"txMessages\": [\"TS_QOE_PREDICTION\"], \"policies\": []}}"}'

# rollback xapp
kubectl rollout restart deployment --namespace ricxapp ricxapp-qp
