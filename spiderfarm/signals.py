from crm import settings
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import ZoneExtension, ZoneFragment, Domain
from leads.models import Lead
import os
import hashlib

@receiver(pre_save, sender=ZoneExtension)
def make_zonefile_dir(sender, instance, **kwargs):
    print('-- inside make_zonefile_dir signal -> presave')
    dir_label = '/' + instance.tld_extension.lstrip('.')
    zonefile_path = settings.ZONE_FRAGMENT_DIR + dir_label
    imported_path = zonefile_path + '/' + 'imported'

    try:
        os.mkdir(zonefile_path)
        os.mkdir(imported_path)

    except:
        print('cannot create path for TLD extension: %s' % instance.tld_extension)

    finally:
        print('created path for zone fragment storage: %s' % zonefile_path)
        instance.storage_path = zonefile_path

@receiver(post_save, sender=ZoneFragment)
def set_zone_identifiers(sender, instance, created, **kwargs):
    if created:
        print('-- spiderfarm.signals.get_domain_count() -> post_save')
        sha1 = hashlib.sha1()
        BUF_SIZE = 65536
        # get length of returned list 
        url_count = len(instance.get_unique_domains())
        print('-- Zone fragment has %s unique domains ..' % url_count)
        instance.unique_domains = url_count
        # get sha1 checksum for file

        with open(instance.zone_file.path, 'rb') as f:
            buf = f.read(BUF_SIZE)
            while len(buf) > 0:
                sha1.update(buf)
                buf = f.read(BUF_SIZE)

        print('hex: %s' % sha1.hexdigest())
        instance.zone_signature = sha1.hexdigest()
        instance.save() 

@receiver(post_save, sender=Domain)
def create_lead(sender, instance, created, **kwargs):
    print('-- inside create_lead signal --')
    # make sure domain is created, save new Lead
    if created:
        print('-- creating Lead now --')
        new_lead = Lead.objects.create(domain=instance, status='NEW')
        # save Lead
        new_lead.save()
        # set domain_common 
        instance.domain_common = instance.no_prefix_url()
        instance.save()
