from __future__ import absolute_import, unicode_literals
import re
from celery import task, shared_task, current_task
from datetime import datetime, timedelta, timezone
from common.models import User
from itertools import cycle
from .models import Lead
from spiderfarm.models import ZoneExtension, ZoneFragment, SpiderJob, Domain
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db.models import Q
from django.shortcuts import reverse
from django.template.loader import render_to_string
from django.db.models import Count

from accounts.models import User
from leads.models import Lead
from spiderfarm.models import Domain

import json
import boto3
import time
import os
import collections

#################################################################################

def flatten(x):
    result = []
    for el in x:
        if isinstance(x, collections.Iterable) and not isinstance(el, str):
            result.extend(flatten(el))
        else:
            result.append(el)

    return result

def get_progress_percentage(total, current_val):
    ''' returns formatted string for AJAX output on progress bar HTML '''
    _val = int(current_val) / int(total)
    _scaled = int(_val * 100)
    return str(_scaled) + '%'


def get_rendered_html(template_name, context={}):
    html_content = render_to_string(template_name, context)
    return html_content


@task
def send_email(subject, html_content,
               text_content=None, from_email=None,
               recipients=[], attachments=[], bcc=[], cc=[]):
    # send email to user with attachment
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    if not text_content:
        text_content = ''
    email = EmailMultiAlternatives(
        subject, text_content, from_email, recipients, bcc=bcc, cc=cc
    )
    email.attach_alternative(html_content, "text/html")
    for attachment in attachments:
        # Example: email.attach('design.png', img_data, 'image/png')
        email.attach(*attachment)
    email.send()


@task
def send_lead_assigned_emails(lead_id, new_assigned_to_list, site_address):
    lead_instance = Lead.objects.filter(
        ~Q(status='converted'), pk=lead_id, is_active=True
    ).first()
    if not (lead_instance and new_assigned_to_list):
        return False

    users = User.objects.filter(id__in=new_assigned_to_list).distinct()
    subject = "Lead '%s' has been assigned to you" % lead_instance
    from_email = settings.DEFAULT_FROM_EMAIL
    template_name = 'lead_assigned.html'

    url = site_address
    url += '/leads/' + str(lead_instance.id) + '/view/'

    context = {
        "lead_instance": lead_instance,
        "lead_detail_url": url,
    }
    mail_kwargs = {"subject": subject, "from_email": from_email}
    for user in users:
        if user.email:
            context["user"] = user
            html_content = get_rendered_html(template_name, context)
            mail_kwargs["html_content"] = html_content
            mail_kwargs["recipients"] = [user.email]
            send_email.delay(**mail_kwargs)



@task
def send_email_to_assigned_user(recipients, lead_id, domain='demo.django-crm.io', protocol='http'):
    """ Send Mail To Users When they are assigned to a lead """
    lead = Lead.objects.get(id=lead_id)
    created_by = lead.created_by
    for user in recipients:
        recipients_list = []
        user = User.objects.filter(id=user, is_active=True).first()
        if user:
            recipients_list.append(user.email)
            context = {}
            context["url"] = protocol + '://' + domain + \
                reverse('leads:view_lead', args=(lead.id,))
            context["user"] = user
            context["lead"] = lead
            context["created_by"] = created_by
            subject = 'Assigned a lead for you. '
            html_content = render_to_string(
                'assigned_to/leads_assigned.html', context=context)

            msg = EmailMessage(
                subject,
                html_content,
                to=recipients_list
            )
            msg.content_subtype = "html"
            msg.send()

@shared_task
def create_lead_from_file(validated_rows):
    """Parameters : validated_rows
    This function is used to create leads from a given file.
    """
    print('-- inside leads.tasks.create_lead_from_file --')

    total_domains = len(validated_rows)
    print('-- total leads being uploaded: %s --' % total_domains)
    
    cel_id = current_task.request.id
    print('-- task.id: %s--' % cel_id)
    
    _domain_count = 0
    _tld_ext = ZoneExtension.objects.get(tld_extension='.com')
    current_domain_progress = 0
    spiderjob_total = total_domains
    uploaded_domains = []

    # create an 'import csv' spiderjob
    upload_spiderjob = SpiderJob.objects.create(spider_type='IMPORT',
                                                crawl_type='CSV',
                                                data_type='SSL',
                                                job_status='RUNNING',
                                                celery_id=cel_id)

    # take off the header row of the CSV
    val_rows = validated_rows[1:]
  
    upload_domains = flatten(val_rows)

    #_last_ssl_update = datetime.now()
    '''
    for domain in upload_domains:
        _domain_count += 1
        current_domain_progress += 1
        _added_domain = ''

        #print('-- row value: %s' % domain)

        target_domain = 'http://' + domain
        #print('-- domain to check: %s --' % target_domain)
        phase_progress = get_progress_percentage(total_domains, _domain_count)
        spiderjob_progress = get_progress_percentage(spiderjob_total, current_domain_progress)
        
        if not Domain.objects.filter(domain_name=target_domain).exists():
            _domain = Domain()
            _domain.domain_name = target_domain
            _domain.tld_ext = _tld_ext    
            _domain.import_status = 'SSL'
            #_domain.last_ssl_update = _last_ssl_update
            _domain.save()
            _domain.spider_jobs.add(str(upload_spiderjob))
            # update _added_domain for progress UI
            _added_domain = _domain.domain_common
            uploaded_domains.append(_added_domain)
         
        current_task.update_state(state='PROGRESS',
                                      meta={'import_status': 'Cleaning data for ',
                                            'current_domain': domain,
                                            'domain_count': str(_domain_count),
                                            'current_domain_progress': phase_progress,
                                            'total_domains': total_domains,
                                            'spiderjob_label': str(upload_spiderjob),
                                            'spiderjob_progress': spiderjob_progress,})
        
    # reset phase counters
    _domain_count = 0
    '''
    # now invoke SSL crawlers for all uploaded domains
    for domain in upload_domains:
        time.sleep(0.01)
        _domain_count += 1
        current_domain_progress += 1
        phase_progress = get_progress_percentage(total_domains, _domain_count)
        spiderjob_progress = get_progress_percentage(spiderjob_total, current_domain_progress)

        upload_spiderjob.invoke_lambda(domain, 'gtld_importer', str(upload_spiderjob))

        current_task.update_state(state='PROGRESS',
                                      meta={'import_status': 'Crawling SSL on ',
                                            'current_domain': domain,
                                            'domain_count': str(_domain_count),
                                            'current_domain_progress': phase_progress,
                                            'total_domains': total_domains,
                                            'spiderjob_label': str(upload_spiderjob),
                                            'spiderjob_progress': spiderjob_progress,})

    upload_spiderjob.job_status = 'COMPLETE'
    upload_spiderjob.end_timestamp = datetime.now()
    upload_spiderjob.save()
    
    return {'import_status': '-- Lead uploads complete --',
            'current_domain': '',
            'domain_count': str(_domain_count),
            'current_domain_progress': '100%',
            'total_domains': total_domains,
            'spiderjob_label': str(upload_spiderjob),
            'spiderjob_progress': '100%',}

@shared_task
def assign_leads(sales_users, start_date, end_date, lead_type='SSL'):
    # convert start and end strings to datetime objects - format: YYY-MM-DD
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    user_list = []

    # get all unassigned leads
    _unassigned = Lead.objects.annotate(assigned_count=Count('assigned_to')).filter(assigned_count=0)

    print('-- _unassigned #: %s ' % _unassigned.count())
    # start by querying for either SSL or Domain expire 
    if lead_type == 'SSL':
        unassigned_list = _unassigned.filter(domain__ssl_expire__gte=start_dt).filter(domain__ssl_expire__lte=end_dt)

    print('-- unassigned_list #: %s ' % unassigned_list.count())

    if 'ALL' in sales_users:
        print('-- inside ALL option in assign_ssl_leads')
        # get all Users who can be assigned leads
        all_users = User.objects.filter(role__icontains='SALES')
        # put into user list

        for user in all_users:
            print('adding %s to user list' % user)
            user_list.append(user)

    else:
        # add passed users to list
        print('-- inside LIST option in assign_ssl_leads')
        for _email in sales_users:
            _user = User.objects.get(email=_email)
            user_list.append(_user)

    user_pool = cycle(user_list)
    lead_count = 0

    for lead in unassigned_list:
        lead_count += 1
        print('-- lead_count: %s' % lead_count)
        current_assign = next(user_pool)
        
        if not current_assign:
            print('-- cycle returned None, cycle again for user obj')
            current_assign = next(user_pool)

        lead.assigned_to.set([current_assign])

        prep_percent = str(int( (float(lead_count) / unassigned_list.count()) * 100)) + '%'

        current_task.update_state(state='PROGRESS',
                                  meta={'current': lead_count,
                                        'total': unassigned_list.count(),                                                                                    'percent': prep_percent,})

    return {'current': lead_count, 'total': unassigned_list.count(), 'percent': '100%'}
        

@shared_task
def unassign_leads(sales_users, start_date, end_date, lead_type='SSL'):
    # convert start and end strings to datetime objects - format: YYY-MM-DD
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")

    user_list = []

    # get all assigned leads
    _assigned = Lead.objects.annotate(assigned_count=Count('assigned_to')).filter(assigned_count__gt=0)

    print('-- _assigned #: %s ' % _assigned.count())
    # start by querying for either SSL or Domain expire 
    if lead_type == 'SSL':
        assigned_list = _assigned.filter(domain__ssl_expire__gte=start_dt).filter(domain__ssl_expire__lte=end_dt)

    print('-- assigned_list #: %s ' % assigned_list.count())

    lead_count = 0

    if 'ALL' in sales_users:

        print('-- inside ALL option in unassign_ssl_leads')
        # clear all assigned_to fields for each lead
        for lead in assigned_list:
            lead_count += 1

            lead.assigned_to.clear()
            prep_percent = str(int( (float(lead_count) / assigned_list.count()) * 100)) + '%'

            current_task.update_state(state='PROGRESS',
                                      meta={'current': lead_count,                                                                                  'total': assigned_list.count(),                                                                       'percent': prep_percent,})
    
    else:
        print('-- inside LIST option in unassign_ssl_leads')
        for _email in sales_users:
            _user = User.objects.get(email=_email)
            user_list.append(_user)

        for lead in assigned_list:
            lead_count += 1
            # go through each lead, pull assigned sales ppl and remove if on list
            _sales_users = lead.assigned_to.all()

            for user in user_list:
                if user in _sales_users:
                    lead.assigned_to.remove(user)

            prep_percent = str(int( (float(lead_count) / assigned_list.count()) * 100)) + '%'
            current_task.update_state(state='PROGRESS',
                                      meta={'current': lead_count,                                                                                  'total': assigned_list.count(),                                                                       'percent': prep_percent,})

    return {'current': lead_count, 'total': assigned_list.count(), 'percent': '100%'}

