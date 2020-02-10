from django.db import models
from django.utils.translation import pgettext_lazy
from django.utils.translation import ugettext_lazy as _

from spiderfarm.models import Domain
from common.models import User
from teams.models import Teams
from common.utils import LEAD_STATUS
from taggit.managers import TaggableManager
from taggit.models import GenericTaggedItemBase, TagBase, TaggedItemBase

class LeadTag(TagBase):

    class Meta:
        verbose_name = _('Lead Tag')
        verbose_name_plural = _('Lead Tags')


class TaggedLeads(GenericTaggedItemBase):

    tag = models.ForeignKey(LeadTag, related_name='lead_tag', on_delete=models.PROTECT)


class Lead(models.Model):
    domain = models.OneToOneField(Domain, on_delete=models.PROTECT, primary_key=True)
    first_name = models.CharField(("First name"), max_length=255, blank=True, null=True)
    last_name = models.CharField(("Last name"), max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(_("Status of Lead"), max_length=255,
                              blank=True, null=True, choices=LEAD_STATUS, default=LEAD_STATUS[0][0])

    assigned_to = models.ManyToManyField(User, related_name='lead_assigned_users', blank=True, null=True)
    teams = models.ManyToManyField(Teams, blank=True, null=True)
    created_on = models.DateTimeField(_("Created on"), auto_now_add=True)
    tags = TaggableManager(_("Hosting tags"), blank=True, through=TaggedLeads)

    class Meta:
        ordering =['-created_on']

    def __str__(self):
        return str(self.domain)

