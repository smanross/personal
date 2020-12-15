# Powershell example 
add-type @"
   using System.Net;
   using System.Security.Cryptography.X509Certificates;
   public class TrustAllCertsPolicy : ICertificatePolicy {
   public bool CheckValidationResult(
   ServicePoint srvPoint, X509Certificate certificate,
   WebRequest request, int certificateProblem) {
   return true;
   }
   }
  "@

# Then:

[System.Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12  # powershell defaults to Tls10 and CB requires TLS 1.2
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCertsPolicy

# Then, request token.

$postparam=@{username='myusername';password='mypassword'}
$response=Invoke-WebRequest -Uri https://cb.whatever.com/api/v2/api-token-auth/ -Method Post -Body $postparam -UseBasicParsing

# Get token value from the response,

$hash=$response.Content |ConvertFrom-Json
$token= $hash.token

# Make a get call to see list of servers, or whatever you want to do now that you have the token

$response=Invoke-WebRequest -Uri https://10.55.62.10/api/v2/servers/ -Method Get -Headers @{'Authorization' = 'Bearer ' + $token} -UseBasicParsing
