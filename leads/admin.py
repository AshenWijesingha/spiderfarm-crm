from django.contrib import admin
from leads.models import Lead, LeadTag, TaggedLeads
from import_export import resources

class LeadResource(resources.ModelResource):

    class Meta:
        model = Lead


admin.site.register(Lead)
admin.site.register(LeadTag)
admin.site.register(TaggedLeads)


