$resourceGroup = "offerup-rg"
$location = "eastus"
$planName = "offerup-plan"
$appName = "online-market-listing-intelligence"

az login
az group create --name $resourceGroup --location $location
az appservice plan create --name $planName --resource-group $resourceGroup --sku B1 --is-linux
az webapp create --resource-group $resourceGroup --plan $planName --name $appName --runtime "PYTHON|3.11"
az webapp config appsettings set --resource-group $resourceGroup --name $appName --settings APP_USERNAME=admin APP_PASSWORD=change-me APP_AUDIT_LOG_PATH=/tmp/app_audit.log
az webapp deploy --resource-group $resourceGroup --name $appName --src-path . --type zip
