from django.contrib import admin
from .models import *
from import_export import resources
from import_export.admin import ImportExportModelAdmin

class DomainResource(resources.ModelResource):

    class Meta:
        model = Domain
        fields = ('id', 'tld_ext', 'domain_name', 'ssl_expire', 'ssl_issuer_name')
        
class DomainAdmin(ImportExportModelAdmin):
    resource_class = DomainResource

admin.site.register(ZoneExtension)
admin.site.register(Domain, DomainAdmin)
admin.site.register(CertificateProvider)
admin.site.register(ZoneFragment)
admin.site.register(SpiderJob)
admin.site.register(MxServerTag)
admin.site.register(WebServerTag)
admin.site.register(NameServerTag)
admin.site.register(XPoweredByTag)
admin.site.register(WebAppTag)
admin.site.register(CertIssuerTag)
