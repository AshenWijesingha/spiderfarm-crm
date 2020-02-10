from __future__ import absolute_import, unicode_literals
import re
from celery import task, shared_task, current_task
from datetime import datetime, timedelta, timezone
from common.models import User
from itertools import cycle
from spiderfarm.models import ZoneExtension, ZoneFragment, SpiderJob, Domain
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db.models import Q, Count
from django.shortcuts import reverse
from django.template.loader import render_to_string
from celery.result import AsyncResult
from accounts.models import User
from leads.models import Lead
import time
import json
import boto3
import time
import os

def get_progress_percentage(total, current_val):
    ''' returns formatted string for AJAX output on progress bar HTML '''
    _val = int(current_val) / int(total)
    _scaled = int(_val * 100)
    return str(_scaled) + '%'

def create_zone_fragments(tld_type, frag_count):
    ''' returns list of zone fragments to be imported '''
    frag_list = []
    _count = int(frag_count)

    zone_tld = ZoneExtension.objects.get(tld_extension=tld_type)
    path_dir = zone_tld.storage_path

    zone_frags = [name for name in os.listdir(path_dir) if '.txt' in name]
    
    for filename in zone_frags[:_count]:
        full_path = path_dir + '/' + filename
        print('adding to frag_list: %s' % full_path)
        _zone_frag = ZoneFragment.objects.create(tld_ext=zone_tld, zone_file=full_path)
        _zone_frag.save()

        frag_list.append(_zone_frag)

    print('created %s ZoneFragment records for import ...' % len(frag_list))
    

def create_import_spiderjob(zonefrag_list, cel_id=''):
    '''
    input: list of ZoneFragments and celery task id
    returns: a Zone Import SpiderJob object
    '''
    _spiderjob = SpiderJob.objects.create(spider_type = 'IMPORT',
                                             crawl_type = 'ZONE',
                                             data_type = 'SSL',
                                             job_status = 'PENDING',
                                             celery_id = cel_id)

    # save the SpiderJob to get pk for tag text
    _spiderjob.save()

    # tag ZoneFragments with SpiderJob, vice versa
    for frag in zonefrag_list:
        frag.spider_jobs.add(str(_spiderjob))

    return _spiderjob

def assign_zones_to_spiderjobs(_zonefrags, celery_id, MAX=settings.IMPORT_MAX):
    '''
    input: ZoneFragment QuerySet, celery_id string
    output: list of SpiderJobs

    The function reads the ZoneFragments passed to it,
        breaking up and assigning ZoneFragments for each
        SpiderJob so the total domains crawled per job doesn't
        exceed the max setting (10k domains)
    '''
    spider_frags, spiderjob_list = [], []
    domain_count = _zonefrags[0].unique_domains

    for pos in range(_zonefrags.count()):
        print('-- inside loop for assign_zonez_to_spiderfjobs')
        if domain_count < MAX:
            print('-- domain count less than %s' % MAX)
            try:

                next_count = domain_count + _zonefrags[pos + 1].unique_domains
                print('-- next_count = %s' % next_count)
                if next_count > MAX:
                    print('-- next_count > %s' % MAX)
                    spiderjob_list.append( create_import_spiderjob(spider_frags, celery_id) )
                    spider_frags = []
                    domain_count = 0

            except IndexError:
                # reached end of list, create SpiderJob with remaining ZoneFrags
                # adding edge case handling for single zone fragment
                if _zonefrags.count() == 1:
                    print('-- single fragment passed, add to spider fragment list and move on')
                    spider_frags.append(_zonefrags[0])

                print('-- appending new spiderjob to return list')
                spiderjob_list.append( create_import_spiderjob(spider_frags, celery_id) )
        
        print('-- not greater than MAX, adding to domain count and spider_frags list')
        domain_count += _zonefrags[pos].unique_domains
        spider_frags.append(_zonefrags[pos])

    print('created %s import SpiderJobs' % len(spiderjob_list))
    for job in spiderjob_list:
        print('%s has %s domains' % (str(job), len(job.get_domain_list() )))

    return spiderjob_list

@shared_task
def import_domains(tld_type, frag_count):
    try:
        print('-- inside spiderfarm.tasks.import_domains --')
        # --- AWS lambda client ---
        lambda_client = boto3.client('lambda', region_name='us-west-2')
        # pull the TLD Extension model 
        tld_obj = ZoneExtension.objects.get(tld_extension=tld_type)    
        # using the storage path, get list slice of job range to run
        zone_directory = tld_obj.storage_path 

        # create new ZoneFragment records from frag_count
        create_zone_fragments(tld_type, frag_count) 

        _import_frags = ZoneFragment.objects.filter(imported=False).order_by('unique_domains')

        print('-- # of import fragments created: %s' % _import_frags.count())

        cel_id = current_task.request.id
        print('-- task.id: %s' % cel_id)
        #print('-- single _import_frag slice: %s' % _import_frags.first())

        # -- create set of pending spiderjobs
        spiderjob_list = assign_zones_to_spiderjobs(_import_frags, cel_id)

        print(spiderjob_list)

        current_spiderjob = 0
        current_domain_progress = 0

        print('# of pending import spider jobs: %s' % len(spiderjob_list))
        # MAIN TASK -> run through spiderjob_list, mobbing domains to GTLD lambda
        # -----------------------------------------------------------------------
    
        for job in spiderjob_list:
            # -- get total count of domains in ZoneFragment queryset ---
            _domains = job.get_domain_list()
            _domain_count = 0

            job.job_status = 'RUNNING'
            job.save()

            total_domains = len(_domains)
            _update_delay = (total_domains * 0.001) * 2
            spiderjob_total = total_domains * len(spiderjob_list)
            current_spiderjob += 1

            # -- if only 1 spiderjob queued up, skip initial delay to clear lambda concurrency
            if current_spiderjob > 1:
                time.sleep(_update_delay)
    
            # --- hit GTLD Import lambda; primes domains and saves only valid SSL --
            for domain in _domains:
                _domain_count +=1
                current_domain_progress +=1
                job.invoke_lambda(domain, 'gtld_importer', str(job))
        
                phase_progress = get_progress_percentage(total_domains, _domain_count)
                spiderjob_progress = get_progress_percentage(spiderjob_total, current_domain_progress)
                
                count_status = "Crawling %s of %s domains" % (_domain_count, total_domains)

                current_task.update_state(state='PROGRESS',
                                              meta={'import_status': count_status,
                                                    'current_domain': _domain_count,
                                                    'current_domain_progress': phase_progress,
                                                    'total_domains': total_domains,
                                                    'spiderjob_label': str(job),
                                                    'spiderjob_progress': spiderjob_progress,
                                                    'spiderjob_total': spiderjob_total,
                                                    'current_spiderjob': current_spiderjob, 
                                                    'total_spiderjobs': len(spiderjob_list),})

            # set spiderjob status to complete
            job.job_status = 'COMPLETE'
            job.save()
        
            time.sleep(_update_delay)

            # --- move onto zone file cleanup ---
            current_task.update_state(state='PROGRESS',
                                          meta={'import_status': 'Cleaning up imported zone files..',
                                                'current_domain': domain,
                                                'current_domain_progress': '100%',
                                                'total_domains': total_domains,
                                                'spider_job': str(job),
                                                'spiderjob_progress': '100%',
                                                'spiderjob_total': spiderjob_total,
                                                'total_spiderjobs': len(spiderjob_list),})
    
        # --- move the imported ZoneFragment to the TLD extension's imported directory ---
        for frag in _import_frags:
            frag.imported = True
            frag_path = frag.zone_file.path
            frag_filename = frag_path.replace('/home/spiderfarmer/SFCRM/media/uploads/zone_files/com/', '')
            imported_path = '/home/spiderfarmer/SFCRM/media/uploads/zone_files/com/imported'
            imported_filepath = imported_path + '/' + frag_filename
            os.rename(frag_path, imported_filepath)
            frag.save()
     
        # -- end of complete spider_job list, tidy up the UI and close gracefully 
        return {'import_status': '-- Domain importing complete --', 
                'current_domain': '---', 
                'current_domain_progress': '100%', 
                'spider_job': str(job), 
                'spiderjob_progress': '100%',
                'spiderjob_total': spiderjob_total, 
                'total_spiderjobs': len(spiderjob_list)}

    except Exception as e:
        print('-- Exception occured on spiderfarm.tasks.import_domain --')
        print(str(e))
        return {'import_status': str(e)}
    
'''
@shared_task
def ssl_post_import():
    # check if any import SpiderJobs are currently running
    running_imports = SpiderJob.objects.exclude(job_status='COMPLETE').filter(spider_type__in=['IMPORT', 'GHOST']).filter(crawl_type__in=['ZONE','DOMAIN'])
    
    new_ssl_domains = Domain.objects.filter(last_ssl_update__isnull=True)
    # only do SSL post imports if no other imports are running

    if running_imports.count() == 0:
        if new_ssl_domains.count() >= 100:
        
            cel_id = current_task.request.id
            counter = 0
            _timestamp = datetime.now()

            ssl_spiderjob = SpiderJob.objects.create(spider_type='IMPORT',
                                                     crawl_type='DOMAIN',
                                                     data_type='SSL',
                                                     job_status='RUNNING',
                                                     celery_id=cel_id)

            
            if new_ssl_domains.count() < settings.IMPORT_MAX:
                counter = new_ssl_domains.count()
            else:
                counter = settings.IMPORT_MAX
            
            for domain in new_ssl_domains[:counter]:
                print('--')
                print('-- invoking lambda for %s' % domain.no_prefix_url())
                ssl_spiderjob.invoke_lambda(domain.no_prefix_url(), 'ssl_crawler')
                domain.import_status = 'SSL'
                #domain.last_ssl_update = _timestamp
                domain.save()

            end_timestamp = datetime.now()
            ssl_spiderjob.job_status = 'COMPLETE'
            ssl_spiderjob.end_timestamp = end_timestamp
            ssl_spiderjob.save()

        else:
            print('-- not enough NEW import domains to start SSL post-import session --')

    else:
        print('-- running import jobs, cannot start SSL post-import --')
'''
            
@shared_task
def host_data_cleanup():
    # get all SSL status leads and fix any split hosting data
    running_imports = SpiderJob.objects.exclude(job_status='COMPLETE').filter(spider_type__in=['IMPORT', 'GHOST']).filter(crawl_type__in=['ZONE','DOMAIN'])

    imported_ssl_domains = Domain.objects.filter(import_status='SSL')

    if running_imports.count() == 0:
        if imported_ssl_domains.count() >= 100:

            cel_id = current_task.request.id
            counter = 0
            _timestamp = datetime.now()

            cleanup_spiderjob = SpiderJob.objects.create(spider_type='IMPORT',
                                                         crawl_type='DOMAIN',
                                                         data_type='HOST',
                                                         job_status='RUNNING',
                                                         celery_id=cel_id)

            if imported_ssl_domains.count() < settings.IMPORT_MAX:
                counter = imported_ssl_domains.count()
            else:
                counter = settings.IMPORT_MAX

            cleanup_domains = imported_ssl_domains[:counter]
            # first check for whois
            for domain in cleanup_domains:
                if domain.last_whois_update:
                    pass
                else:
                    cleanup_spiderjob.invoke_lambda(domain.no_prefix_url(), 'whois_pull')
                    #domain.last_whois_update = _timestamp
                    domain.import_status = 'HOST'
                    domain.save()

            time.sleep(20)

            # then check for missing geoip
            for domain in cleanup_domains:
                if domain.last_geoip_update:
                    pass
                else:
                    cleanup_spiderjob.invoke_lambda(domain.no_prefix_url(), 'geoip_lookup')
                    domain.last_geoip_update = _timestamp
                    domain.import_status = 'HOST'
                    domain.save()

            end_timestamp = datetime.now()
            cleanup_spiderjob.job_status = 'COMPLETE'
            cleanup_spiderjob.end_timestamp = end_timestamp
            cleanup_spiderjob.save() 

            remaining_ssl_domains = Domain.objects.filter(import_status='SSL')
            print('count of remaining SSL flagged imports: %s' % remaining_ssl_domains.count())
            remaining_ssl_domains.update(import_status='HOST')

        else:
            print('-- not enough SSL domains to start HOST data cleanup session --')

    else:
        print('-- running import jobs, cannot start HOST data cleanup session --')


@shared_task
def ghost_crawl_import():
    # get all HOST status imports and initiate ghost crawls for the domains
    running_imports = SpiderJob.objects.exclude(job_status='COMPLETE').filter(spider_type__in=['IMPORT', 'GHOST']).filter(crawl_type__in=['ZONE','DOMAIN', 'CSV'])

    ghost_domains = Domain.objects.filter(last_ssl_update__isnull=False).filter(last_ghost_crawl__isnull=True).order_by('-time_added')

    if running_imports.count() == 0:
        if ghost_domains.count() >= 100:

            cel_id = current_task.request.id
            counter = 0
            _timestamp = datetime.now()

            ghost_spiderjob = SpiderJob.objects.create(spider_type='GHOST',
                                                               crawl_type='DOMAIN',
                                                               data_type='WEB',
                                                               job_status='RUNNING',
                                                               celery_id=cel_id)

            if ghost_domains.count() < settings.IMPORT_MAX:
                counter = ghost_domains.count()
            else:
                counter = settings.IMPORT_MAX

            _domains = ghost_domains[:counter]
            
            for domain in _domains:
                ghost_spiderjob.invoke_lambda(domain.no_prefix_url(), 'ghost_crawler')
                # sleep between Ghost Crawler calls to space out execution time, don't want
                #  beat jobs to overlap
                time.sleep(0.1)
                domain.import_status = 'GHOST'
                domain.spider_jobs.add(str(ghost_spiderjob))
                domain.save()

            end_timestamp = datetime.now()
            ghost_spiderjob.job_status = 'COMPLETE'
            ghost_spiderjob.end_timestamp = end_timestamp
            ghost_spiderjob.save()
        
        else:
            print('-- not enough cleaned HOST domains to start GHOST crawl session --')

    else:
        print('-- running import jobs, cannot start GHOST crawl session --')


@shared_task
def ssl_daily_update():
    # get all assigned Leads
    _assigned = Lead.objects.annotate(assigned_count=Count('assigned_to')).filter(assigned_count__gt=0)
    # get today's datetime obj
    today = datetime.now()

    three_days_earlier = today - timedelta(days=3)
    three_days_later = today + timedelta(days=3)
    cel_id = current_task.request.id

    _lower_bound = _assigned.filter(domain__ssl_expire__gte=three_days_earlier)

    _interval = _lower_bound.filter(domain__ssl_expire__lte=three_days_later)

    _update_domains = []

    ssl_daily = SpiderJob.objects.create(spider_type='UPDATE',
                                             crawl_type='DOMAIN',
                                             data_type='SSL',
                                             job_status='RUNNING',
                                             celery_id=cel_id)
    
    for entry in _interval:
        print('-- adding %s to update list' % entry.domain.domain_common)
        _update_domains.append(entry.domain)
                
    for domain in _update_domains:
        print('--')
        print('-- invoking lambda for %s' % domain.no_prefix_url())
        ssl_daily.invoke_lambda(domain.no_prefix_url(), 'ssl_crawler')
        domain.last_ssl_update = today
        domain.save()

    end_timestamp = datetime.now()
    ssl_daily.job_status = 'COMPLETE'
    ssl_daily.end_timestamp = end_timestamp
    ssl_daily.save()

    print('-- updated %s domains --' % _update_domains.count())













