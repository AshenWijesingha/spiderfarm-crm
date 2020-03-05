# SpiderFarm CRM
Originally designed for a cold-call tech support scam operation, SpiderFarm CRM is a lead management tool geared towards social engineering. 

### Disclaimer
I wrote this to meet contractual requirements for a [shady company](https://www.sslguru.com) that I was not happy about doing work for (long story, see below). This software enables one to mass scan websites and catalog data (with a nice UI) pertaining to SSL certificates, Whois data and installed CMS software (specifically WordPress) of said scanned sites. This is probably not okay to run at mass scale in most jurisdictions, and is provided for educational purposes only and also to CYA (my A, to be exact) as a whistleblower by disclosing this software to the public as being used by a telephonic fraud entity. 
¯\_(ツ)_/¯

### Features

* Web crawling API that scales horizontally - scan entire GTLD zone files, only limited by the AWS concurrent Lambda execuetion rate on your AWS account.

* Catalog unique data points for each domain name scanned including: SSL and domain name expiration, Whois registrar information, geographic IP location (GeoIP) and software/server stack finderprinting (WordPress).

* Create users and assign "sales leads" to them, consisting of website data ordered by upcoming SSL or domain name expiration. 

* upload CSVs of domain names and import into existing database

* Full demo of software features can be seen [here](https://www.youtube.com/watch?v=S4glCmPbapI): 

### Initial cleanup and installation process

These first few commits are gonna be for getting this "ready for installation" - if you try to run it now "out of the box" it will break. I'm listing the dependencies needed and the issues I'm finding as I install to a clean server.

### Additional dependencies
* Django
  * django-filebrowser-no-grapelli
  * django-celery-beat
  * djangorestframework
  * django-import-export
  * django-taggit
  * django-queryset-csv
  
* Pip dependecies
  * mysqlclient
  
### Lambda functions for Web Crawler API

There are 5 lambda function zip files that must be installed after the base Django installation to get this up and running. Getting the lambda functions to play nicely with the callbacks from the server requires some AWS permission setting from the Boto3 lirary and the console - I'll add that to the Wiki after I finish the the instructions on the clean Django CRM setup.


This software was originally designed to be run on AWS and is heavily dependant on AWS Lambda serverless functions to harvest website data as intended. With that said, it wouldn't be too difficult to adjust for any other serverless function cloud provider's services.

