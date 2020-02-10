# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import models
from django.utils.translation import ugettext_lazy as _
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db.models import Count
import random
import hashlib
from taggit.managers import TaggableManager
from taggit.models import GenericTaggedItemBase, TagBase, TaggedItemBase
import json
import boto3
import time
import re
import hashlib
import os

SSL_LAMBDA = 'ssl_crawler'
WHOIS_LAMBDA = 'whois_pull'
GEOIP_LAMBDA = 'geoip_lookup'
GHOST_CRAWLER = 'ghost_crawler'
GTLD_IMPORT = 'gtld_importer'

JOB_STATUS = (
    ('RUNNING', 'RUNNING'),
    ('COMPLETE', 'COMPLETE'),
    ('PENDING', 'PENDING'),
)

SPIDER_TYPE = (
    ('GHOST', 'GHOST'),
    ('IMPORT', 'IMPORT'),
    ('UPDATE', 'UPDATE'),
)

CRAWL_TYPE = (
    ('ZONE', 'ZONE'),
    ('DOMAIN', 'DOMAIN'),
    ('CSV','CSV'),
)

DATA_TYPE = (
    ('SSL', 'SSL'),
    ('HOST', 'HOST'),
    ('WEB', 'WEB'),
)

IMPORT_STATUS = (
    ('NEW', 'NEW'),
    ('SSL', 'SSL'),
    ('HOST', 'HOST'),
)

## ssl issuer tag ## 

class CertIssuerTag(TagBase):

    class Meta:
        verbose_name = _('Certificate Issuer')
        verbose_name_plural = _('Certificate Issuers')

class TaggedCertIssuers(GenericTaggedItemBase):

    tag = models.ForeignKey(CertIssuerTag, related_name='cert_issuer', on_delete=models.PROTECT)

## ------------- ##

## mx server tag ##

class MxServerTag(TagBase):
    
    class Meta:
        verbose_name = _('MX Server')
        verbose_name_plural = _('MX Servers')

class TaggedMxServers(GenericTaggedItemBase):

    tag = models.ForeignKey(MxServerTag, related_name='domain_mx_servers', on_delete=models.PROTECT)

## ---------- ##

# web server type ##
class WebServerTag(TagBase):

    class Meta:
        verbose_name = _('Web Server')

class TaggedWebServers(GenericTaggedItemBase):

    tag = models.ForeignKey(WebServerTag, related_name='domain_web_server', on_delete=models.PROTECT)
## ---------- ##

## name server tag ##

class NameServerTag(TagBase):

    class Meta:
        verbose_name = _('Name Server')
        verbose_name_plural = _('Name Servers')

class TaggedNameServers(GenericTaggedItemBase):

    tag = models.ForeignKey(NameServerTag, related_name='domain_name_servers', on_delete=models.PROTECT)

## ----------- ##

class XPoweredByTag(TagBase):

    class Meta:
        verbose_name = _('X-Powered-By Header')
        verbose_name_plural = _('X-Powered-By Headers')

class TaggedXPoweredByHeaders(GenericTaggedItemBase):

    tag = models.ForeignKey(XPoweredByTag, related_name='domain_x_powered_by', on_delete=models.PROTECT)

class WebAppTag(TagBase):

    class Meta:
        verbose_name = _('Web App Signature')
        verbose_name_plural= _('Web App Signatures')

class TaggedWebAppSignatures(GenericTaggedItemBase):

    tag = models.ForeignKey(WebAppTag, related_name='domain_web_app_tags', on_delete=models.PROTECT
            )
## san list tag ##

class SanListTag(TagBase):

    class Meta:
        verbose_name = _('SAN List')

class TaggedSanEntries(GenericTaggedItemBase):

    tag = models.ForeignKey(SanListTag, related_name='domain_san_list', on_delete=models.PROTECT)

## ------------ ##

## domain spider job tag ##

class DomainSpiderJobTag(TagBase):

    class Meta:
        verbose_name = _('Domain Spider Job')
        verbose_name_plural = _('Domain Spider Jobs')

class TaggedDomainSpiderJobs(GenericTaggedItemBase):

    tag = models.ForeignKey(DomainSpiderJobTag, related_name='domain_spider_jobs', on_delete=models.PROTECT)

## ------------- ##

## zone spider job tag ##

class ZoneSpiderJobTag(TagBase):

    class Meta:
        verbose_name = _('Zone Spider Jobs')

class TaggedZoneSpiderJobs(GenericTaggedItemBase):

    tag = models.ForeignKey(ZoneSpiderJobTag, related_name='zone_spider_jobs', on_delete=models.PROTECT)

## ------------ ##

## assigned zonefragments tag ##

class AssignedZoneFragmentsTag(TagBase):

    class Meta:
        verbose_name = _('Assigned Zone Fragments')

class TaggedAssignedZoneFragments(GenericTaggedItemBase):

    tag = models.ForeignKey(AssignedZoneFragmentsTag, related_name='assigned_zone_frags', on_delete=models.PROTECT)

## ------------ ##

def tld_zone_path(instance, filename):
    ''' return associated ZoneExtension's storage path '''
    print('-- INSIDE upload_to function --')
    return 'uploads/zone_files/' + str(instance.tld_ext).lstrip('.') + '/' + filename  


class ZoneExtension(models.Model):

    time_added = models.DateTimeField( _("zone added"), auto_now_add=True)
    tld_extension = models.CharField(_("TLD Extension"), blank=False, null=False, unique=True, max_length=10)
    domain_extractor = models.CharField(_("Regex extractor for zone fragments"), blank=True, null=True, unique=True, max_length=200)
    storage_path = models.FilePathField(path='/home/spiderfarmer/SFCRM/media/uploads/zone_files', match='\.txt$', default='/home/spiderfarmer/SFCRM/media/uploads/zone_files', blank=True)    

    def __str__(self):
        return '%s' % self.tld_extension.lower()

    def get_import_path(self):
        ''' return import path for specific tlds'''
        return self.storage_path + '/' + 'imported'

    def no_dot(self):
        return str(self).lstrip('.')

    def count_zonefrags(self, imported=False):
        if imported:
            _directory = self.get_import_path()

        else:
            _directory = self.storage_path

        # pull out only files, not directories - if '.txt' in filename
        frag_count = len([name for name in os.listdir(_directory) if '.txt' in name])
        return frag_count


class ZoneFragment(models.Model):

    tld_ext = models.ForeignKey(ZoneExtension, related_name='zonefrag_tld', on_delete=models.PROTECT)
    unique_domains = models.IntegerField(_("Unique domains"), blank=True, null=True)
    upload_timestamp = models.DateTimeField( _("Upload timestamp"), auto_now_add=True)
    zone_file = models.FileField(_("Zonefile fragment"), upload_to=tld_zone_path)
    zone_signature = models.CharField(_("Zone fragment checksum"),  unique=True, max_length=40, blank=True, null=True)
    spider_jobs = TaggableManager(_("Spider jobs"), blank=True, through=TaggedZoneSpiderJobs)
    imported = models.BooleanField(_('Imported'), default=False)

    def __str__(self):
        return 'Zone fragment #%s' % self.pk

    def prefix_http(self, domain, ssl=False):
        if ssl:
            return 'https://' + domain
        else:
            return 'http://' + domain

    def extract_domain(self, line, extract_re):
        '''
        take line, run regex extractor on it
          if match, return extracted string, else None
        '''
        print('-- inside ZoneFragment.extract_domain')
        print('-- line: %s' % line)
        extract_re = self.tld_ext.domain_extractor
        _domain = re.search(extract_re, line)
        print('-- _domain: %s' % _domain)

        if _domain:
            print('-- domain found: %s' % _domain.group(1))
            _url = str(_domain.group(1)) + str(self.tld_ext)
            print('-- url: %s' % _url.lower())
            return _url.lower()

        return None

    def get_unique_domains(self):
        '''
        read zone_break file into a list,
          extract unique domains and return as list
        '''
        url_list = []
        zone_lines = []
        unique_list = []

        with open(self.zone_file.path) as f:
            zone_lines = [line.rstrip('\n') for line in f]

            for line in zone_lines:
                _extract = self.extract_domain(line, self.tld_ext.domain_extractor)

                if _extract:
                    print('-- adding %s to url_list ' % _extract)
                    url_list.append(_extract)

        # filter unique domains -> list->set->list
        unique_list = list(set(url_list))

        return unique_list

class Domain(models.Model):

    domain_name = models.URLField(unique=True)
    domain_common = models.CharField(_("Non-prefixed domain"), max_length=200, blank=True, null=True)
    redirect_url = models.URLField( _("Redirects to"), blank=True, null=True)
    time_added = models.DateTimeField( _("Domain added"), auto_now_add=True)
    tld_ext = models.ForeignKey(ZoneExtension, related_name='tld_ext', on_delete=models.PROTECT)
    last_export = models.DateTimeField( _("Last export time"), blank=True, null=True)
    ssl_expire = models.DateTimeField( _("SSL expire time"), blank=True, null=True)
    ssl_issuer_name = TaggableManager(_("SSL issuer"), blank=True, through=TaggedCertIssuers)
    ssl_issuer_org_unit = models.CharField(_("Issuer org unit"), max_length=200, blank=True, null=True)
    ssl_url = models.CharField(_("Primary ssl domain"), max_length=200, blank=True, null=True)
    ssl_san = TaggableManager(_("SAN List"), blank=True, through=TaggedSanEntries)
    domain_expire = models.DateTimeField( _("Domain expire date"), blank=True, null=True)
    server_type = TaggableManager(_("Server software"), blank=True, through=TaggedWebServers)
    name_servers = TaggableManager(_("Name servers"), blank=True, through=TaggedNameServers)
    mx_servers = TaggableManager(_("MX servers"), blank=True, through=TaggedMxServers)
    x_powered_by = TaggableManager(_("X-Powered-By Headers"),blank=True,through=TaggedXPoweredByHeaders)
    domain_registrar = models.CharField(_("Domain registrar"), max_length=50, blank=True, null=True)
    software_tags = TaggableManager(_("Web app tags"), blank=True, through=TaggedWebAppSignatures)
    registrar_url = models.URLField(_("Registrar URL"), blank=True, null=True)
    registrant_country = models.CharField(_("Registrant country"), max_length=50, blank=True, null=True)
    registrant_email = models.CharField(_("Registrant email"), max_length=200, blank=True, null=True)
    geoip_country = models.CharField(_("GeoIP country"), max_length=200, blank=True, null=True)
    geoip_geocode = models.CharField(_("GeoIP country code"), max_length=200, blank=True, null=True)
    site_ip = models.GenericIPAddressField(_("Current IP"), blank=True, null=True)
    last_ghost_crawl = models.DateTimeField( _("Last Ghost crawl"), blank=True, null=True)
    last_ssl_update = models.DateTimeField( _("Last SSL update"), blank=True, null=True)
    last_whois_update = models.DateTimeField( _("Last WHOIS update"), blank=True, null=True)
    last_geoip_update = models.DateTimeField( _("Last GeoIP update"), blank=True, null=True)
    ssl_error = models.CharField(_("SSL error message"),  max_length=255, blank=True, null=True)
    whois_error = models.CharField(_("WHOIS error message"),  max_length=255, blank=True, null=True)
    geoip_error = models.CharField(_("GeoIP error message"),  max_length=255, blank=True, null=True)
    import_status = models.CharField(_("Import status"), max_length=25, choices=IMPORT_STATUS, default=IMPORT_STATUS[0][0])
    spider_jobs = TaggableManager(_("Spider jobs"), blank=True, through=TaggedDomainSpiderJobs)

    def no_prefix_url(self):
        http_prefix = 'http://'
        https_prefix = 'https://'
        norm_url = self.domain_name.lower()

        if norm_url.startswith(http_prefix):
            return norm_url[len(http_prefix):]
        elif norm_url.startswith(https_prefix):
            return norm_url[len(https_prefix):] 
        else:
            return self.domain_name

    def __str__(self):
        return self.no_prefix_url()
    
    def get_san_list(self):
        if self.ssl_san:
            san_list = self.ssl_san.split(" ")
            return san_list
        return None
 
    def clean(self):
        print("inside model clean for Domain")
        if self.tld_ext.tld_extension.lower() not in self.domain_name:
            err_str = 'domain name and tld extension do not match.'
            raise ValidationError(err_str)


class CertificateProvider(models.Model):

    provider_name = models.CharField(_('SSL Cert Provider'),unique=True, max_length=20)
    include_sales = models.BooleanField(_('Include in Sales CSV Exports?'),default=False)
    added_timestamp = models.DateTimeField( _("Cert provider added timestamp"), auto_now_add=True, blank=True, null=True)

    def __str__(self):
        return self.provider_name


class SpiderJob(models.Model):

    spider_type = models.CharField(_("Spider type"), max_length=25, choices=SPIDER_TYPE, default=SPIDER_TYPE[1][1])
    start_timestamp = models.DateTimeField( _("Start timestamp"), auto_now_add=True)
    end_timestamp = models.DateTimeField( _("End timestamp"), blank=True, null=True)
    celery_id = models.CharField(_("Celery worker ID "), max_length=36, blank=True, null=True)
    crawl_type = models.CharField(_("Crawl type"), max_length=25, choices=CRAWL_TYPE, default=CRAWL_TYPE[0][0])
    data_type = models.CharField(_("Data type"), max_length=25, choices=DATA_TYPE, default=DATA_TYPE[0][0])
    job_status = models.CharField(_("Job status"), max_length=25, choices=JOB_STATUS, default=JOB_STATUS[2][0])
    assigned_zones = TaggableManager(_('Assigned zone fragments'), blank=True, through=TaggedAssignedZoneFragments)  

    def tag_text(self, job_num):

        _tag = self.spider_type.capitalize() + ' ' + self.crawl_type.capitalize() + ': ' + self.data_type

        return '#%s - %s' % (job_num, _tag)

    def __str__(self):
        return self.tag_text(self.pk)


    def sort_unique_domains(self, passed_urls=None):
        '''
         -- only for zone spider jobs --
              if passed in a list, sort and return,
              else pull the unique list from tagged zone fragment
        '''
        if self.crawl_type.lower() == 'zone':
            url_list, sorted_list = [], []

            if passed_urls:
                url_list = passed_urls

            else:
                # select all the valid zone fragments tagged w/ spider job, having unique domains > 0
                _zone_frags = ZoneFragment.objects.filter(spider_jobs__name__in=[self.tag_text(self.pk)]).filter(unique_domains__gt=0)

                print('total zone fragments tagged with spider job: %s' % _zone_frags.count())

                for frag in _zone_frags:
                    url_list.extend(frag.get_unique_domains())

            print('entry # in url_list: %s' % len(url_list))

            for domain in sorted([line.strip().split('.')[::-1] for line in url_list]):
                sorted_list.append('.'.join(domain[::-1]))

            return sorted_list

    
    def get_domain_list(self):
        '''
        queries for ZoneFragment with the spider job pk in tag,
          and returns a list with those domains in it
        '''
        # dump sorted url list from ZoneFrag obj
        domain_list = self.sort_unique_domains()
        return domain_list


    def invoke_lambda(self, domain, lambda_name, job_tag=''):
        print('-- inside invoke lambda --')
        # assemble the payload data in json
        lambda_client = boto3.client('lambda', region_name='us-west-2')

        if job_tag:
            # create payload with spiderjob tag string 
            payload = {
                'domain_name': domain,
                'dev': 'True',
                'job_tag': job_tag,
            }

        else:
            # normal payload
            payload = {
                'domain_name': domain,
                'dev': 'True',
            }

        # json-ize the dictionary
        json_payload = json.dumps(payload)

        if lambda_name == SSL_LAMBDA:
            print('-- invoking SSL lambda --')
            # hit ssl lammie with domain name
            invoke_response = lambda_client.invoke(FunctionName=SSL_LAMBDA,
                                                   InvocationType='Event',
                                                   Payload=json_payload)
        if lambda_name == WHOIS_LAMBDA:
            print('-- invoking WHOIS lambda --')
            # hit whois lammie with domain name
            invoke_response = lambda_client.invoke(FunctionName=WHOIS_LAMBDA,
                                               InvocationType='Event',
                                               Payload=json_payload)

        if lambda_name == GEOIP_LAMBDA:
            print('-- invoking GeoIp lambda --')
            # hit geoip lammie with domain name
            invoke_response = lambda_client.invoke(FunctionName=GEOIP_LAMBDA,
                                               InvocationType='Event',
                                               Payload=json_payload)

        if lambda_name == GHOST_CRAWLER:
            print('-- invoking Ghost Crawler --')
            # hit Ghost Crawler lambda with domain name
            invoke_response = lambda_client.invoke(FunctionName=GHOST_CRAWLER,
                                               InvocationType='Event',
                                               Payload=json_payload)

        if lambda_name == GTLD_IMPORT:
            print('-- invoking GTLD Import lambda --')
            # hit GTLD lammie with domain name
            invoke_response = lambda_client.invoke(FunctionName=GTLD_IMPORT,
                                               InvocationType='Event',
                                               Payload=json_payload)


    def imported_path(self, home=False, json=False):
        print('-- inside SpiderJob.imported_path --')
        _path = '/imported'
        _json = '/json'

        import_path = ''

        try:
            zone_file = ZoneFragment.objects.get(zone_signature=self.assigned_zone)

            if home:
                import_path = zone_file.tld_ext.storage_path

            elif json:
                import_path = zone_file.tld_ext.storage_path + _json

            else:
                import_path = zone_file.tld_ext.storage_path + _path

            print('-- import path: %s' % import_path)
            return import_path

        except Exception as e:
            print(e)


    def zonefrag_name(self):
        print('-- inside SpiderJob.zonefrag_name --')
        name_re = r'\/(zonebreak.*.txt)'

        try:
            zone_frag = ZoneFragment.objects.get(zone_signature=self.assigned_zone)
            file_name = re.search(name_re, zone_frag.zone_file.name)

            if file_name:
                return file_name.group(1)

            else:
                print('-- filename regex failed: %s' % file_name)
                return None

        except Exception as e:
            print(e)


