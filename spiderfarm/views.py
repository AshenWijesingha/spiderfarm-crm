# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.parsers import JSONParser, MultiPartParser
from django.views.generic import (
    CreateView, UpdateView, DetailView, ListView, TemplateView, View)
from django.http import HttpResponse
from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import *
from .tasks import import_domains
from celery.result import AsyncResult
from django.http import Http404
from django.conf import settings
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from .models import *
import os, os.path
import datetime
import re


def remove_prefix(domain):
    if 'https://' in domain:
        return domain.replace('https://', '')

    if 'http://' in domain:
        return domain.replace('http://', '')

def parse_spiderjob_status(job_ids):
    # Input: list from queryset of "RUNNING" SpiderJobs in DB
    # Output: dict with error state or job_status w/ task_id
    if len(job_ids) > 1:
        print('-- error: celery id returned more than one')
        data = {'job_status': 'error - multiple job ids returned'}

    elif not job_ids:
        print('-- SpiderJob manager is ready for jobs')
        data = {'job_status': 'ready'}

    else:
        print('-- current celery task id: %s' % job_ids.first())
        data = {'task_id': str(job_ids.first()), 'job_status': 'running',}
        
    return data
        
class CreateOrUpdateDomain(APIView):
    parser_classes = (JSONParser,)
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)


    def post(self, request, format=None):

        # look up the domain, if exists, update, else make new Domain record
        try:
            print('-- inside CreateOrUpdateDomain.post(), trying to serialize ...')
            # get domain from request
            target_domain = request.data['domain_name']
            
            print('-----------------------------')
            print('-- request.data: %s' % request.data)

            domain_rec = Domain.objects.get(domain_name=target_domain)
            
            # initialize serializer w/ record instance AND data for update 
            serializer = DomainSerializer(domain_rec, data=request.data)

            if serializer.is_valid():
                
                print('valid Domain serializer -> saving Domain record')
                print(serializer.validated_data)

                if request.data['name_servers']:
                    ns_list = request.data['name_servers'].rstrip(' ').split(' ')
                    for ns in ns_list:
                        domain_rec.name_servers.add(ns)

                domain_rec.domain_expire = serializer.validated_data['domain_expire']
                domain_rec.domain_registrar = serializer.validated_data['domain_registrar']
                domain_rec.registrar_url = serializer.validated_data['registrar_url']
                domain_rec.registrant_email = serializer.validated_data['registrant_email']
                domain_rec.registrant_country = serializer.validated_data['registrant_country']

                domain_rec.last_whois_update = datetime.datetime.now()

                domain_rec.save()

                # check for SpiderJob tag, update
                job_tag = request.POST.get('spider_jobs', '')

                if job_tag:
                    print('-- SpiderJob tag found: %s' % job_tag)
                    domain_rec.spider_jobs.add(job_tag)


                return Response("Updated Domain data for %s" % target_domain, status=status.HTTP_201_CREATED)
            else:
                # something fucked up, throw back errors
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Domain.DoesNotExist: 

            print('-- Domain %s DNE, trying to add' % request.data['domain_name'])

            if request.data['registrant_country'] == 'US':
                # Domain isn't in DB currently, create a new Domain record
                whois_update=datetime.datetime.now()
                tld_match = re.search(r'http\:\/\/[\w-]+(\.\w+)*$', request.data['domain_name'])

                if tld_match:
                    print("extracted tld: " + tld_match.group(1))
                    # with extracted tld, make sure its in the db and save
                    tld = str(tld_match.group(1))
                    try:
                        tld_rec = ZoneExtension.objects.get(tld_extension=tld)
                        new_domain = Domain.objects.create(tld_ext=tld_rec, last_whois_update=whois_update, domain_name=request.data['domain_name'])

                        new_domain.domain_expire = request.data['domain_expire']
                        new_domain.domain_registrar = request.data['domain_registrar']
                        new_domain.registrar_url = request.data['registrar_url']
                        new_domain.registrant_email = request.data['registrant_email']
                        new_domain.registrant_country = request.data['registrant_country']
                        
                        new_domain.save()

                        ns_list = request.data['name_servers'].rstrip(' ').split(' ')
                        for ns in ns_list:
                            new_domain.name_servers.add(ns)

                        # check for SpiderJob tag, update
                        job_tag = request.POST.get('spider_jobs', '')

                        if job_tag:
                            print('-- SpiderJob tag found: %s' % job_tag)
                            new_domain.spider_jobs.add(job_tag)

                        return Response("Added Domain record for %s" % request.data['domain_name'], status=status.HTTP_201_CREATED)

                    except ZoneExtension.DoesNotExist:
                        print('%s is not a valid ZoneExtension' % tld)
                        return Response('invalid ZoneExtension', status=status.HTTP_400_BAD_REQUEST)

                    except Exception as e:
                        print(e)
                        return Response(e, status=status.HTTP_400_BAD_REQUEST)

            else:
                return Response('Domain not registered in US, skipping DB save', status=status.HTTP_400_BAD_REQUEST)


class CreateOrUpdateGeoIp(APIView):
    parser_classes = (JSONParser,)
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)


    def post(self, request, format=None):

        try:
            print('-- inside UpdateGeoIP.post(), trying to serialize ...')
            print('-- request.data: %s' % request.data)

            target_domain = request.data['domain_name']
            print('-- trying to lookup/update existing record')

            domain_rec = Domain.objects.get(domain_name=target_domain)
         
            # initialize serializer w/ record instance AND data for update 
            serializer = GeoIpSerializer(domain_rec, data=request.data)
            print('recieved serializer: %s' % serializer)

            if serializer.is_valid():
                print('valid GeoIP serializer -> saving Domain record')
                print(serializer.validated_data)
                print('----------------------------------------------')
                updated_record = serializer.save()

                # check for spider job tag, update
                job_tag = request.POST.get('spider_jobs', '')
                
                if job_tag:
                    print('-- SpiderJob tag found: %s' % job_tag)
                    updated_record.spider_jobs.add( job_tag )

                return Response("Updated GeoIP data for %s" % target_domain, status=status.HTTP_201_CREATED)

            else:
                print(serializer.errors)
                domain_rec.last_geoip_update = datetime.datetime.now()
                domain_rec.geoip_error = serializer.errors
                domain_rec.save()

        except Domain.DoesNotExist:

            print('-- Domain not found; check GeoIP data to add')

            if request.data['geoip_geocode'] == 'US':

                serializer = GeoIpSerializer(data=request.data)
          
                if serializer.is_valid():
                    print('valid serializer -> saving Domain record')
                    print(serializer.validated_data)  
                    domain_record = serializer.save()

                    # check for spider job tag, update
                    job_tag = request.POST.get('spider_jobs', '')

                    if job_tag:
                        print('-- SpiderJob tag found: %s' % job_tag)
                        domain_record.spider_jobs.add( job_tag )

                    return Response("Successfully created new Domain record", status=status.HTTP_201_CREATED)

                else:
                    print('-- invalid serializer --')
                    print(serializer.errors)
            else:
                return Response("Non US-based IP - skipping DB save", status=status.HTTP_400_BAD_REQUEST)
            #return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(e)
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)


class UpdateSslData(APIView):
    parser_classes = (JSONParser,)
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    
    def post(self, request, format=None):

        target_domain = request.data['domain_name']
        print('target domain: %s' % target_domain)

        try:
            print('-- inside UpdateSslData.post(), trying to serialize ...')
            print('-- request.data: %s' % request.data)

            # get domain from serializer
            domain_rec = Domain.objects.get(domain_name=target_domain)
 
            #if request.data['ssl_expire']:
            #    print('expire_date: %s' % request.data['ssl_expire'])

            # initialize serializer w/ record instance AND data for update 
            serializer = SslSerializer(domain_rec, data=request.data)

            if serializer.is_valid():
                print('valid SSL serializer -> saving Domain record')
                print(serializer.validated_data)

                # break up SAN into list and add to tags
                san_list = request.data['ssl_san'].rstrip(' ').split(' ')

                domain_rec.ssl_san.clear()

                for dom in san_list:
                    print('--- SAN list entry: %s' % dom)
                    domain_rec.ssl_san.add(dom)

                domain_rec.ssl_expire = serializer.validated_data['ssl_expire']
                domain_rec.ssl_url = serializer.validated_data['ssl_url']
                
                domain_rec.ssl_issuer_name.set( request.data['ssl_issuer_name'] )

                if serializer.validated_data['ssl_issuer_org_unit']:
                    domain_rec.ssl_issuer_org_unit = serializer.validated_data['ssl_issuer_org_unit']
                
                # -- check issuer for free cert signatures, flag error 
                bad_issuers = ["aws", "cpanel", "encrypt"]
                for issuer in bad_issuers:
                    if issuer in request.data['ssl_issuer_name'].lower():
                        domain_rec.ssl_error = '-- Free cert issuer --'

                domain_rec.last_ssl_update = datetime.datetime.now()

                domain_rec.save()

                return Response("Updated SSL data for %s" % target_domain, status=status.HTTP_200_OK)

            else:
                print(serializer.errors)
                # update Domain record with ssl error and last_ssl_update field instead
                domain_rec.last_ssl_update = datetime.datetime.now()
                domain_rec.ssl_error = serializer.errors
                domain_rec.save()

        except Exception as e:
            print(e)
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)


class UpdateSignatureData(APIView):
    parser_classes = (JSONParser,)
    authentication_classes = (TokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request, format=None):
    
        target_domain = request.data['domain_name']
   
        if target_domain: 
            try:
                print('-- inside UpdateSignatureData.post(), trying to serialize ...')
                print('-- request.data: %s' % request.data)
                prefix_domain = 'http://' + target_domain

                # get domain from serializer
                domain_rec = Domain.objects.get(domain_name=prefix_domain)
            
                # initialize serializer w/ record instance AND data for update 
                serializer = WebSignatureSerializer(data=request.data)

                if serializer.is_valid():
                    print('valid WebSignature serializer -> updating Domain record')
                    print(serializer.validated_data)

                    # parse site redirect
                    if serializer.data.get('site_redirect', None):
                        print('--- site redirects to %s' % serializer.validated_data['site_redirect'])
                        domain_rec.redirect_url = serializer.validated_data['site_redirect']
                        domain_rec.save()

                    # parse server type
                    if serializer.data.get('server_type', None):
                        domain_rec.server_type.set( serializer.validated_data['server_type'] )

                    # parse x_powered_by
                    if serializer.data.get('x_powered_by', None):
                        x_powered = serializer.validated_data['x_powered_by'].split(', ')
                        # clear x-powered-by tags
                        domain_rec.x_powered_by.clear()

                        for tag in x_powered:
                            domain_rec.x_powered_by.add(tag)

                    # parse wp_version
                    if serializer.data.get('wp_version', None):
                        domain_rec.software_tags.set( serializer.validated_data['wp_version'] )

                    if serializer.data.get('wp_addons', None):
                        addon_tags = serializer.validated_data['wp_addons']
                        # clear software tags
                        domain_rec.software_tags.clear()

                        for tag in addon_tags:
                            domain_rec.software_tags.add(tag)
 
                    # parse MX records
                    if serializer.data.get('mx_records', None):
                        mx_tags = serializer.validated_data['mx_records']

                        print('type for mx_tags: %s' % type(mx_tags))
                        # clear tags
                        domain_rec.mx_servers.clear()

                        for tag in mx_tags:
                            print('-- adding %s mx record tag to %s' % (tag, domain_rec.domain_name))
                            domain_rec.mx_servers.add( tag.lower() )
                
                    return Response("Updated web signature data for %s" % target_domain, status=status.HTTP_200_OK)
            
                else:
                    print('-- invalid serializer for UpdateSignatureData.post --')
                    print(serializer.errors)
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


            except Domain.DoesNotExist:
                err_msg = ' -- Domain record not found for: %s ' % request.data['domain_name']

                print(err_msg)
                return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)

            except Exception as e:
                print('-- generic error on UpdateSignatureData.post: %s' % str(e))
                return Response(str(e), status=status.HTTP_400_BAD_REQUEST)

        else:
            err_msg = ' -- no domain data in request --'
            print(err_msg)
            return Response(err_msg, status=status.HTTP_400_BAD_REQUEST)

class CheckPendingZones(APIView):
    parser_classes = (JSONParser,)
    #authentication_classes = (TokenAuthentication,)
    #permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        ''' Retrieve count of zone files notprocessed for TLD in request data'''
        try:
            _tld = '.' + request.GET.get('tld_type', '.com')
            print('passed url query param: %s' % _tld)
            zone_tld = ZoneExtension.objects.get(tld_extension=_tld)

            zone_directory = zone_tld.storage_path
            print('zone fragment directory: %s' % zone_directory)
            # pull out only files, not directories - if '.txt' in filename
            frag_count = len([name for name in os.listdir(zone_directory) if '.txt' in name])           
            print('frag_count in CheckPendingZones view -> Spiderfarm: %s' % frag_count)           
 
            data = {'tld_type': _tld, 
                    'frag_count': frag_count}

            serializer = PendingZonesSerializer(data)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            print(e)
            return Response(str(e), status=status.HTTP_400_BAD_REQUEST)  
          
class SpiderJobStatus(APIView):
    parser_classes = (JSONParser,)
 
    def get(self, request, *args, **kwargs):
        status = request.GET.get('status', None)
        crawl_type = request.GET.get('crawl-type', 'import')
        lead_type = request.GET.get('lead-type', None)
 
        if status:
            if status.lower() == 'check':
                print('-- status variable passed to /spiderfarm/spider-jobs')
                # get all SpiderJobs currently running
                try:
                    # trying to get data for SSL domain crawls
                    if crawl_type:
                        print('-- crawl-type passed in GET: %s' % crawl_type)

                        if crawl_type == 'ssl':
                            # retrieve running job id for ssl crawl 
                            job_ids = job_ids = SpiderJob.objects.filter(job_status='RUNNING', crawl_type='SSL').values_list('celery_id', flat=True).distinct()

                        else:
                            job_ids = SpiderJob.objects.filter(job_status__in=['RUNNING','PENDING']).values_list('celery_id', flat=True).distinct()

                        # should contain either an error msg, or job_status as running, or
                        #  or job_status and task_id
                        job_dict = parse_spiderjob_status(job_ids)

                        return Response(job_dict)

                except Exception as e:
                    print(e)
                    data = {'job_status': e}
                    return Response(data)

            else:
                data = {'job_status': 'ready'}
                return Response(data)            
            
class ImportDomainsView(LoginRequiredMixin, View):

    def post(self, request, *args, **kwargs):
        ''' '''
        print(' -- inside spiderfarm.ImportDomainsView.post')
        request_post = request.POST
        pending_zones = request_post.get('import_domains_pending_zones')
        zone_tld = request_post.get('import_domains_tld_type')
        zone_count = request_post.get('import_domains_zone_count')

        if pending_zones <= zone_count:
            import_count = pending_zones
        else:
            import_count = zone_count

        print('zone_tld: %s' % zone_tld)
        print('import_count: %s' % import_count)
        
        task = import_domains.delay(zone_tld, import_count)

        return HttpResponse(json.dumps({'task_id': task.id}), content_type='application/json')
        
    def get(self, request, *args, **kwargs):
        task_id = request.GET.get('task_id', None)

        if task_id:
            task = AsyncResult(task_id)
            data = {
                'status': 'running',
                'state': task.state,
                'result': task.result,
            }

            return HttpResponse(json.dumps(data), content_type='application/json')

        data = { 'status': 'ready'}
        return HttpResponse(json.dumps(data), content_type='application/json')             


















